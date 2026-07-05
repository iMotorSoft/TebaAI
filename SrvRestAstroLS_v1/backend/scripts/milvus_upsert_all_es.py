#!/usr/bin/env python3
"""Simple Milvus upsert for all ES/EN docs pending insertion."""
import asyncio, hashlib, sys, time
from uuid import uuid4

MILVUS = "tebaai_breslov_test_chunks_v1"
SCOPE = "breslov_primary"
BATCH = 16
PREVIEW_MAX = 600

async def main():
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute
    from infrastructure.milvus.client import create_connection
    from modules.embeddings.client import embed_batch
    from pymilvus import Collection

    create_connection()

    pool = create_pool_from_settings()
    await open_pool(pool)

    async with pool.connection() as conn:
        docs = await fetch_all(conn, """SELECT id, title, source_sha256, language
            FROM library_documents WHERE knowledge_scope_id = (
                SELECT id FROM knowledge_scopes WHERE knowledge_scope_code = %(s)s
            ) AND language IN ('es','en') AND status = 'test_candidate'""", {"s": SCOPE})

    coll = Collection(MILVUS)
    coll.load()

    total = 0
    for d in docs:
        async with pool.connection() as conn:
            chunks = await fetch_all(conn, """SELECT c.id, c.chunk_uid, c.content, c.chunk_index,
                c.page_start, c.page_end, e.id as eid FROM library_document_chunks c
                JOIN library_chunk_embeddings e ON e.chunk_id = c.id
                WHERE c.document_id = %(did)s AND e.status = 'indexed' 
                AND (e.milvus_primary_key IS NULL OR e.milvus_primary_key = 'pending')
                ORDER BY c.chunk_index""", {"did": d["id"]})

        if not chunks:
            print(f"  {d['title'][:50]}: OK")
            continue

        print(f"  {d['title'][:50]}: {len(chunks)} pendientes")
        ok = 0
        for b in range(0, len(chunks), BATCH):
            batch = chunks[b:b+BATCH]
            texts = [c["content"][:1000] for c in batch]
            vectors = embed_batch(texts)
            for i, ck in enumerate(batch):
                preview = ck["content"][:PREVIEW_MAX]
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
                    async with pool.connection() as c2:
                        await execute(c2, """UPDATE library_chunk_embeddings 
                            SET milvus_primary_key = %(pk)s, milvus_collection = %(coll)s,
                                vector_status = 'indexed_test', status = 'indexed'
                            WHERE id = %(eid)s""",
                            {"pk": mpk, "coll": MILVUS, "eid": ck["eid"]})
                    ok += 1
                except Exception as e:
                    print(f"    chunk {ck['chunk_uid'][:12]}: {e}")
                    break
            print(f"    {ok}/{len(chunks)}", end="\r")
        print(f"\n    Done: {ok}")
        total += ok

    coll.release()
    print(f"\nTotal indexed: {total}")

    # Verify
    async with pool.connection() as conn:
        for d in docs:
            r = await fetch_one(conn, """SELECT COUNT(*) as c FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id = e.chunk_id
                WHERE c.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL AND e.milvus_primary_key != 'pending'""",
                {"did": d["id"]})
            t = await fetch_one(conn, """SELECT COUNT(*) as c FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id = e.chunk_id
                WHERE c.document_id = %(did)s""", {"did": d["id"]})
            print(f"  {d['title'][:50]}: {r['c']}/{t['c']} en Milvus")

    await close_pool(pool)

asyncio.run(main())
PYEOF
