#!/usr/bin/env python3
"""
Batch embed all 2222 citable chunks for Likutey Halajot Interior Final.
Processes in batches of 16 for efficiency.
"""
from __future__ import annotations
import asyncio, hashlib, sys, pathlib, time
from uuid import uuid4, UUID
sys.path.insert(0, ".")

import globalVar

DOC_ID = "47768aac-704e-4296-9649-53b9ea037096"
MILVUS_COLL = "tebaai_breslov_test_chunks_v1"
EMBED_MODEL = "openai_text_embedding_3_small"
EMBED_DIM = 1536
BATCH_SIZE = 16
TITLE = "Likutey Halajot Explicado — Interior Final"
PDF_PATH = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
pdf_sha256 = hashlib.sha256(pathlib.Path(PDF_PATH).read_bytes()).hexdigest()

async def main():
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all
    from modules.embeddings.client import embed_batch
    from modules.library.vector_repository import (
        create_embedding_run, create_chunk_embedding, update_embedding_run
    )
    from pymilvus import MilvusClient

    pool = create_pool_from_settings()
    await open_pool(pool)

    async with pool.connection() as conn:
        chunks = await fetch_all(conn, """
            SELECT id::text, chunk_uid, content, content_sha256, chunk_index,
                   language, page_start, page_end
            FROM library_document_chunks
            WHERE document_id = %(did)s AND citable = true
            ORDER BY chunk_index
        """, {"did": DOC_ID})
        total = len(chunks)
        print(f"Total citable chunks: {total}")

        mc = MilvusClient(f'http://{globalVar.MILVUS_HOST}:{globalVar.MILVUS_PORT}')
        run_id = uuid4()
        await create_embedding_run(conn, {
            "id": run_id, "collection_code": "breslov_primary",
            "milvus_collection": MILVUS_COLL,
            "embedding_provider": "litellm", "embedding_model": EMBED_MODEL,
            "embedding_dimension": EMBED_DIM, "status": "running",
            "chunks_total": total,
        })

        embed_ok = 0
        t0 = time.time()

        for batch_start in range(0, total, BATCH_SIZE):
            batch = chunks[batch_start:batch_start + BATCH_SIZE]
            texts = [c["content"][:1200] for c in batch]

            try:
                vectors = embed_batch(texts, model=EMBED_MODEL)
                if vectors and len(vectors) == len(batch):
                    for i, ck in enumerate(batch):
                        ck_text = texts[i]
                        preview_bytes = ck_text[:800].encode("utf-8")[:1024]
                        preview = preview_bytes.decode("utf-8", errors="ignore")
                        vector = vectors[i]

                        mc.insert(MILVUS_COLL, [{
                            "pk": ck["chunk_uid"],
                            "chunk_id": ck["chunk_uid"],
                            "document_id": DOC_ID,
                            "collection_code": "breslov_primary",
                            "language": ck["language"] or "es",
                            "title": TITLE[:256],
                            "source_type": "pdf",
                            "source_sha256": pdf_sha256,
                            "content_sha256": ck["content_sha256"],
                            "chunk_index": int(ck["chunk_index"]),
                            "page_start": int(ck.get("page_start") or 0),
                            "page_end": int(ck.get("page_end") or 0),
                            "content_preview": preview,
                            "embedding": [float(v) for v in vector],
                        }])

                        await create_chunk_embedding(conn,
                            chunk_id=UUID(ck["id"]), run_id=run_id,
                            provider="litellm", model=EMBED_MODEL, dimension=EMBED_DIM,
                            milvus_collection=MILVUS_COLL, milvus_pk=ck["chunk_uid"],
                            content_sha256=ck["content_sha256"], status="indexed")
                        embed_ok += 1
            except Exception as exc:
                for ck in batch:
                    await create_chunk_embedding(conn,
                        chunk_id=UUID(ck["id"]), run_id=run_id,
                        provider="litellm", model=EMBED_MODEL, dimension=EMBED_DIM,
                        milvus_collection=MILVUS_COLL, milvus_pk="failed",
                        content_sha256=ck["content_sha256"], status="failed")
                print(f"  BATCH FAIL at {batch_start}: {exc}")

            elapsed = time.time() - t0
            rate = embed_ok / elapsed if elapsed > 0 else 0
            print(f"  {embed_ok}/{total} ({rate:.1f}/s) @ {elapsed:.0f}s")

        await update_embedding_run(conn, run_id, status="completed",
            chunks_embedded=embed_ok, chunks_indexed=embed_ok)
        print(f"\nDone: {embed_ok}/{total} in {time.time()-t0:.0f}s")

    await close_pool(pool)

asyncio.run(main())
