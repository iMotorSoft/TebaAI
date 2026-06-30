"""Hybrid search combining PostgreSQL FTS and Milvus vector search."""

from __future__ import annotations

import html
from typing import Any

from psycopg import AsyncConnection

from infrastructure.milvus.client import ensure_collection, search_vectors
from infrastructure.postgres.transaction import fetch_all, fetch_one
from modules.embeddings.client import embed_text
from modules.library.text_search import search_chunks_text

HYBRID_WEIGHTS = {
    "fts_coeff": 0.55,
    "vector_coeff": 0.45,
    "fts_only_coeff": 0.70,
    "vector_only_coeff": 0.45,
    "phrase_bonus": 0.10,
}

FTS_LIMIT = 30
VECTOR_LIMIT = 30


# @lat: [[library-retrieval-models-policy#Hybrid Search]]
async def search_chunks_hybrid(
    conn: AsyncConnection,
    collection_code: str,
    query: str,
    top_k: int = 10,
    language: str = "es",
    fts_limit: int = FTS_LIMIT,
    vector_limit: int = VECTOR_LIMIT,
    milvus_collection: str = "tebaai_breslov_chunks_v1",
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    w = weights or HYBRID_WEIGHTS

    # 1. FTS search
    fts_results = await search_chunks_text(
        conn,
        collection_code=collection_code,
        query=query,
        top_k=fts_limit,
        mode="auto",
        language=language,
    )
    fts_by_chunk: dict[str, dict] = {}
    for r in fts_results:
        cid = str(r["chunk_id"])
        r["_source"] = "fts"
        r["_fts_rank"] = r.get("rank", 0.0) or 0.0
        r["_vector_score"] = None
        fts_by_chunk[cid] = r

    # 2. Vector search
    try:
        from infrastructure.milvus.client import create_connection
        create_connection()
        query_vec = embed_text(query)
        ensure_collection(milvus_collection, dimension=len(query_vec))
        milvus_hits = search_vectors(
            collection_name=milvus_collection,
            query_embedding=query_vec,
            top_k=vector_limit,
            expr=f'collection_code == "{collection_code}"',
            output_fields=["chunk_id", "document_id", "title", "content_preview", "chunk_index", "content_sha256",
                           "page_start", "page_end"],
        )
    except Exception:
        milvus_hits = []

    # Enrich Milvus results from PostgreSQL
    vec_by_chunk: dict[str, dict] = {}
    for hit in milvus_hits:
        cid = hit.get("chunk_id", "")
        if not cid:
            continue
        vec_score = hit.get("distance", 0.0) or 0.0
        pg_data = await _enrich_chunk(conn, cid, collection_code)
        entry: dict[str, Any] = {
            "chunk_id": cid,
            "document_id": pg_data.get("document_id") or hit.get("document_id", ""),
            "document_title": pg_data.get("document_title") or hit.get("title", ""),
            "author": pg_data.get("author"),
            "collection_code": collection_code,
            "chunk_index": pg_data.get("chunk_index") or hit.get("chunk_index", 0),
            "language": pg_data.get("language", language),
            "page_start": pg_data.get("page_start"),
            "page_end": pg_data.get("page_end"),
            "chapter": pg_data.get("chapter"),
            "section": pg_data.get("section"),
            "reference_label": pg_data.get("reference_label"),
            "content_length": pg_data.get("content_length", 0),
            "content": pg_data.get("content", ""),
            "_source": "vector",
            "_fts_rank": None,
            "_vector_score": vec_score,
        }
        vec_by_chunk[cid] = entry

    # 3. Merge & dedup
    all_chunks: dict[str, dict] = {}

    for cid, r in fts_by_chunk.items():
        r["source_signals"] = ["fts"]
        r["_hybrid_score"] = r["_fts_rank"] * w["fts_only_coeff"]
        r["match_type"] = "fts"
        all_chunks[cid] = r

    for cid, r in vec_by_chunk.items():
        if cid in all_chunks:
            existing = all_chunks[cid]
            existing["source_signals"] = ["fts", "vector"]
            existing["_vector_score"] = r["_vector_score"]
            # Compute hybrid score
            n_fts = _normalize(existing["_fts_rank"])
            n_vec = _normalize(existing["_vector_score"])
            score = n_fts * w["fts_coeff"] + n_vec * w["vector_coeff"]
            # Phrase bonus if highlighted_excerpt has <mark>
            if "<mark>" in (existing.get("highlighted_excerpt") or ""):
                score += w["phrase_bonus"]
            existing["_hybrid_score"] = score
            existing["match_type"] = "hybrid"
            # Preserve FTS highlight
        else:
            r["source_signals"] = ["vector"]
            r["match_type"] = "vector"
            r["_hybrid_score"] = r["_vector_score"] * w["vector_only_coeff"]
            r["_fts_rank"] = None
            # Generate plain excerpt from content
            content = r.get("content", "")
            r["plain_excerpt"] = content[:300]
            r["highlighted_excerpt"] = _simple_highlight(content, query)
            all_chunks[cid] = r

    # 4. Sort by hybrid score descending
    sorted_chunks = sorted(all_chunks.values(), key=lambda x: x.get("_hybrid_score", 0) or 0, reverse=True)

    # 5. Build final results
    results = []
    for r in sorted_chunks[:top_k]:
        results.append({
            "document_id": r.get("document_id", ""),
            "document_title": r.get("document_title", ""),
            "author": r.get("author"),
            "collection_code": r.get("collection_code", collection_code),
            "chunk_id": r.get("chunk_id", ""),
            "chunk_index": r.get("chunk_index", 0),
            "language": r.get("language", language),
            "page_start": r.get("page_start"),
            "page_end": r.get("page_end"),
            "chapter": r.get("chapter"),
            "section": r.get("section"),
            "reference_label": r.get("reference_label"),
            "match_type": r.get("match_type", "hybrid"),
            "rank": round(r.get("_hybrid_score", 0) or 0, 4),
            "fts_rank": round(r["_fts_rank"], 4) if r.get("_fts_rank") is not None else None,
            "vector_score": round(r["_vector_score"], 4) if r.get("_vector_score") is not None else None,
            "hybrid_score": round(r.get("_hybrid_score", 0) or 0, 4),
            "source_signals": r.get("source_signals", []),
            "plain_excerpt": r.get("plain_excerpt"),
            "highlighted_excerpt": r.get("highlighted_excerpt", ""),
            "content_length": r.get("content_length", 0),
        })

    return results


async def _enrich_chunk(conn: AsyncConnection, chunk_id: str, collection_code: str) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        """
        SELECT d.id AS document_id, d.title AS document_title, d.author,
               c.code AS collection_code, ch.chunk_index, ch.language,
               ch.page_start, ch.page_end, ch.chapter, ch.section,
               ch.reference_label, ch.content, ch.content_length
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        JOIN library_collections c ON c.id = ch.collection_id
        WHERE ch.id = %(chunk_id)s AND c.code = %(code)s
        """,
        {"chunk_id": chunk_id, "code": collection_code},
    )
    if row:
        return dict(row)
    return {}


def _normalize(val: float | None) -> float:
    if val is None:
        return 0.0
    # Simple sigmoid-like normalization for FTS rank (0-1 range roughly)
    return min(1.0, max(0.0, val / 3.0))


def _simple_highlight(content: str, query: str) -> str:
    """Generate simple highlighted excerpt for vector-only results."""
    if not content or not query:
        return html.escape(content[:300]) if content else ""
    norm_content = content.lower()
    norm_query = query.lower().strip()
    pos = norm_content.find(norm_query)
    if pos == -1:
        # Try first word
        first_word = norm_query.split()[0] if norm_query else ""
        if first_word:
            pos = norm_content.find(first_word)
    if pos == -1:
        return html.escape(content[:300])
    start = max(0, pos - 100)
    end = min(len(content), pos + len(query) + 150)
    excerpt = content[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    # Highlight
    local_pos = pos - start
    before = html.escape(excerpt[:local_pos])
    matched = html.escape(excerpt[local_pos:local_pos + len(query)])
    after = html.escape(excerpt[local_pos + len(query):])
    return f"{prefix}{before}<mark>{matched}</mark>{after}{suffix}"
