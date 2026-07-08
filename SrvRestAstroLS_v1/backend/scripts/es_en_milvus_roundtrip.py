#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Index ES/EN embeddings into Milvus test and verify round-trip."""

from __future__ import annotations

import asyncio, logging, sys

logger = logging.getLogger("es_en_milvus_roundtrip")

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

    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one
    from modules.library.indexing_service import index_existing_chunks
    from modules.embeddings.client import embed_text
    from infrastructure.milvus.client import (
        create_connection, collection_exists, search_vectors,
        ensure_collection,
    )
    from globalVar import EMBEDDINGS_DIMENSION

    milvus_collection = "tebaai_breslov_test_chunks_v1"

    if "_test_" not in milvus_collection:
        print("ERROR: Milvus collection must contain _test_")
        sys.exit(1)

    print(f"Milvus collection: {milvus_collection}")

    # Connect Milvus
    create_connection()
    exists = collection_exists(milvus_collection)
    print(f"Collection exists: {exists}")

    if not exists:
        ensure_collection(milvus_collection, dimension=EMBEDDINGS_DIMENSION)
        print("Collection created")

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            coll = await fetch_one(conn,
                "SELECT id FROM library_collections_legacy WHERE code = 'breslov_test'")
            if not coll:
                print("ERROR: breslov_test collection not found in PG")
                return
            collection_id = coll["id"]

            print("\n--- Indexing embeddings to Milvus ---")
            result_ix = await index_existing_chunks(
                conn,
                collection_id=collection_id,
                collection_code="breslov_test",
                milvus_collection_name=milvus_collection,
            )
            print(f"Index result: {json.dumps(result_ix, indent=2, default=str)}")

            print("\n--- Round-trip verification per document ---")
            for prefix in DOCUMENT_PREFIXES:
                doc = await fetch_one(conn, """
                    SELECT d.id, d.title, d.language
                    FROM library_documents d
                    WHERE d.id::text LIKE %(pid)s
                """, {"pid": f"{prefix}%"})

                if not doc:
                    print(f"  {prefix}: NOT FOUND")
                    continue

                chunks = await fetch_all(conn, """
                    SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256,
                           ch.chunk_index, ch.page_start, ch.page_end
                    FROM library_document_chunks ch
                    WHERE ch.document_id = %(did)s
                      AND EXISTS (
                        SELECT 1 FROM library_chunk_embeddings e
                        WHERE e.chunk_id = ch.id
                      )
                    ORDER BY ch.chunk_index
                    LIMIT 20
                """, {"did": str(doc["id"])})

                if not chunks:
                    print(f"  {prefix} ({doc['title'][:40]}): 0 indexed chunks found")
                    continue

                passed = 0
                failed = 0
                details = []

                for ch in chunks:
                    uid = ch["chunk_uid"]
                    sha256_original = ch["content_sha256"]

                    milvus_hits = search_vectors(
                        collection_name=milvus_collection,
                        query_embedding=embed_text(ch["content"][:200]),
                        top_k=5,
                        output_fields=["chunk_id", "content_sha256", "chunk_uid", "chunk_index"],
                        expr=f'chunk_uid == "{uid}"',
                    )

                    in_milvus = len(milvus_hits) > 0
                    milvus_sha = milvus_hits[0].get("content_sha256", "") if milvus_hits else None
                    sha_match = milvus_sha == sha256_original if milvus_sha else False

                    # PG re-read
                    pg_row = await fetch_one(conn,
                        "SELECT content_sha256 FROM library_document_chunks WHERE id = %(id)s",
                        {"id": str(ch["id"])})
                    pg_sha = pg_row["content_sha256"] if pg_row else None

                    ok = in_milvus and sha_match and pg_sha == sha256_original
                    if ok:
                        passed += 1
                    else:
                        failed += 1

                    details.append({
                        "chunk_index": ch["chunk_index"],
                        "chunk_uid": uid,
                        "in_milvus": in_milvus,
                        "sha_match": sha_match,
                        "pg_sha_match": pg_sha == sha256_original,
                        "ok": ok,
                    })

                pct = round(passed / len(chunks) * 100, 1) if chunks else 0
                print(f"  {prefix} ({doc['title'][:40]}): {passed}/{len(chunks)} passed ({pct}%)")
                if failed > 0:
                    for d in details:
                        if not d["ok"]:
                            print(f"    FAIL: chunk_index={d['chunk_index']} uid={d['chunk_uid']} in_milvus={d['in_milvus']} sha={d['sha_match']}")

        print("\nRound-trip complete.")
        print(f"Productivo {milvus_collection.replace('_test_', '_')} intacto (no tocado)")

    finally:
        await close_pool(pool)

if __name__ == "__main__":
    import json
    asyncio.run(main())
