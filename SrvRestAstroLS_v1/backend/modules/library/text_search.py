"""Text search over library_document_chunks using PostgreSQL FTS."""

from __future__ import annotations

import html
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from infrastructure.postgres.transaction import fetch_all, fetch_one


SEARCH_MODES = ("auto", "fts", "phrase", "trigram", "hybrid")


# @lat: [[library-retrieval-models-policy#Textual / Literal Search]]
async def search_chunks_text(
    conn: AsyncConnection,
    collection_code: str,
    query: str,
    top_k: int = 10,
    mode: str = "auto",
    language: str = "es",
) -> list[dict[str, Any]]:
    """Search chunks by text across multiple modes."""
    if mode not in SEARCH_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Choose from: {', '.join(SEARCH_MODES)}")

    # Normalize query with unaccent
    conn.row_factory = dict_row
    cur = conn.cursor()
    await cur.execute("SELECT public.unaccent(%s) AS q", (query,))
    norm_q = (await cur.fetchone())["q"]

    if not norm_q or not norm_q.strip():
        return []

    if mode == "auto":
        if " " in norm_q.strip() and len(norm_q.strip()) > 3:
            # Multi-word: try phrase first, fall back to fts
            results = await _search_phrase(conn, collection_code, norm_q, query, top_k)
            if len(results) >= top_k:
                return results
            fts_results = await _search_fts(conn, collection_code, norm_q, query, top_k)
            return _merge(results, fts_results, top_k)
        else:
            return await _search_fts(conn, collection_code, norm_q, query, top_k)
    elif mode == "fts":
        return await _search_fts(conn, collection_code, norm_q, query, top_k)
    elif mode == "phrase":
        return await _search_phrase(conn, collection_code, norm_q, query, top_k)
    elif mode == "trigram":
        return await _search_trigram(conn, collection_code, norm_q, query, top_k)
    return []


async def _search_fts(
    conn: AsyncConnection,
    collection_code: str,
    norm_q: str,
    raw_q: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Full Text Search using tsvector."""
    rows = await fetch_all(
        conn,
        """
        SELECT
            d.id AS document_id, d.title AS document_title, d.author,
            c.code AS collection_code,
            ch.id AS chunk_id, ch.chunk_index, ch.language,
            ch.page_start, ch.page_end, ch.chapter, ch.section, ch.reference_label,
            'fts' AS match_type,
            ts_rank_cd(ch.search_vector_es, plainto_tsquery('spanish', %(norm_q)s)) AS rank_es,
            ts_rank_cd(ch.search_vector_simple, plainto_tsquery('simple', %(norm_q)s)) AS rank_simple,
            ch.content, ch.content_length
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        JOIN library_collections c ON c.id = ch.collection_id
        WHERE c.code = %(code)s
          AND (
              ch.search_vector_es @@ plainto_tsquery('spanish', %(norm_q)s)
              OR ch.search_vector_simple @@ plainto_tsquery('simple', %(norm_q)s)
          )
        ORDER BY rank_es DESC, rank_simple DESC
        LIMIT %(limit)s
        """,
        {"code": collection_code, "norm_q": norm_q, "limit": top_k},
    )
    return [_build_result(r, raw_q, "fts") for r in rows]


async def _search_phrase(
    conn: AsyncConnection,
    collection_code: str,
    norm_q: str,
    raw_q: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Exact phrase search using ILIKE on normalized text."""
    like_pattern = f"%{norm_q}%"
    rows = await fetch_all(
        conn,
        """
        SELECT
            d.id AS document_id, d.title AS document_title, d.author,
            c.code AS collection_code,
            ch.id AS chunk_id, ch.chunk_index, ch.language,
            ch.page_start, ch.page_end, ch.chapter, ch.section, ch.reference_label,
            'phrase' AS match_type,
            POSITION(%(norm_q)s IN ch.search_text_normalized) AS pos,
            ch.content, ch.content_length
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        JOIN library_collections c ON c.id = ch.collection_id
        WHERE c.code = %(code)s
          AND ch.search_text_normalized ILIKE %(pattern)s
        ORDER BY POSITION(%(norm_q)s IN ch.search_text_normalized)
        LIMIT %(limit)s
        """,
        {"code": collection_code, "norm_q": norm_q, "pattern": like_pattern, "limit": top_k},
    )
    return [_build_result(r, raw_q, "phrase") for r in rows]


async def _search_trigram(
    conn: AsyncConnection,
    collection_code: str,
    norm_q: str,
    raw_q: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Trigram similarity search."""
    rows = await fetch_all(
        conn,
        """
        SELECT
            d.id AS document_id, d.title AS document_title, d.author,
            c.code AS collection_code,
            ch.id AS chunk_id, ch.chunk_index, ch.language,
            ch.page_start, ch.page_end, ch.chapter, ch.section, ch.reference_label,
            'trigram' AS match_type,
            similarity(ch.search_text_normalized, %(norm_q)s) AS sim,
            ch.content, ch.content_length
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        JOIN library_collections c ON c.id = ch.collection_id
        WHERE c.code = %(code)s
          AND similarity(ch.search_text_normalized, %(norm_q)s) > 0.1
        ORDER BY sim DESC
        LIMIT %(limit)s
        """,
        {"code": collection_code, "norm_q": norm_q, "limit": top_k},
    )
    return [_build_result(r, raw_q, "trigram") for r in rows]


def _build_result(row: dict, raw_q: str, match_type: str) -> dict[str, Any]:
    """Build result dict with plain and highlighted excerpts."""
    content: str = row.get("content") or ""
    rank = row.get("rank_es") or row.get("rank_simple") or row.get("sim") or row.get("pos") or 0.0
    if isinstance(rank, int):
        rank = float(rank)

    plain_excerpt, highlighted_excerpt = _make_excerpts(content, raw_q, max_words=45)

    return {
        "document_id": str(row["document_id"]),
        "document_title": row.get("document_title") or "",
        "author": row.get("author"),
        "collection_code": row["collection_code"],
        "chunk_id": str(row["chunk_id"]),
        "chunk_index": row["chunk_index"],
        "language": row.get("language"),
        "page_start": row.get("page_start"),
        "page_end": row.get("page_end"),
        "chapter": row.get("chapter"),
        "section": row.get("section"),
        "reference_label": row.get("reference_label"),
        "match_type": match_type,
        "rank": round(float(rank), 4),
        "plain_excerpt": plain_excerpt,
        "highlighted_excerpt": highlighted_excerpt,
        "content_length": row.get("content_length", len(content)),
    }


def _make_excerpts(content: str, query: str, max_words: int = 45) -> tuple[str, str]:
    """Extract plain and highlighted excerpts from content around query matches."""
    if not content or not query:
        excerpt = content[:300] if content else ""
        return excerpt, excerpt

    norm_content = content.lower()
    norm_query = query.lower().strip()

    # Find all match positions (case-insensitive)
    positions: list[int] = []
    start = 0
    while True:
        pos = norm_content.find(norm_query, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1

    if not positions:
        excerpt = content[:300]
        return excerpt, html.escape(excerpt)

    # Use first match position for excerpt window
    match_pos = positions[0]
    words_before = 15
    words_after = 30

    excerpt_start = 0
    word_count = 0
    i = match_pos - 1
    while i >= 0 and word_count < words_before:
        if content[i] in (" ", "\n"):
            word_count += 1
        i -= 1
    excerpt_start = max(0, i + 1)

    excerpt_end = len(content)
    word_count = 0
    i = match_pos + len(query)
    while i < len(content) and word_count < words_after:
        if content[i] in (" ", "\n"):
            word_count += 1
        i += 1
    excerpt_end = min(len(content), i)

    raw = content[excerpt_start:excerpt_end]
    prefix = "..." if excerpt_start > 0 else ""
    suffix = "..." if excerpt_end < len(content) else ""

    plain = prefix + raw.strip() + suffix

    # Build highlighted: escape raw text first, then insert <mark> tags
    # using position mapping to account for HTML entity length changes
    escaped = html.escape(raw)

    # Build position map: raw index -> escaped byte offset
    pos_map = [0]
    for ch in raw:
        pos_map.append(pos_map[-1] + len(html.escape(ch)))

    # Insert </mark> and <mark> in reverse position order
    hl_chars = list(escaped)
    for idx in reversed(range(len(positions))):
        p = positions[idx] - excerpt_start
        if 0 <= p < len(raw):
            s = pos_map[p]
            e = pos_map[min(p + len(query), len(raw))]
            hl_chars.insert(e, "</mark>")
            hl_chars.insert(s, "<mark>")

    highlighted = prefix + "".join(hl_chars).strip() + suffix

    return plain, highlighted


def _merge(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Merge two result lists, deduplicating by chunk_id, keeping primary order."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for r in primary + secondary:
        cid = r["chunk_id"]
        if cid not in seen:
            seen.add(cid)
            merged.append(r)
            if len(merged) >= top_k:
                break
    return merged
