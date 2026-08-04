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
    include_test_candidates: bool = False,
) -> list[dict[str, Any]]:
    """Resolve explicit work filters without treating default UI scope as a filter."""
    rows = await fetch_all(
        conn,
        """
        SELECT d.id AS document_id, d.document_code, d.title, d.language,
               d.source_filename, d.source_sha256, d.status, d.edition,
               d.metadata, d.bibliographic_metadata
        FROM library_documents d
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        WHERE ks.knowledge_scope_code = %(scope)s
          AND (
                d.status = 'ready'
                OR (%(include_test)s AND d.status = 'test_candidate')
          )
        ORDER BY d.title
        """,
        {"scope": knowledge_scope_code, "include_test": include_test_candidates},
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
        if any(alias.casefold() in str(row.get("title") or "").casefold() for alias in wanted)
        or (
            "lmi" in work_codes
            and row.get("document_code") == "likutey_moharan_ii_spanish_bri"
        )
    ]


async def search_structural_heading_candidates(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    normalized_query: str,
    accent_folded_query: str,
    hebrew_query: bool,
    languages: list[str],
    document_ids: list[str] | None,
    top_k: int,
    include_test_candidates: bool = False,
) -> list[dict[str, Any]]:
    """Return a bounded set of existing title/heading fields for Python classification.

    Indexed normalized text covers ordinary chunks. The short-null branch is limited
    to compact layout blocks from DEV test candidates whose ingestion predates
    ``search_text_normalized``.
    """
    return await fetch_all(
        conn,
        """
        SELECT
            ch.id AS chunk_id,
            ch.document_id,
            ch.chunk_index,
            ch.content,
            ch.section_title,
            ch.block_type,
            ch.evidence_role,
            ch.citable,
            ch.page_start,
            ch.page_end,
            ch.printed_page_label,
            ch.search_text_normalized,
            d.status AS document_status,
            body.id AS associated_chunk_id
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        LEFT JOIN LATERAL (
            SELECT candidate.id
            FROM library_document_chunks candidate
            WHERE candidate.document_id = ch.document_id
              AND candidate.chunk_index > ch.chunk_index
              AND candidate.page_start = ch.page_start
              AND candidate.citable = true
              AND length(trim(candidate.content)) >= 40
              AND (
                    ch.block_type IS NULL
                    OR candidate.block_type = ch.block_type
                    OR ch.section_title IS NOT NULL
              )
            ORDER BY candidate.chunk_index
            LIMIT 1
        ) body ON true
        WHERE ks.knowledge_scope_code = %(scope)s
          AND (
                d.status = 'ready'
                OR (%(include_test)s AND d.status = 'test_candidate')
          )
          AND ch.language = ANY(%(languages)s::text[])
          AND (
                %(document_ids)s::uuid[] IS NULL
                OR ch.document_id = ANY(%(document_ids)s::uuid[])
          )
          AND (
                lower(coalesce(ch.section_title, ''))
                    LIKE '%%' || %(normalized_query)s || '%%'
                OR public.unaccent(lower(coalesce(ch.section_title, '')))
                    LIKE '%%' || %(query)s || '%%'
                OR (
                    %(hebrew_query)s
                    AND lower(ch.content) LIKE '%%' || %(normalized_query)s || '%%'
                )
                OR ch.search_text_normalized ILIKE '%%' || %(query)s || '%%'
                OR (
                    %(include_test)s
                    AND d.status = 'test_candidate'
                    AND ch.search_text_normalized IS NULL
                    AND length(ch.content) <= 320
                    AND public.unaccent(lower(ch.content))
                        LIKE '%%' || %(query)s || '%%'
                )
          )
        ORDER BY
            CASE
                WHEN lower(coalesce(ch.section_title, '')) = %(normalized_query)s
                    OR public.unaccent(lower(coalesce(ch.section_title, ''))) = %(query)s
                    THEN 0
                WHEN (
                        %(hebrew_query)s
                        AND lower(ch.content) LIKE '%%' || %(normalized_query)s || '%%'
                    )
                    OR public.unaccent(lower(ch.content)) LIKE '%%' || %(query)s || '%%'
                    THEN 1
                ELSE 2
            END,
            length(ch.content),
            ch.document_id,
            ch.chunk_index,
            ch.id
        LIMIT %(limit)s
        """,
        {
            "scope": knowledge_scope_code,
            "normalized_query": normalized_query,
            "query": accent_folded_query,
            "hebrew_query": hebrew_query,
            "languages": languages,
            "document_ids": document_ids or None,
            "include_test": include_test_candidates,
            "limit": top_k,
        },
    )


async def search_printed_reference_candidates(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    reference_variants: list[str],
    languages: list[str],
    document_ids: list[str] | None,
    include_test_candidates: bool = False,
) -> list[dict[str, Any]]:
    """Search for marginal_source chunks matching a printed biblical reference."""
    if not reference_variants:
        return []
    # Use the reference regex to extract book, chapter, verse for precise matching
    from modules.library.editorial_evidence_v2 import _BIBLICAL_REFERENCE
    import re as _re
    # Build variants as regex patterns with exact verse boundaries.  A query
    # verse must never be a prefix of a longer verse: "16:1" must not match
    # "16:10" or "16:11", and "116:1" is a different chapter entirely.
    pg_re_variants = []
    ilike_variants = []
    for v in reference_variants:
        m = _BIBLICAL_REFERENCE.search(v)
        if m:
            book = _re.escape(m.group(1))
            chapter = _re.escape(m.group(2))
            verse = _re.escape(m.group(3))
            # Build regex that handles optional 's' suffix for book names
            # e.g. Salmo -> (?:Salmo|Salmos), Proverbio -> (?:Proverbio|Proverbios)
            book_pluralized = book
            if not book.endswith('s'):
                # If book is singular, also match the plural form
                book_singular = book.rstrip('s')
                book_pluralized = f'(?:{book}{book}s?)' if book != book_singular else f'(?:{book}{book}s)?'
                # Simplify: just match with and without trailing 's'
                book_pluralized = f'{book}s?'
            # Match the exact book chapter:verse surface.  The trailing
            # guard excludes longer verses (16:10, 16:11) and a following
            # hyphenated range.  The leading guard excludes 116:1 when the
            # query is 16:1, and vice versa.
            pg_re = (
                r'(?i)(?<![\d:])' + book_pluralized + r'\s+' + chapter + r':' + verse
                + r'(?![\d])'
                + r'(?:[^\w]|$)'
            )
            pg_re_variants.append(pg_re)
            # Also add a simple ILIKE variant for backup
            # Use the original reference text without parentheses
            clean_ref = v.strip('()[]')
            ilike_variants.append(clean_ref)
    if not pg_re_variants:
        return []
    return await fetch_all(
        conn,
        """
        WITH ref AS (
            SELECT DISTINCT trim(value) AS query
            FROM unnest(%(variants)s::text[]) AS values(value)
            WHERE length(trim(value)) >= 2
        )
        SELECT DISTINCT ON (ch.id, ref.query)
            ch.id AS chunk_id,
            ch.document_id,
            ch.chunk_index,
            ch.content,
            ch.block_type,
            ch.evidence_role,
            ch.citable,
            ch.page_start,
            ch.page_end,
            ch.printed_page_label,
            ch.section_title,
            d.status AS document_status,
            true AS exact_match,
            2 AS exact_variant_count
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        CROSS JOIN ref
        WHERE ks.knowledge_scope_code = %(scope)s
          AND (
                d.status = 'ready'
                OR (%(include_test)s AND d.status = 'test_candidate')
          )
          AND ch.citable = true
          AND (
                ch.evidence_role = 'marginal_citation'
                OR ch.block_type = 'marginal_source'
          )
          AND (
                ch.language = ANY(%(languages)s::text[])
                OR ch.language = 'mixed'
          )
          AND (
                %(document_ids)s::uuid[] IS NULL
                OR ch.document_id = ANY(%(document_ids)s::uuid[])
          )
          AND ch.content ~ ref.query
        ORDER BY ch.id, ref.query, ch.document_id, ch.page_start, ch.chunk_index
        LIMIT 30
        """,
        {
            "scope": knowledge_scope_code,
            "variants": pg_re_variants,
            "languages": languages,
            "document_ids": document_ids or None,
            "include_test": include_test_candidates,
        },
    )


async def search_literal_candidates(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    variants: list[str],
    languages: list[str],
    document_ids: list[str] | None,
    top_k: int,
    hebrew_compact: str = "",
    hebrew_fallback_compacts: list[str] | None = None,
    include_test_candidates: bool = False,
) -> list[dict[str, Any]]:
    """Run phrase, FTS and trigram signals over canonical PostgreSQL chunks."""
    chunks = await fetch_all(
        conn,
        r"""
        WITH query_variants AS (
            SELECT
                regexp_replace(
                    regexp_replace(
                        public.unaccent(lower(trim(value))),
                        '(?<=[a-z]) *\([^()\n]{2,120}\)', '', 'g'
                    ),
                    '[[:space:]]+', ' ', 'g'
                ) AS query,
                min(ordinality) AS ordinal
            FROM unnest(%(variants)s::text[]) WITH ORDINALITY AS values(value, ordinality)
            WHERE length(trim(value)) >= 2
            GROUP BY 1
        ),
        normalized_text AS (
            SELECT id,
                   regexp_replace(
                       regexp_replace(
                           public.unaccent(lower(coalesce(search_text_normalized, content))),
                           '(?<=[a-z]) *\([^()\n]{2,120}\)', '', 'g'
                       ),
                       '[[:space:]]+', ' ', 'g'
                   ) AS norm_text
            FROM library_document_chunks
        ),
        scored AS (
            SELECT
                ch.id AS chunk_id,
                ch.block_type,
                ch.evidence_role,
                ch.content,
                bool_or(
                    nt.norm_text LIKE '%%' || q.query || '%%'
                ) AS exact_match,
                count(DISTINCT q.query) FILTER (
                    WHERE nt.norm_text LIKE '%%' || q.query || '%%'
                ) AS exact_variant_count,
                (
                    array_agg(q.query ORDER BY q.ordinal) FILTER (
                        WHERE nt.norm_text LIKE '%%' || q.query || '%%'
                    )
                )[1] AS matched_variant,
                min(q.ordinal) FILTER (
                    WHERE nt.norm_text LIKE '%%' || q.query || '%%'
                ) AS matched_variant_ordinal,
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
                max(
                    COALESCE(
                        similarity(ch.search_text_normalized, q.query),
                        similarity(ch.content, q.query)
                    )
                ) FILTER (WHERE q.ordinal <= 2) AS trigram_score
            FROM library_document_chunks ch
            JOIN normalized_text nt ON nt.id = ch.id
            JOIN library_documents d ON d.id = ch.document_id
            JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
            CROSS JOIN query_variants q
            WHERE ks.knowledge_scope_code = %(scope)s
              AND (
                    d.status = 'ready'
                    OR (%(include_test)s AND d.status = 'test_candidate')
              )
              AND ch.citable = true
              AND ch.language = ANY(%(languages)s::text[])
              AND (
                    %(document_ids)s::uuid[] IS NULL
                    OR ch.document_id = ANY(%(document_ids)s::uuid[])
              )
              AND (
                    (
                        nt.norm_text LIKE '%%' || q.query || '%%'
                    )
                    OR ch.search_vector_es @@ websearch_to_tsquery('spanish', q.query)
                    OR ch.search_vector_simple @@ websearch_to_tsquery('simple', q.query)
                    OR (
                        q.ordinal <= 2
                        AND COALESCE(
                            similarity(ch.search_text_normalized, q.query),
                            similarity(ch.content, q.query)
                        ) > 0.12
                    )
              )
            GROUP BY ch.id
        )
        SELECT
            chunk_id,
            block_type,
            evidence_role,
            content,
            exact_match,
            exact_variant_count,
            matched_variant,
            matched_variant_ordinal,
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
            "include_test": include_test_candidates,
            "limit": top_k,
        },
    )
    if not hebrew_compact or not include_test_candidates:
        return chunks
    nodes = await fetch_all(
        conn,
        """
        SELECT
            n.content_node_id AS chunk_id,
            (
                regexp_replace(n.literal_text, '[^א-ת]', '', 'g')
                LIKE '%%' || %(compact)s || '%%'
            ) AS exact_match,
            1 AS exact_variant_count,
            0.0::real AS fts_score,
            0.0::real AS trigram_score,
            CASE
                WHEN regexp_replace(n.literal_text, '[^א-ת]', '', 'g')
                    LIKE '%%' || %(compact)s || '%%'
                    THEN 100.0
                ELSE 60.0
            END::real AS literal_score,
            CASE
                WHEN regexp_replace(n.literal_text, '[^א-ת]', '', 'g')
                    LIKE '%%' || %(compact)s || '%%'
                    THEN 'hebrew_exact_normalized'
                ELSE 'hebrew_bigram'
            END::text AS literal_match_type,
            'content_node'::text AS search_record_type
        FROM library_content_nodes_v2 n
        JOIN library_content_units_v2 u
          ON u.content_unit_id = n.content_unit_id
        JOIN library_documents d
          ON d.id = u.document_id
        JOIN knowledge_scopes ks
          ON ks.id = d.knowledge_scope_id
        WHERE ks.knowledge_scope_code = %(scope)s
          AND d.status = 'test_candidate'
          AND n.citable = true
          AND (
                %(document_ids)s::uuid[] IS NULL
                OR d.id = ANY(%(document_ids)s::uuid[])
          )
          AND regexp_replace(n.literal_text, '[^א-ת]', '', 'g')
              LIKE ANY(%(patterns)s::text[])
        ORDER BY
            CASE
                WHEN regexp_replace(n.literal_text, '[^א-ת]', '', 'g')
                    LIKE '%%' || %(compact)s || '%%' THEN 0
                ELSE 1
            END,
            CASE WHEN n.node_role = 'primary' THEN 0 ELSE 1 END,
            n.content_node_id
        LIMIT %(limit)s
        """,
        {
            "scope": knowledge_scope_code,
            "document_ids": document_ids or None,
            "compact": hebrew_compact,
            "patterns": [
                f"%{value}%"
                for value in dict.fromkeys([
                    hebrew_compact,
                    *(hebrew_fallback_compacts or []),
                ])
                if value
            ],
            "limit": top_k,
        },
    )
    return [*nodes, *chunks][:top_k]


async def search_source_lesson_candidates(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    source_work_code: str,
    lesson_number: int,
    document_ids: list[str],
    top_k: int = 12,
) -> list[dict[str, Any]]:
    """Return original-work nodes for an explicitly requested source lesson.

    This structural lane uses persisted unit references, never title tokens or
    AI classification. Commentary documents are retrieved through their
    explicit source identities in the ordinary lexical/vector lanes.
    """
    canonical_prefixes = {"likutey_moharan_ii": "LMII"}
    prefix = canonical_prefixes.get(source_work_code)
    if not prefix or not document_ids:
        return []
    return await fetch_all(
        conn,
        """
        SELECT DISTINCT ON (u.canonical_ref)
            n.content_node_id AS chunk_id,
            n.content_type AS block_type,
            n.node_role AS evidence_role,
            n.literal_text AS content,
            true AS exact_match,
            1 AS exact_variant_count,
            u.canonical_ref AS matched_variant,
            0 AS matched_variant_ordinal,
            1.0::float AS fts_score,
            1.0::float AS trigram_score,
            4.0::float AS literal_score,
            'source_lesson_exact'::text AS literal_match_type
        FROM library_content_units_v2 u
        JOIN library_content_nodes_v2 n ON n.content_unit_id=u.content_unit_id
        JOIN library_documents d ON d.id=u.document_id
        JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
        WHERE ks.knowledge_scope_code=%(scope)s
          AND d.id=ANY(%(document_ids)s::uuid[])
          AND d.status IN ('ready', 'test_candidate')
          AND n.citable=true
          AND u.canonical_ref LIKE %(reference)s
        ORDER BY u.canonical_ref, n.node_order, n.content_node_id
        LIMIT %(limit)s
        """,
        {
            "scope": knowledge_scope_code,
            "document_ids": document_ids,
            "reference": f"{prefix} {lesson_number}:%",
            "limit": top_k,
        },
    )


async def fetch_canonical_chunks(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str,
    chunk_ids: list[str],
    include_test_candidates: bool = False,
) -> list[dict[str, Any]]:
    """Rehydrate selected IDs from PostgreSQL, including complete canonical Markdown."""
    if not chunk_ids:
        return []
    chunks = await fetch_all(
        conn,
        """
        SELECT
            ch.id AS chunk_id,
            ch.document_id,
            d.document_code,
            coalesce(
                (
                    SELECT canonical_document.title
                    FROM library_documents canonical_document
                    WHERE canonical_document.source_sha256 = d.source_sha256
                      AND (
                            canonical_document.status = 'ready'
                            OR canonical_document.document_code IS NOT NULL
                      )
                    ORDER BY
                        CASE WHEN canonical_document.status = 'ready' THEN 0 ELSE 1 END,
                        CASE WHEN canonical_document.document_code IS NOT NULL THEN 0 ELSE 1 END,
                        canonical_document.created_at DESC
                    LIMIT 1
                ),
                d.title
            ) AS work,
            d.author,
            d.source_filename AS physical_file_name,
            d.source_sha256,
            d.canonical_text_role,
            d.status AS document_status,
            d.edition,
            d.metadata AS document_metadata,
            d.bibliographic_metadata AS document_bibliographic_metadata,
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
          AND (
                d.status = 'ready'
                OR (%(include_test)s AND d.status = 'test_candidate')
          )
          AND ch.citable = true
          AND ch.id = ANY(%(chunk_ids)s::uuid[])
        """,
        {
            "scope": knowledge_scope_code,
            "chunk_ids": chunk_ids,
            "include_test": include_test_candidates,
        },
    )
    if not include_test_candidates:
        return chunks
    nodes = await fetch_all(
        conn,
        """
        SELECT
            n.content_node_id AS chunk_id,
            n.content_node_id AS content_node_id,
            n.page_anchor_id,
            d.id AS document_id,
            d.document_code,
            CASE
                -- This source is physical volume 2 (lessons 7-16) of part I.
                WHEN d.document_code = 'likutey_moharan_ii_spanish_bri'
                    THEN 'Likutey Moharán I'
                ELSE d.title
            END AS work,
            d.author,
            d.source_filename AS physical_file_name,
            d.source_sha256,
            d.canonical_text_role,
            d.status AS document_status,
            d.edition,
            d.metadata AS document_metadata,
            d.bibliographic_metadata AS document_bibliographic_metadata,
            n.language,
            n.literal_text AS markdown,
            n.literal_hash AS content_sha256,
            p.pdf_page_number AS pdf_page,
            p.pdf_page_number AS pdf_page_end,
            p.printed_page_number::text AS printed_page,
            coalesce(
                'Torá ' || substring(u.canonical_ref from '([0-9]+:[0-9]+)'),
                'Torá ' || substring(
                    n.literal_text
                    from 'LIKUTEY MOHAR[ÁA]N[[:space:]]*#([0-9]+:[0-9]+)'
                ),
                u.title,
                u.canonical_ref
            ) AS section,
            u.canonical_ref AS reference_label,
            n.content_type AS block_type,
            n.node_role AS evidence_role,
            n.citable,
            n.metadata_json AS metadata,
            '{}'::jsonb AS bibliographic_metadata,
            'content_node'::text AS search_record_type,
            n.authority_level
        FROM library_content_nodes_v2 n
        JOIN library_content_units_v2 u
          ON u.content_unit_id = n.content_unit_id
        JOIN library_documents d
          ON d.id = u.document_id
        JOIN knowledge_scopes ks
          ON ks.id = d.knowledge_scope_id
        LEFT JOIN library_page_anchors_v2 p
          ON p.page_anchor_id = n.page_anchor_id
        WHERE ks.knowledge_scope_code = %(scope)s
          AND d.status = 'test_candidate'
          AND n.citable = true
          AND n.content_node_id = ANY(%(chunk_ids)s::uuid[])
        """,
        {"scope": knowledge_scope_code, "chunk_ids": chunk_ids},
    )
    return [*chunks, *nodes]


async def fetch_preceding_section_title(
    conn: Any,
    *,
    document_id: str,
    pdf_page: int,
) -> str | None:
    """Return the preceding canonical section for a cross-page footnote."""
    rows = await fetch_all(
        conn,
        """
        SELECT section_title
        FROM library_document_chunks
        WHERE document_id = %(document_id)s
          AND page_start < %(pdf_page)s
          AND coalesce(section_title, '') <> ''
        ORDER BY page_start DESC, chunk_index DESC
        LIMIT 1
        """,
        {"document_id": document_id, "pdf_page": pdf_page},
    )
    return str(rows[0]["section_title"]).strip() if rows else None
