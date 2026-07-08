#!/usr/bin/env python3
"""Batch Milvus upsert for all ES/EN Breslov documents."""
import asyncio, hashlib, sys
from uuid import uuid4

SCOPE = "breslov_primary"
MILVUS = "tebaai_breslov_test_chunks_v1"
MODEL = "openai_text_embedding_3_small"
DIM = 1536
BATCH = 16

async def main():
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute
    from modules.embeddings.client import embed_batch
    from modules.library.indexing_service import ensure_collection
    from modules.library.vector_repository import create_embedding_run, update_embedding_run
    from pymilvus import Collection

    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        from infrastructure.milvus.client import create_connection
        create_connection()
        coll = Collection(MILVUS)
        coll.load()

        docs = await fetch_all(pool, """SELECT id, title, source_type, source_sha256, language
            FROM library_documents WHERE knowledge_scope_id = (
                SELECT id FROM knowledge_scopes WHERE knowledge_scope_code = %(s)s
            ) AND language IN ('es','en') AND status = 'test_candidate'""", {"s": SCOPE})

        total_milvus = 0
        for d in docs:
            chunks = await fetch_all(pool, """SELECT c.id, c.chunk_uid, c.content, c.chunk_index,
                c.page_start, c.page_end, e.id as eid FROM library_document_chunks c
                JOIN library_chunk_embeddings e ON e.chunk_id = c.id
                WHERE c.document_id = %(did)s AND e.status = 'indexed'
                AND (e.milvus_primary_key IS NULL OR e.milvus_primary_key = 'pending')
                ORDER BY c.chunk_index""", {"did": d["id"]})

            if not chunks:
                print(f"  {d['title'][:50]}: already in Milvus")
                continue

            print(f"  {d['title'][:50]}: {len(chunks)} to index")
            ok = 0
            for b in range(0, len(chunks), BATCH):
                batch = chunks[b:b+BATCH]
                texts = [c["content"][:1000] for c in batch]
                try:
                    vectors = embed_batch(texts, model=MODEL)
                except Exception as e:
                    print(f"    ERROR batch {b}: {e}")
                    break

                for i, ck in enumerate(batch):
                    preview = ck["content"][:800]
                    cs = hashlib.sha256(ck["content"][:1000].encode()).hexdigest()
                    title = str(d["title"] or "")[:200]
                    try:
                        ins = coll.insert([
                            [str(ck["chunk_uid"])], [str(ck["id"])], [str(d["id"])],
                            [str(SCOPE)], [str(d["language"] or "es")], [title], ["pdf"],
                            [str(d["source_sha256"] or "")[:64]], [str(cs)],
                            [int(ck["chunk_index"])], [int(ck.get("page_start") or 0)],
                            [int(ck.get("page_end") or 0)], [str(preview)],
                            [[float(v) for v in vectors[i]]],
                        ])
                        mpk = str(ins.primary_keys[0]) if ins.primary_keys else str(uuid4())
                        await execute(pool, """UPDATE library_chunk_embeddings
                            SET milvus_primary_key = %(pk)s, milvus_collection = %(coll)s,
                                vector_status = 'indexed_test', status = 'indexed'
                            WHERE id = %(eid)s""",
                            {"pk": mpk, "coll": MILVUS, "eid": ck["eid"]})
                        ok += 1
                    except Exception as e:
                        print(f"    ERROR insert chunk {ck['chunk_uid'][:12]}: {e}")
                        break
                print(f"    {ok}/{len(chunks)}", end="\r")

            coll.release()
            print(f"\n    Done: {ok}")
            total_milvus += ok

            r = await fetch_one(pool, """SELECT COUNT(*) as c FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id = e.chunk_id
                WHERE c.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL AND e.milvus_primary_key != ''""",
                {"did": d["id"]})
            t = await fetch_one(pool, """SELECT COUNT(*) as c FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id = e.chunk_id
                WHERE c.document_id = %(did)s""", {"did": d["id"]})
            print(f"    Round-trip: {r['c']}/{t['c']}")
            coll = Collection(MILVUS)
            coll.load()

        print(f"\n  Total indexed in Milvus: {total_milvus}")
    finally:
        await close_pool(pool)

asyncio.run(main())
PYEOF
