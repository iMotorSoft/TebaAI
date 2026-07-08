#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Generate 20 embeddings per ES/EN document via LiteLLM for Milvus test."""

from __future__ import annotations

import asyncio, json, logging, sys
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger("es_en_embeddings")

DOCUMENT_PREFIXES = [
    "c7c10741",  # Kokhavey Ohr
    "987bd9d3",  # El Alma del Rebe Najmán
    "76f2adbc",  # El Jardín de las Almas
    "27f175ea",  # KITZUR
    "43ba4f4b",  # La Potencia de la Plegaria
    "56ddcc3b",  # Likutey Halajot LM II 8
]

async def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from modules.embeddings.client import embed_batch
    from globalVar import EMBEDDINGS_MODEL_ALIAS, EMBEDDINGS_DIMENSION
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one
    from modules.library.vector_repository import create_chunk_embedding, create_embedding_run, update_embedding_run

    model = EMBEDDINGS_MODEL_ALIAS
    expected_dim = EMBEDDINGS_DIMENSION
    limit = 20

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            for prefix in DOCUMENT_PREFIXES:
                doc = await fetch_one(conn, """
                    SELECT d.id, d.title, d.language
                    FROM library_documents d
                    WHERE d.id::text LIKE %(pid)s
                """, {"pid": f"{prefix}%"})

                if not doc:
                    print(f"ERROR: document {prefix} not found")
                    continue

                chunks = await fetch_all(conn, """
                    SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256,
                           ch.chunk_index, ch.page_start, ch.page_end
                    FROM library_document_chunks ch
                    WHERE ch.document_id = %(did)s
                      AND NOT EXISTS (
                        SELECT 1 FROM library_chunk_embeddings e
                        WHERE e.chunk_id = ch.id
                      )
                    ORDER BY ch.chunk_index
                    LIMIT %(limit)s
                """, {"did": str(doc["id"]), "limit": limit})

                if not chunks:
                    print(f"  {prefix}: no unembedded chunks found (already done?)")
                    existing = await fetch_one(conn, """
                        SELECT COUNT(*) as cnt FROM library_chunk_embeddings e
                        JOIN library_document_chunks ch ON ch.id = e.chunk_id
                        WHERE ch.document_id = %(did)s
                    """, {"did": str(doc["id"])})
                    print(f"  existing embeddings for this doc: {existing['cnt'] if existing else 0}")
                    continue

                actual = len(chunks)
                texts = [c["content"][:1800] for c in chunks]
                print(f"  {prefix} ({doc['title'][:40]}): generating {actual} embeddings...")

                embeddings = embed_batch(texts, model=model)

                if not embeddings:
                    print(f"  ERROR: empty embeddings for {prefix}")
                    continue

                actual_dim = len(embeddings[0])
                dim_valid = actual_dim == expected_dim
                print(f"    dimension: {actual_dim} (expected {expected_dim}, valid={dim_valid})")

                if not dim_valid:
                    print(f"    SKIPPING {prefix}: dimension mismatch")
                    continue

                run_id = uuid4()
                await create_embedding_run(conn, {
                    "id": run_id,
                    "collection_code": "breslov_test",
                    "milvus_collection": "tebaai_breslov_test_chunks_v1",
                    "embedding_provider": "litellm",
                    "embedding_model": model,
                    "embedding_dimension": actual_dim,
                    "status": "running",
                    "chunks_total": 0,
                })

                for i, chunk in enumerate(chunks):
                    await create_chunk_embedding(
                        conn,
                        chunk_id=chunk["id"],
                        run_id=run_id,
                        provider="litellm",
                        model=model,
                        dimension=actual_dim,
                        milvus_collection="tebaai_breslov_test_chunks_v1",
                        milvus_pk=chunk["chunk_uid"],
                        content_sha256=chunk["content_sha256"],
                        status="indexed",
                    )

                await update_embedding_run(conn, run_id, "completed",
                    chunks_embedded=len(chunks), chunks_indexed=0)

                print(f"    done: {len(embeddings)} embeddings persisted")
                print(f"    sample vector (first 5): {embeddings[0][:5]}")

        print("\nAll documents processed successfully.")

    finally:
        await close_pool(pool)

if __name__ == "__main__":
    asyncio.run(main())
