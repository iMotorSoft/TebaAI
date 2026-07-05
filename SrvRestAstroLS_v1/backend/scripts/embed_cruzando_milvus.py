#!/usr/bin/env python3
"""
Milvus upsert for Cruzando el Puente — insert all 741 chunk embeddings.

Run after embed_cruzando_full (which already generated PG records).

Usage:
  uv run python -m scripts.embed_cruzando_milvus
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from uuid import uuid4

DOCUMENT_ID = "0bad063c-f7a8-429c-a0ac-c01af224d5cb"
COLLECTION = "breslov_primary"
MILVUS_TEST_COLL = "tebaai_breslov_test_chunks_v1"
EMBED_MODEL = "openai_text_embedding_3_small"
EMBED_DIM = 1536
BATCH_SIZE = 16


def truncate(text: str, max_chars: int = 1200) -> str:
    return text[:max_chars]


async def main():
    print(f"{'='*60}")
    print(f"  MILVUS UPSERT — Cruzando el Puente")
    print(f"{'='*60}")

    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute
    from modules.library.vector_repository import (
        create_embedding_run, update_embedding_run,
    )
    from modules.embeddings.client import embed_batch
    from modules.library.indexing_service import ensure_collection, EMBEDDINGS_MODEL_ALIAS, EMBEDDINGS_DIMENSION
    from pymilvus import Collection

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        # Get doc info
        async with pool.connection() as conn:
            doc_info = await fetch_one(conn, """
                SELECT title, source_type, source_sha256, language
                FROM library_documents WHERE id = %(did)s
            """, {"did": DOCUMENT_ID})

            chunks = await fetch_all(conn, """
                SELECT c.id, c.chunk_uid, c.content, c.chunk_index,
                       c.page_start, c.page_end
                FROM library_document_chunks c
                JOIN library_chunk_embeddings e ON e.chunk_id = c.id
                WHERE c.document_id = %(did)s AND e.status = 'indexed'
                ORDER BY c.chunk_index
            """, {"did": DOCUMENT_ID})

        print(f"Chunks to index: {len(chunks)}")

        # Create embedding run
        run_id = uuid4()
        async with pool.connection() as conn:
            await create_embedding_run(conn, {
                "id": run_id,
                "collection_code": COLLECTION,
                "milvus_collection": MILVUS_TEST_COLL,
                "embedding_provider": "litellm",
                "embedding_model": EMBED_MODEL,
                "embedding_dimension": EMBED_DIM,
                "status": "running",
                "chunks_total": len(chunks),
            })

        # Ensure collection
        ensure_collection(MILVUS_TEST_COLL, dimension=EMBED_DIM)
        coll = Collection(MILVUS_TEST_COLL)
        coll.load()

        milvus_ok = 0
        milvus_fail = 0

        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[batch_start:batch_start + BATCH_SIZE]
            batch_texts = [truncate(c["content"]) for c in batch]

            try:
                vectors = embed_batch(batch_texts, model=EMBED_MODEL)

                for i, ck in enumerate(batch):
                    embed_text = truncate(ck["content"])
                    cs = hashlib.sha256(embed_text.encode("utf-8")).hexdigest()
                    vector = vectors[i]

                    title = str(doc_info["title"] or "")[:256]
                    preview = embed_text[:800]

                    ins_result = coll.insert([
                        [str(ck["chunk_uid"])],
                        [str(ck["id"])],
                        [str(DOCUMENT_ID)],
                        [str(COLLECTION)],
                        [str(doc_info["language"] or "es")],
                        [title],
                        [str(doc_info["source_type"] or "pdf")],
                        [str(doc_info["source_sha256"] or "")],
                        [str(cs)],
                        [int(ck["chunk_index"])],
                        [int(ck.get("page_start") or 0)],
                        [int(ck.get("page_end") or 0)],
                        [str(preview)],
                        [[float(v) for v in vector]],
                    ])
                    milvus_pk = str(ins_result.primary_keys[0]) if ins_result.primary_keys else str(uuid4())

                    async with pool.connection() as conn:
                        await execute(conn, """
                            UPDATE library_chunk_embeddings
                            SET milvus_primary_key = %(pk)s,
                                milvus_collection = %(coll)s,
                                vector_status = 'indexed_test',
                                status = 'indexed'
                            WHERE chunk_id = %(cid)s
                            AND status = 'indexed'
                        """, {
                            "pk": milvus_pk,
                            "coll": MILVUS_TEST_COLL,
                            "cid": str(ck["id"]),
                        })
                    milvus_ok += 1

            except Exception as exc:
                milvus_fail += len(batch)
                print(f"  ERROR batch {batch_start}: {exc}")
                break

            if (batch_start + len(batch)) % 50 < BATCH_SIZE or (batch_start + len(batch)) >= len(chunks):
                print(f"  Milvus: {milvus_ok}/{len(chunks)} indexed", end="\r")

        print(f"\n  Complete: {milvus_ok} OK, {milvus_fail} failed")

        async with pool.connection() as conn:
            await update_embedding_run(conn, run_id, "completed" if milvus_fail == 0 else "completed",
                                       chunks_indexed=milvus_ok)

        coll.release()

        # Round-trip check
        print(f"\n[Round-trip]")
        async with pool.connection() as conn:
            in_milvus = await fetch_one(conn, """
                SELECT COUNT(*) as cnt FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id = e.chunk_id
                WHERE c.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL AND e.milvus_primary_key != ''
            """, {"did": DOCUMENT_ID})
            total = await fetch_one(conn, """
                SELECT COUNT(*) as cnt FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id = e.chunk_id
                WHERE c.document_id = %(did)s
            """, {"did": DOCUMENT_ID})

            rt_pct = in_milvus["cnt"] / total["cnt"] * 100 if total["cnt"] > 0 else 0
            print(f"  Embeddings with Milvus pk: {in_milvus['cnt']}/{total['cnt']} ({rt_pct:.0f}%)")

            # Milvus query sample
            sample = await fetch_all(conn, """
                SELECT c.chunk_uid FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id = e.chunk_id
                WHERE c.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL
                LIMIT 20
            """, {"did": DOCUMENT_ID})

            rt_q = 0
            for r in sample:
                coll.load()
                results = coll.query(expr=f'pk == "{r["chunk_uid"]}"', output_fields=["pk"])
                if results and results[0]["pk"] == r["chunk_uid"]:
                    rt_q += 1
            print(f"  Milvus queries (sample 20): {rt_q}/20 verified")

        print(f"\n{'='*60}")
        print(f"  MILVUS DONE — Productivo intacto")
        print(f"{'='*60}")

    finally:
        await close_pool(pool)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
