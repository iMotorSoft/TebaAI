"""Read-only PostgreSQL retrieval for relation QA."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from infrastructure.postgres.transaction import fetch_all


_SELECT_FIELDS = """
    SELECT ch.id::text AS chunk_id,
           ch.document_id::text AS document_id,
           d.title AS document_title,
           COALESCE(d.subtitle, '') AS subtitle,
           d.status AS document_status,
           ch.content,
           ch.language,
           ch.page_start,
           ch.page_end,
           COALESCE(ch.chapter, '') AS chapter,
           COALESCE(ch.section_title, ch.section, '') AS section,
           COALESCE(ch.node_path, '') AS node_path,
           COALESCE(ch.block_type, '') AS block_type,
           COALESCE(ch.block_subtype, '') AS block_subtype,
           COALESCE(ch.evidence_role, '') AS evidence_role,
           COALESCE(ch.citable, true) AS citable,
           COALESCE(ch.metadata, '{}'::jsonb) AS metadata,
           COALESCE(ch.bibliographic_metadata, '{}'::jsonb) AS bibliographic_metadata,
           ch.chunk_index
    FROM library_document_chunks ch
    JOIN library_documents d ON d.id = ch.document_id
"""


def _statuses(include_test_candidates: bool) -> list[str]:
    return ["ready", "test_candidate"] if include_test_candidates else ["ready"]


def _like_patterns(variants: Sequence[str]) -> list[str]:
    """Build ILIKE patterns without matching short Latin transliterations in words."""
    patterns: list[str] = []
    for raw in variants:
        value = raw.strip()
        if len(value) < 2:
            continue
        has_hebrew = any("\u0590" <= char <= "\u05ff" for char in value)
        if not has_hebrew and len(value) <= 3:
            patterns.extend([value, f"{value} %", f"% {value}", f"% {value} %"])
        else:
            patterns.append(f"%{value}%")
    return list(dict.fromkeys(patterns))


async def search_fts_chunks(
    conn: AsyncConnection,
    *,
    knowledge_scope_id: UUID,
    variants: Sequence[str],
    language: str,
    include_test_candidates: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """Run websearch FTS per variant using only controlled vector columns."""
    results: dict[str, dict[str, Any]] = {}
    statuses = _statuses(include_test_candidates)
    per_variant = max(3, min(limit, 12))

    for variant in variants:
        term = variant.strip()
        if len(term) < 2:
            continue
        is_hebrew = any("\u0590" <= char <= "\u05ff" for char in term)
        use_spanish = language == "es" and not is_hebrew
        vector_column = "search_vector_es" if use_spanish else "search_vector_simple"
        config = "spanish" if use_spanish else "simple"
        rows = await fetch_all(
            conn,
            _SELECT_FIELDS
            + f"""
            WHERE ch.knowledge_scope_id = %(scope_id)s
              AND d.status = ANY(%(statuses)s)
              AND ch.{vector_column} @@ websearch_to_tsquery(
                    %(config)s::regconfig, %(query)s
                  )
            ORDER BY ts_rank_cd(
                       ch.{vector_column},
                       websearch_to_tsquery(%(config)s::regconfig, %(query)s)
                     ) DESC,
                     ch.chunk_index
            LIMIT %(limit)s
            """,
            {
                "scope_id": str(knowledge_scope_id),
                "statuses": statuses,
                "config": config,
                "query": term,
                "limit": per_variant,
            },
        )
        for row in rows:
            row["retrieval_methods"] = ["fts_websearch"]
            row["score"] = max(float(row.get("score") or 0.0), 0.8)
            results.setdefault(row["chunk_id"], row)
    return list(results.values())[:limit]


async def search_ilike_chunks(
    conn: AsyncConnection,
    *,
    knowledge_scope_id: UUID,
    variants: Sequence[str],
    include_test_candidates: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """Run literal ILIKE fallback over canonical PostgreSQL text."""
    patterns = _like_patterns(variants)
    if not patterns:
        return []
    rows = await fetch_all(
        conn,
        _SELECT_FIELDS
        + """
        WHERE ch.knowledge_scope_id = %(scope_id)s
          AND d.status = ANY(%(statuses)s)
          AND ch.content ILIKE ANY(%(patterns)s)
        ORDER BY ch.page_start NULLS LAST, ch.chunk_index
        LIMIT %(limit)s
        """,
        {
            "scope_id": str(knowledge_scope_id),
            "statuses": _statuses(include_test_candidates),
            "patterns": patterns,
            "limit": limit,
        },
    )
    for row in rows:
        row["retrieval_methods"] = ["ilike_fallback"]
        row["score"] = 0.75
    return rows


async def search_relation_pattern_chunks(
    conn: AsyncConnection,
    *,
    knowledge_scope_id: UUID,
    patterns: Sequence[str],
    include_test_candidates: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """Find explicit relation phrases and exact cooccurrence candidates."""
    like_patterns = [f"%{value}%" for value in patterns if value]
    if not like_patterns:
        return []
    rows = await fetch_all(
        conn,
        _SELECT_FIELDS
        + """
        WHERE ch.knowledge_scope_id = %(scope_id)s
          AND d.status = ANY(%(statuses)s)
          AND ch.content ILIKE ANY(%(patterns)s)
        ORDER BY ch.page_start NULLS LAST, ch.chunk_index
        LIMIT %(limit)s
        """,
        {
            "scope_id": str(knowledge_scope_id),
            "statuses": _statuses(include_test_candidates),
            "patterns": like_patterns,
            "limit": limit,
        },
    )
    for row in rows:
        row["retrieval_methods"] = ["relation_pattern"]
        row["score"] = 0.9
    return rows


async def search_cooccurrence_chunks(
    conn: AsyncConnection,
    *,
    knowledge_scope_id: UUID,
    concept_a_variants: Sequence[str],
    concept_b_variants: Sequence[str],
    include_test_candidates: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """Find chunks containing at least one variant of each concept."""
    a_patterns = _like_patterns(concept_a_variants)
    b_patterns = _like_patterns(concept_b_variants)
    if not a_patterns or not b_patterns:
        return []
    rows = await fetch_all(
        conn,
        _SELECT_FIELDS
        + """
        WHERE ch.knowledge_scope_id = %(scope_id)s
          AND d.status = ANY(%(statuses)s)
          AND ch.content ILIKE ANY(%(a_patterns)s)
          AND ch.content ILIKE ANY(%(b_patterns)s)
        ORDER BY ch.page_start NULLS LAST, ch.chunk_index
        LIMIT %(limit)s
        """,
        {
            "scope_id": str(knowledge_scope_id),
            "statuses": _statuses(include_test_candidates),
            "a_patterns": a_patterns,
            "b_patterns": b_patterns,
            "limit": limit,
        },
    )
    for row in rows:
        row["retrieval_methods"] = ["cooccurrence_same_chunk"]
        row["score"] = 0.85
    return rows


async def get_chunks_by_ids(
    conn: AsyncConnection,
    *,
    knowledge_scope_id: UUID,
    chunk_ids: Sequence[str],
    include_test_candidates: bool,
) -> list[dict[str, Any]]:
    """Rehydrate vector candidates from canonical PG rows and enforce scope."""
    if not chunk_ids:
        return []
    return await fetch_all(
        conn,
        _SELECT_FIELDS
        + """
        WHERE ch.knowledge_scope_id = %(scope_id)s
          AND d.status = ANY(%(statuses)s)
          AND ch.id = ANY(%(chunk_ids)s::uuid[])
        """,
        {
            "scope_id": str(knowledge_scope_id),
            "statuses": _statuses(include_test_candidates),
            "chunk_ids": list(chunk_ids),
        },
    )
