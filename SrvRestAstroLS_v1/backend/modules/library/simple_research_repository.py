"""PostgreSQL authority for the simple grounded research pipeline."""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from infrastructure.postgres.transaction import fetch_all


async def resolve_ready_documents(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    work_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Resolve explicit work filters without treating default UI scope as a filter."""
    rows = await fetch_all(
        conn,
        """
        SELECT d.id AS document_id, d.document_code, d.title, d.language
        FROM library_documents d
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        WHERE ks.knowledge_scope_code = %(scope)s
          AND d.status = 'ready'
        ORDER BY d.title
        """,
        {"scope": knowledge_scope_code},
    )
    if not work_codes:
        return rows

    aliases = {
        "kitzur": ("kitzur",),
        "lmi": ("likutey moharán i ", "likutey moharan i "),
        "lmii": ("likutey moharán ii", "likutey moharan ii"),
        "lh": ("likutey halajot", "likutey halakhot"),
        "lm_xv": ("likutey moharán xv", "likutey moharan xv"),
        "potencia_plegaria": ("potencia de la plegaria",),
    }
    wanted = {
        alias
        for code in work_codes
        for alias in aliases.get(code, (code.replace("_", " "),))
    }
    return [
        row
        for row in rows
        if any(alias in str(row.get("title") or "").casefold() for alias in wanted)
    ]


async def search_literal_candidates(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    variants: list[str],
    languages: list[str],
    document_ids: list[str] | None,
    top_k: int,
) -> list[dict[str, Any]]:
    """Run phrase, FTS and trigram signals over canonical PostgreSQL chunks."""
    return await fetch_all(
        conn,
        """
        WITH query_variants AS (
            SELECT
                public.unaccent(trim(value)) AS query,
                min(ordinality) AS ordinal
            FROM unnest(%(variants)s::text[]) WITH ORDINALITY AS values(value, ordinality)
            WHERE length(trim(value)) >= 2
            GROUP BY public.unaccent(trim(value))
        ),
        scored AS (
            SELECT
                ch.id AS chunk_id,
                bool_or(ch.search_text_normalized ILIKE '%%' || q.query || '%%') AS exact_match,
                count(DISTINCT q.query) FILTER (
                    WHERE ch.search_text_normalized ILIKE '%%' || q.query || '%%'
                ) AS exact_variant_count,
                max(
                    GREATEST(
                        ts_rank_cd(
                            ch.search_vector_es,
                            websearch_to_tsquery('spanish', q.query)
                        ),
                        ts_rank_cd(
                            ch.search_vector_simple,
                            websearch_to_tsquery('simple', q.query)
                        )
                    )
                ) AS fts_score,
                max(similarity(ch.search_text_normalized, q.query))
                    FILTER (WHERE q.ordinal <= 2) AS trigram_score
            FROM library_document_chunks ch
            JOIN library_documents d ON d.id = ch.document_id
            JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
            CROSS JOIN query_variants q
            WHERE ks.knowledge_scope_code = %(scope)s
              AND d.status = 'ready'
              AND ch.citable = true
              AND ch.language = ANY(%(languages)s::text[])
              AND (
                    %(document_ids)s::uuid[] IS NULL
                    OR ch.document_id = ANY(%(document_ids)s::uuid[])
              )
              AND (
                    ch.search_text_normalized ILIKE '%%' || q.query || '%%'
                    OR ch.search_vector_es @@ websearch_to_tsquery('spanish', q.query)
                    OR ch.search_vector_simple @@ websearch_to_tsquery('simple', q.query)
                    OR (
                        q.ordinal <= 2
                        AND similarity(ch.search_text_normalized, q.query) > 0.12
                    )
              )
            GROUP BY ch.id
        )
        SELECT
            chunk_id,
            exact_match,
            exact_variant_count,
            fts_score,
            trigram_score,
            (
                CASE WHEN exact_match THEN 1.0 ELSE 0.0 END
                + least(exact_variant_count, 5) * 0.20
                + least(coalesce(fts_score, 0.0), 1.0)
                + least(coalesce(trigram_score, 0.0), 1.0)
            ) AS literal_score
        FROM scored
        ORDER BY literal_score DESC, chunk_id
        LIMIT %(limit)s
        """,
        {
            "scope": knowledge_scope_code,
            "variants": variants,
            "languages": languages,
            "document_ids": document_ids or None,
            "limit": top_k,
        },
    )


async def fetch_canonical_chunks(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    chunk_ids: list[str],
) -> list[dict[str, Any]]:
    """Rehydrate selected IDs from PostgreSQL, including complete canonical Markdown."""
    if not chunk_ids:
        return []
    return await fetch_all(
        conn,
        """
        SELECT
            ch.id AS chunk_id,
            ch.document_id,
            d.document_code,
            d.title AS work,
            d.author,
            d.source_filename AS physical_file_name,
            d.source_sha256,
            d.canonical_text_role,
            ch.language,
            ch.content AS markdown,
            ch.content_sha256,
            ch.page_start AS pdf_page,
            ch.page_end AS pdf_page_end,
            ch.printed_page_label AS printed_page,
            coalesce(ch.section_title, ch.section, ch.chapter) AS section,
            ch.reference_label,
            ch.block_type,
            ch.evidence_role,
            ch.citable,
            ch.metadata,
            ch.bibliographic_metadata
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        WHERE ks.knowledge_scope_code = %(scope)s
          AND d.status = 'ready'
          AND ch.citable = true
          AND ch.id = ANY(%(chunk_ids)s::uuid[])
        """,
        {"scope": knowledge_scope_code, "chunk_ids": chunk_ids},
    )
