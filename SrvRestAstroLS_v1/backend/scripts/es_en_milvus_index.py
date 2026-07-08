#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Index 20 ES/EN chunks per document into Milvus test and verify round-trip."""

from __future__ import annotations

import asyncio, json, logging, sys
from uuid import UUID, uuid4

logger = logging.getLogger("es_en_milvus_index")

DOCUMENT_PREFIXES = [
    ("c7c10741", "Kokhavey Ohr"),
    ("987bd9d3", "El Alma del Rebe Najmán"),
    ("76f2adbc", "El Jardín de las Almas"),
    ("27f175ea", "KITZUR"),
    ("43ba4f4b", "La Potencia de la Plegaria"),
    ("56ddcc3b", "Likutey Halajot LM II 8"),
]

MILVUS_COLLECTION = "tebaai_breslov_test_chunks_v1"
CHUNKS_PER_DOC = 20

async def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from modules.embeddings.client import embed_batch, embed_text
    from globalVar import EMBEDDINGS_MODEL_ALIAS, EMBEDDINGS_DIMENSION, EMBEDDINGS_BATCH_SIZE
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one
    from modules.library.vector_repository import create_chunk_embedding, create_embedding_run, update_embedding_run
    from infrastructure.milvus.client import (
        create_connection, collection_exists, search_vectors,
        ensure_collection, insert_vectors,
    )

    model = EMBEDDINGS_MODEL_ALIAS
    dim = EMBEDDINGS_DIMENSION
    bs = EMBEDDINGS_BATCH_SIZE

    # Connect Milvus
    create_connection()
    if not collection_exists(MILVUS_COLLECTION):
        ensure_collection(MILVUS_COLLECTION, dimension=dim)
        print(f"Created Milvus collection {MILVUS_COLLECTION}")
    else:
        print(f"Milvus collection {MILVUS_COLLECTION} exists")

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            coll = await fetch_one(conn,
                "SELECT id FROM library_collections_legacy WHERE code = 'breslov_test'")
            if not coll:
                print("ERROR: breslov_test collection not found")
                return
            collection_id = coll["id"]

            for prefix, title in DOCUMENT_PREFIXES:
                doc = await fetch_one(conn, """
                    SELECT d.id, d.title, d.language
                    FROM library_documents d
                    WHERE d.id::text LIKE %(pid)s
                """, {"pid": f"{prefix}%"})
                if not doc:
                    print(f"\n{prefix}: DOC NOT FOUND")
                    continue

                # Delete existing embedding records for these chunks
                await conn.execute("""
                    DELETE FROM library_chunk_embeddings
                    WHERE chunk_id IN (
                        SELECT ch.id FROM library_document_chunks ch
                        WHERE ch.document_id = %(did)s
                        ORDER BY ch.chunk_index
                        LIMIT %(limit)s
                    )
                """, {"did": str(doc["id"]), "limit": CHUNKS_PER_DOC})
                print(f"\n{prefix} ({doc['title'][:40]}): cleaned old embedding records")

                # Get chunks
                chunks = await fetch_all(conn, """
                    SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256,
                           ch.chunk_index, ch.page_start, ch.page_end,
                           ch.language, ch.reference_label, ch.metadata,
                           ch.bibliographic_metadata
                    FROM library_document_chunks ch
                    WHERE ch.document_id = %(did)s
                      AND NOT EXISTS (
                        SELECT 1 FROM library_chunk_embeddings e
                        WHERE e.chunk_id = ch.id
                      )
                    ORDER BY ch.chunk_index
                    LIMIT %(limit)s
                """, {"did": str(doc["id"]), "limit": CHUNKS_PER_DOC})

                if not chunks:
                    print(f"  no unindexed chunks")
                    continue

                actual = len(chunks)
                texts = [c["content"][:1800] for c in chunks]

                print(f"  embedding {actual} chunks via LiteLLM...")
                embeddings = embed_batch(texts, model=model)

                if not embeddings or len(embeddings) != actual:
                    print(f"  ERROR: embedding returned {len(embeddings) if embeddings else 0} vectors")
                    continue

                actual_dim = len(embeddings[0])
                print(f"  dimension: {actual_dim} (expected {dim})")

                # Create embedding run
                run_id = uuid4()
                await create_embedding_run(conn, {
                    "id": run_id,
                    "collection_code": "breslov_test",
                    "milvus_collection": MILVUS_COLLECTION,
                    "embedding_provider": "litellm",
                    "embedding_model": model,
                    "embedding_dimension": actual_dim,
                    "status": "running",
                    "chunks_total": 0,
                })

                # Build Milvus vectors
                milvus_vectors = []
                for j, chunk in enumerate(chunks):
                    vec = embeddings[j]
                    meta = chunk.get("metadata") or {}
                    bib = chunk.get("bibliographic_metadata") or {}
                    page_mapping = bib.get("page_mapping", {})
                    ps = chunk.get("page_start") or page_mapping.get("pdf_page_start") or 0
                    pe = chunk.get("page_end") or page_mapping.get("pdf_page_end") or 0

                    milvus_vectors.append({
                        "pk": chunk["chunk_uid"],
                        "chunk_id": str(chunk["id"]),
                        "document_id": str(doc["id"]),
                        "collection_code": "breslov_test",
                        "language": chunk.get("language") or doc["language"],
                        "title": doc["title"],
                        "source_type": "",
                        "source_sha256": "",
                        "content_sha256": chunk["content_sha256"],
                        "chunk_index": chunk["chunk_index"],
                        "page_start": int(ps),
                        "page_end": int(pe),
                        "content_preview": chunk["content"][:200],
                        "embedding": vec,
                    })

                # Insert to Milvus
                try:
                    inserted = insert_vectors(MILVUS_COLLECTION, milvus_vectors)
                    print(f"  Milvus inserted: {inserted}")
                except Exception as exc:
                    print(f"  ERROR inserting to Milvus: {exc}")
                    await update_embedding_run(conn, run_id, "failed", error_message=str(exc))
                    continue

                # Track in PG
                for vec_item in milvus_vectors:
                    await create_chunk_embedding(
                        conn=conn,
                        chunk_id=UUID(vec_item["chunk_id"]),
                        run_id=run_id,
                        provider="litellm",
                        model=model,
                        dimension=actual_dim,
                        milvus_collection=MILVUS_COLLECTION,
                        milvus_pk=vec_item["pk"],
                        content_sha256=vec_item["content_sha256"],
                        status="indexed",
                    )

                await update_embedding_run(
                    conn, run_id, "completed",
                    chunks_embedded=len(chunks),
                    chunks_indexed=inserted,
                )
                print(f"  done: {inserted} vectors indexed")

            # Round-trip verification
            print("\n--- Round-trip verification ---")
            total_ok = 0
            total_check = 0
            for prefix, title in DOCUMENT_PREFIXES:
                doc = await fetch_one(conn, """
                    SELECT d.id, d.title, d.language
                    FROM library_documents d
                    WHERE d.id::text LIKE %(pid)s
                """, {"pid": f"{prefix}%"})
                if not doc:
                    continue

                chunks = await fetch_all(conn, """
                    SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256, ch.chunk_index
                    FROM library_document_chunks ch
                    WHERE ch.document_id = %(did)s
                      AND EXISTS (
                        SELECT 1 FROM library_chunk_embeddings e
                        WHERE e.chunk_id = ch.id
                      )
                    ORDER BY ch.chunk_index
                    LIMIT %(limit)s
                """, {"did": str(doc["id"]), "limit": CHUNKS_PER_DOC})

                passed = 0
                for ch in chunks:
                    uid = ch["chunk_uid"]
                    sha = ch["content_sha256"]
                    hits = search_vectors(
                        collection_name=MILVUS_COLLECTION,
                        query_embedding=embed_text(ch["content"][:200]),
                        top_k=5,
                        output_fields=["pk", "content_sha256", "chunk_index"],
                        expr=f'pk == "{uid}"',
                    )
                    in_milvus = len(hits) > 0
                    sha_match = hits[0].get("content_sha256", "") == sha if in_milvus else False
                    if in_milvus and sha_match:
                        passed += 1

                pct = round(passed / len(chunks) * 100, 1) if chunks else 0
                total_ok += passed
                total_check += len(chunks)
                print(f"  {prefix} ({doc['title'][:40]}): {passed}/{len(chunks)} ({pct}%)")

            print(f"\nTotal round-trip: {total_ok}/{total_check} ({round(total_ok/total_check*100,1) if total_check else 0}%)")
            print(f"Productivo {MILVUS_COLLECTION.replace('_test_', '_')} intacto (no tocado)")

    finally:
        await close_pool(pool)

if __name__ == "__main__":
    asyncio.run(main())
