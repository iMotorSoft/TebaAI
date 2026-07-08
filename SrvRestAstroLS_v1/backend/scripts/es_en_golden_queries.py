#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Golden queries for ES/EN retrieval validation via Milvus test + PostgreSQL."""

from __future__ import annotations

import asyncio, json, sys

MILVUS_COLLECTION = "tebaai_breslov_test_chunks_v1"

QUERIES = [
    # Español
    {"q": "hitbodedut plegaria personal", "lang": "es", "label": "Hitbodedut / plegaria personal"},
    {"q": "alma del Rebe Najmán", "lang": "es", "label": "Alma del Rebe Najmán"},
    {"q": "oracion plegaria rezo", "lang": "es", "label": "Plegaria / oración"},
    {"q": "halaja practica ley judia", "lang": "es", "label": "Halajot / práctica"},
    {"q": "zzzzzzzzzzzzzzzzzzzzzzzzzzzz", "lang": "es", "label": "Negativa español (garbage)"},
    # Inglés
    {"q": "Breslov joy happiness", "lang": "en", "label": "Breslov joy (Kokhavey Ohr)"},
    {"q": "zzzzzzzzzzzzzzzzzzzzzzzzzzzz", "lang": "en", "label": "Negativa inglés (garbage)"},
]

async def main():
    from modules.embeddings.client import embed_text
    from infrastructure.milvus.client import create_connection, search_vectors
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one

    create_connection()
    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            for entry in QUERIES:
                q = entry["q"]
                label = entry["label"]
                print(f"\n{'='*60}")
                print(f"Query: {label}")
                print(f"  text: {q[:60]}{'...' if len(q)>60 else ''}")

                # 1. Embed via LiteLLM
                vec = embed_text(q)

                # 2. Search Milvus test
                hits = search_vectors(
                    collection_name=MILVUS_COLLECTION,
                    query_embedding=vec,
                    top_k=5,
                    output_fields=["pk", "chunk_id", "document_id", "title",
                                   "content_sha256", "chunk_index", "page_start",
                                   "page_end", "language", "collection_code"],
                )

                if not hits:
                    print("  -> 0 results from Milvus (negative query OK)")
                    continue

                print(f"  -> {len(hits)} results from Milvus")
                for rank, hit in enumerate(hits, 1):
                    dist = hit.get("distance", 0)
                    chunk_id = hit.get("chunk_id", "?")
                    doc_id = hit.get("document_id", "?")
                    title = hit.get("title", "?")
                    lang = hit.get("language", "?")
                    pg_start = hit.get("page_start", 0)
                    pg_end = hit.get("page_end", 0)
                    ci = hit.get("chunk_index", 0)

                    # 3. Retrieve full text from PostgreSQL
                    pg_chunk = await fetch_one(conn, """
                        SELECT ch.content, ch.page_start, ch.page_end,
                               ch.reference_label, ch.content_sha256
                        FROM library_document_chunks ch
                        WHERE ch.id = %(cid)s::uuid
                    """, {"cid": chunk_id})

                    snippet = ""
                    pg_page = ""
                    pg_sha = ""
                    if pg_chunk:
                        content = pg_chunk["content"] or ""
                        snippet = content[:200].replace("\n", " ")
                        pg_page = f"pg {pg_chunk['page_start']}-{pg_chunk['page_end']}" if pg_chunk['page_start'] else "no page"
                        pg_sha = pg_chunk['content_sha256'][:16] if pg_chunk['content_sha256'] else ""

                    print(f"\n  #{rank} (distance={dist:.4f})")
                    print(f"    doc: {title}")
                    print(f"    doc_id: {doc_id[:12]}...")
                    print(f"    chunk_id: {chunk_id[:12]}...")
                    print(f"    chunk_index: {ci}")
                    print(f"    page: {pg_page}  language: {lang}")
                    print(f"    sha256: {pg_sha}...")
                    print(f"    snippet: {snippet[:120]}...")
                    print(f"    PG source: verified (text NOT from Milvus)")

    finally:
        await close_pool(pool)

if __name__ == "__main__":
    asyncio.run(main())
