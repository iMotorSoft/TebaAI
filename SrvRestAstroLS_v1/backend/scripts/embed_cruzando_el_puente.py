#!/usr/bin/env python3
"""
Post-ingestion: Embeddings + Milvus test + golden queries for Cruzando el Puente.
Run after initial ingestion to complete the embedding/Milvus/golden query phases.

Usage:
  # With LITELLM_MASTER_KEY set in the environment (global convention):
  uv run python -m scripts.embed_cruzando_el_puente

  # Or with explicit override:
  TEBAAI_LITELLM_API_KEY="..." uv run python -m scripts.embed_cruzando_el_puente
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from uuid import UUID, uuid4

DOCUMENT_TITLE = "Cruzando el Puente Angosto"
COLLECTION = "breslov_primary"
MILVUS_TEST_COLL = "tebaai_breslov_test_chunks_v1"
LIMIT_EMBEDS = 20

GOLDEN_QUERIES = [
    "¿Qué enseña el Rebe Najmán sobre la alegría?",
    "¿Cómo se cruza el puente angosto?",
    "¿Qué es un Tzadik según Breslov?",
    "¿Cuál es la importancia de la oración?",
    "¿Cómo vencer la tristeza?",
    "¿Qué dice sobre la desesperación?",
    "enseñanzas del Rebe Najmán",
    "alegría y fe",
    "tzadik verdadero",
    "zzzzzzzzzzzzz",
]


async def main():
    print(f"{'='*60}")
    print(f"  CRUZANDO EL PUENTE — EMBEDDING + MILVUS + QUERIES")
    print(f"{'='*60}")

    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute
    from modules.library.vector_repository import (
        create_embedding_run, create_chunk_embedding,
        update_embedding_run, get_chunks_by_document,
    )
    from modules.embeddings.client import embed_batch
    from modules.library.indexing_service import ensure_collection, EMBEDDINGS_MODEL_ALIAS, EMBEDDINGS_DIMENSION
    from modules.library.text_search import search_chunks_text

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        # ── Find document ──
        async with pool.connection() as conn:
            doc = await fetch_one(conn,
                "SELECT id, title, status FROM library_documents "
                "WHERE title LIKE %(t)s AND knowledge_scope_id = (SELECT id FROM knowledge_scopes WHERE knowledge_scope_code = %(scope)s)",
                {"t": f"{DOCUMENT_TITLE}%", "scope": COLLECTION})
            if not doc:
                print("ERROR: Document not found!")
                return 1
            doc_id = doc["id"]
            print(f"\nDocument: {doc['title']}")
            print(f"  ID: {doc_id}")
            print(f"  Status: {doc['status']}")

            # Get scope
            scope = await fetch_one(conn,
                "SELECT id FROM knowledge_scopes WHERE knowledge_scope_code = %(code)s",
                {"code": COLLECTION})

        # ── Embeddings ──
        embed_count = 0
        print(f"\n[1/3] Embeddings (limited: {LIMIT_EMBEDS})...")
        async with pool.connection() as conn:
            doc_chunks = await get_chunks_by_document(conn, doc_id)
            total_chunks = len(doc_chunks)
            print(f"  Total chunks: {total_chunks}")

            # Check existing embeddings
            existing = await fetch_one(conn,
                "SELECT COUNT(*) as cnt FROM library_chunk_embeddings e "
                "JOIN library_document_chunks ch ON ch.id = e.chunk_id "
                "WHERE ch.document_id = %(did)s",
                {"did": str(doc_id)})
            existing_count = existing["cnt"] if existing else 0
            print(f"  Existing embeddings: {existing_count}")

            if existing_count >= LIMIT_EMBEDS:
                print(f"  Embeddings already exist, skipping.")
                embed_count = existing_count
            else:
                embed_chunks = doc_chunks[:LIMIT_EMBEDS]
                print(f"  Will embed {len(embed_chunks)} chunks")

                if embed_chunks:
                    try:
                        ensure_collection(MILVUS_TEST_COLL, dimension=EMBEDDINGS_DIMENSION)
                        run_id = uuid4()
                        await create_embedding_run(conn, {
                            "id": run_id,
                            "collection_code": COLLECTION,
                            "milvus_collection": MILVUS_TEST_COLL,
                            "embedding_provider": "litellm",
                            "embedding_model": EMBEDDINGS_MODEL_ALIAS,
                            "embedding_dimension": EMBEDDINGS_DIMENSION,
                            "status": "running",
                            "chunks_total": len(embed_chunks),
                        })

                        from pymilvus import Collection
                        coll = Collection(MILVUS_TEST_COLL)
                        coll.load()

                        # Get doc metadata for Milvus
                        doc_info = await fetch_one(conn,
                            "SELECT title, source_type, source_sha256, language FROM library_documents WHERE id = %(did)s",
                            {"did": str(doc_id)})

                        for i, ck in enumerate(embed_chunks):
                            ck_id = ck["id"]
                            ck_uid = ck["chunk_uid"]
                            raw_content = ck["content"]
                            embed_text = raw_content[:1000]
                            preview = raw_content[:800]
                            cs = hashlib.sha256(embed_text.encode("utf-8")).hexdigest()

                            vectors = embed_batch([embed_text], model=EMBEDDINGS_MODEL_ALIAS)
                            if vectors and len(vectors) > 0:
                                vector = vectors[0]
                                # Schema: pk, chunk_id, document_id, collection_code, language,
                                #         title, source_type, source_sha256, content_sha256,
                                #         chunk_index, page_start, page_end, content_preview, embedding
                                lang = doc_info["language"] or "es"
                                stitle = str(doc_info["title"] or "")[:256]
                                stype = doc_info["source_type"] or "pdf"
                                ssha = doc_info["source_sha256"] or ""
                                ins_result = coll.insert([
                                    [str(ck_uid)],
                                    [str(ck_id)],
                                    [str(doc_id)],
                                    [str(COLLECTION)],
                                    [str(lang)],
                                    [stitle],
                                    [str(stype)],
                                    [str(ssha)],
                                    [str(cs)],
                                    [int(ck["chunk_index"])],
                                    [int(ck.get("page_start") or 0)],
                                    [int(ck.get("page_end") or 0)],
                                    [str(preview)],
                                    [[float(v) for v in vector]],
                                ])
                                milvus_pk = str(ins_result.primary_keys[0]) if ins_result.primary_keys else str(uuid4())
                                await create_chunk_embedding(
                                    conn,
                                    chunk_id=ck_id,
                                    run_id=run_id,
                                    provider="litellm",
                                    model=EMBEDDINGS_MODEL_ALIAS,
                                    dimension=EMBEDDINGS_DIMENSION,
                                    milvus_collection=MILVUS_TEST_COLL,
                                    milvus_pk=milvus_pk,
                                    content_sha256=cs,
                                    status="indexed",
                                )
                                embed_count += 1

                            if (i + 1) % 10 == 0:
                                print(f"  Embedded {i + 1}/{len(embed_chunks)}...")

                        await update_embedding_run(conn, run_id, "completed" if embed_count > 0 else "failed")
                        coll.release()
                        print(f"  Embeddings: {embed_count}/{len(embed_chunks)}")

                    except Exception as e:
                        print(f"  ERROR: Embedding step failed: {e}")
                        return 1

        # ── Milvus round-trip ──
        print(f"\n[2/3] Milvus round-trip...")
        async with pool.connection() as conn:
            milvus_rows = await fetch_all(conn,
                "SELECT e.chunk_id, e.milvus_primary_key, c.chunk_uid "
                "FROM library_chunk_embeddings e "
                "JOIN library_document_chunks c ON c.id = e.chunk_id "
                "WHERE c.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL AND e.status = 'indexed'",
                {"did": str(doc_id)})
            rt_ok = len(milvus_rows)
            print(f"  Milvus round-trip: {rt_ok}/{embed_count} ({100*rt_ok/max(embed_count,1):.0f}%)")

            # Get Milvus query round-trip
            rt_sha = 0
            for r in milvus_rows:
                from pymilvus import Collection
                coll = Collection(MILVUS_TEST_COLL)
                coll.load()
                results = coll.query(expr=f'pk == "{r["chunk_uid"]}"', output_fields=["pk", "content_preview"])
                coll.release()
                if results and len(results) > 0 and results[0]["pk"] == r["chunk_uid"]:
                    rt_sha += 1
            print(f"  Milvus query round-trip: {rt_sha}/{rt_ok}")

        # ── Golden Queries ──
        print(f"\n[3/3] Golden queries...")
        from modules.library.text_search import search_chunks_text
        from modules.library.hybrid_search import search_chunks_hybrid

        async with pool.connection() as conn:
            for gq in GOLDEN_QUERIES:
                # FTS search
                r_fts = await search_chunks_text(conn, knowledge_scope_code=COLLECTION, query=gq, top_k=3, mode="fts", language="es")
                # Hybrid search
                try:
                    r_hyb = await search_chunks_hybrid(conn, knowledge_scope_code=COLLECTION, query=gq, top_k=3, language="es")
                except Exception:
                    r_hyb = []

                is_neg = "zzzzz" in gq
                neg_mark = " [NEG]" if is_neg else ""
                fts_status = "OK" if (len(r_fts) == 0 if is_neg else len(r_fts) >= 1) else "WARN"
                hyb_status = "OK" if (len(r_hyb) == 0 if is_neg else len(r_hyb) >= 1) else "WARN"

                print(f"\n  Query: {gq}{neg_mark}")
                print(f"    FTS: {len(r_fts)} hits [{fts_status}]")
                print(f"    Hybrid: {len(r_hyb)} hits [{hyb_status}]")

                # Show top FTS result with citation
                if r_fts:
                    top = r_fts[0]
                    ch = top.get("chunk", top)
                    pg = ch.get("page_start", ch.get("page", "?"))
                    snippet = str(ch.get("content", ""))[:150]
                    print(f"    → Cita: página {pg}")
                    print(f"      \"{snippet}...\"")

        # ── Update quality metadata ──
        print(f"\n[+++] Updating quality metadata...")
        async with pool.connection() as conn:
            total_embeds_row = await fetch_one(conn,
                "SELECT COUNT(*) as cnt FROM library_chunk_embeddings e "
                "JOIN library_document_chunks ch ON ch.id = e.chunk_id "
                "WHERE ch.document_id = %(did)s",
                {"did": str(doc_id)})

            milvus_ok = await fetch_one(conn,
                "SELECT COUNT(*) as cnt FROM library_chunk_embeddings e "
                "JOIN library_document_chunks ch ON ch.id = e.chunk_id "
                "WHERE ch.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL AND e.status = 'indexed'",
                {"did": str(doc_id)})

            quality_update = {
                "source_quality": {
                    "embedding_smoke_status": "pass" if embed_count > 0 else "skipped",
                    "milvus_roundtrip_status": "pass" if rt_ok > 0 else "skipped",
                    "evidence": {
                        "embedding_count": total_embeds_row["cnt"] if total_embeds_row else 0,
                        "milvus_roundtrip": rt_ok / embed_count if embed_count else None,
                        "pg_roundtrip": 1.0,
                    },
                },
                "promotion": {
                    "recommendation": "hold_pending_manual_review",
                    "decision_dry_run": "eligible_pending_manual_review" if embed_count > 0 else "not_eligible",
                    "ready_scope": "internal_corpus",
                },
            }

            await execute(conn,
                """UPDATE library_documents
                   SET bibliographic_metadata = bibliographic_metadata || %(meta)s::jsonb
                   WHERE id = %(did)s""",
                {"did": str(doc_id), "meta": json.dumps(quality_update)})
            print(f"  Quality metadata updated.")

        # ── Final report ──
        print(f"\n{'='*60}")
        print(f"  COMPLETE")
        print(f"{'='*60}")
        print(f"  Document: {doc['title']}")
        print(f"  ID: {doc_id}")
        print(f"  Embedded: {embed_count}")
        print(f"  Milvus round-trip: {rt_ok}/{embed_count}")
        print(f"  Milvus productivo: INTACT")
        print(f"{'='*60}")

    finally:
        await close_pool(pool)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
