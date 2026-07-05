#!/usr/bin/env python3
"""
Batch corpus expansion: ingest Un Día en la Vida + embed all ES/EN docs.

Documents covered:
  - Un Día en la Vida (new ingestion, 196 pages)
  - KITZUR (817 chunks, 0 embeddings)
  - Kokhavey Ohr (852 chunks, 0 embeddings)
  - El Alma del Rebe Najmán (498 chunks, 0 embeddings)
  - La Potencia de la Plegaria (646 chunks, 0 embeddings)
  - El Jardín de las Almas (147 chunks, 0 embeddings)
  - Likutey Halajot LM II 8 (1205 chunks, 0 embeddings)

Usage:
  uv run python -m scripts.batch_ingest_embed_breslov
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import sys
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

SCOPE_CODE = "breslov_primary"
SCOPE_ORG = "tebaai"
SCOPE_WS = "breslov"
SCOPE_PROJ = "breslov_library"
MILVUS_TEST_COLL = "tebaai_breslov_test_chunks_v1"
EMBED_MODEL = "openai_text_embedding_3_small"
EMBED_DIM = 1536
BATCH_SIZE = 16

NEW_DOCS = [
    {
        "title": "Un Día en la Vida de un Jasid de Breslov",
        "pdf": "/media/issajar/DEVELOP/Download/Tora/Breslov/UN DÍA EN LA VIDA (KDP).pdf",
        "lang": "es",
    },
]

EXISTING_DOCS = [
    "KITZUR",
    "Kokhavey Ohr",
    "El Alma del Rebe Najmán",
    "La Potencia de la Plegaria",
    "El Jardín de las Almas",
    "Likutey Halajot LM II 8",
]

def truncate(text: str, n: int = 1200) -> str:
    return text[:n]


async def ensure_scope(conn):
    from modules.library.repository import resolve_scope_context
    return await resolve_scope_context(
        conn,
        organization_code=SCOPE_ORG,
        workspace_code=SCOPE_WS,
        project_code=SCOPE_PROJ,
        knowledge_scope_code=SCOPE_CODE,
    )


async def ingest_new_doc(conn, doc_def: dict, scope) -> str | None:
    from modules.library.extractors import extract_pdf_with_page_markers, compute_file_sha256
    from modules.library.repository import get_collection_by_code, create_document, create_document_text
    from modules.library.domain import LibraryDocument, LibraryDocumentText
    from infrastructure.postgres.transaction import fetch_one

    pdf = pathlib.Path(doc_def["pdf"])
    if not pdf.is_file():
        print(f"  SKIP: PDF not found: {doc_def['pdf']}")
        return None

    # Check if already in PG by title
    existing = await fetch_one(conn,
        "SELECT id FROM library_documents WHERE title ILIKE %(t)s AND knowledge_scope_id = %(sid)s",
        {"t": f"{doc_def['title'][:30]}%", "sid": scope.id})
    if existing:
        print(f"  EXISTS already: {existing['id']}")
        return existing["id"]

    pdf_sha = compute_file_sha256(doc_def["pdf"])
    md_content, page_meta, xmeta = extract_pdf_with_page_markers(str(pdf), page_from=1)
    md_sha = hashlib.sha256(md_content.encode("utf-8")).hexdigest()

    legacy_coll = await get_collection_by_code(conn, SCOPE_CODE)
    legacy_id = legacy_coll.id if legacy_coll else UUID("00000000-0000-0000-0000-000000000001")

    doc = LibraryDocument.create(
        collection_id=legacy_id,
        title=doc_def["title"],
        language=doc_def["lang"],
        source_type="pdf",
        source_path=str(pdf),
        source_filename=pdf.name,
        source_size_bytes=pdf.stat().st_size,
        source_sha256=pdf_sha,
        knowledge_scope_id=scope.id,
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        project_id=scope.project_id,
        status="test_candidate",
        bibliographic_metadata={
            "source_quality": {
                "source_kind": "pdf_modern_unicode",
                "canonical_text_role": "candidate",
                "text_quality_status": "pass",
                "page_mapping_status": "pending_chunk_validation",
            },
            "extraction": {
                "method": "pymupdf4llm_controlled_page_markers",
                "pages": len(page_meta),
                "page_markers": True,
                "sha256_md": md_sha,
                "sha256_pdf": pdf_sha,
            },
        },
    )
    await create_document(conn, doc)

    text = LibraryDocumentText.create(
        document_id=doc.id,
        text_format="markdown",
        content=md_content,
        content_sha256=md_sha,
        extraction_method="pymupdf4llm_controlled_page_markers",
        knowledge_scope_id=scope.id,
        page_markers_enabled=True,
        page_count=len(page_meta),
    )
    await create_document_text(conn, text)
    print(f"  INGESTED: {doc.id} — {doc_def['title']} ({len(page_meta)} págs, {len(md_content):,} chars)")

    # Chunking
    from modules.library.chunking import chunk_text
    from modules.library.vector_repository import create_chunks
    from modules.library.extractors import resolve_page_range_from_markers

    text_row = await fetch_one(conn,
        "SELECT id FROM library_document_texts WHERE document_id = %(did)s ORDER BY created_at DESC LIMIT 1",
        {"did": str(doc.id)})

    chunks = chunk_text(md_content, document_id=doc.id, text_id=text_row["id"],
                        language=doc_def["lang"], chunk_size=1800, overlap=250, min_chunk=200)

    mapped = 0
    for c in chunks:
        c["collection_id"] = legacy_id
        c["knowledge_scope_id"] = scope.id
        c["organization_id"] = scope.organization_id
        c["workspace_id"] = scope.workspace_id
        c["project_id"] = scope.project_id
        c["page_start"], c["page_end"] = resolve_page_range_from_markers(
            c["char_start"], c["char_end"], page_meta)
        c["page_mapping_status"] = "mapped" if c["page_start"] is not None else "not_mapped"
        c["metadata"] = {"document_status": "test_candidate"}
        c["created_at"] = datetime.now(timezone.utc)
        c["updated_at"] = datetime.now(timezone.utc)
        if c["page_start"] is not None:
            mapped += 1

    empty = sum(1 for c in chunks if c["content_length"] < 50)
    print(f"  Chunks: {len(chunks)}, empty: {empty}, page mapped: {mapped}/{len(chunks)} ({100*mapped/len(chunks):.0f}%)")
    inserted = await create_chunks(conn, chunks)
    print(f"  {inserted} chunks inserted")
    return str(doc.id)


async def embed_document(conn, doc_id: str, scope, pool):
    from modules.library.vector_repository import (
        create_embedding_run, create_chunk_embedding, update_embedding_run,
    )
    from modules.embeddings.client import embed_batch
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute

    # Get unembedded chunks
    chunks = await fetch_all(conn, """
        SELECT c.id, c.chunk_uid, c.content, c.chunk_index, c.page_start, c.page_end,
               c.collection_id, c.knowledge_scope_id, c.organization_id, c.workspace_id,
               c.project_id, c.chunk_set_version
        FROM library_document_chunks c
        LEFT JOIN library_chunk_embeddings e ON e.chunk_id = c.id AND e.status = 'indexed'
        WHERE c.document_id = %(did)s AND e.id IS NULL
        ORDER BY c.chunk_index
    """, {"did": doc_id})

    if not chunks:
        doc_title = await fetch_one(conn, "SELECT title FROM library_documents WHERE id = %s", [doc_id])
        t = doc_title["title"][:50] if doc_title else "?"
        print(f"  {t}: all {await get_embed_count(conn, doc_id)} already embedded, skip")
        return 0, 0

    doc_title = await fetch_one(conn, "SELECT title FROM library_documents WHERE id = %s", [doc_id])
    t = doc_title["title"][:50] if doc_title else "?"
    print(f"\n  {t}: {len(chunks)} chunks to embed")

    run_id = uuid4()
    await create_embedding_run(conn, {
        "id": run_id, "collection_code": SCOPE_CODE,
        "milvus_collection": MILVUS_TEST_COLL,
        "embedding_provider": "litellm", "embedding_model": EMBED_MODEL,
        "embedding_dimension": EMBED_DIM, "status": "running",
        "chunks_total": len(chunks),
    })

    ok, fail = 0, 0
    start = time.time()
    for b in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[b:b+BATCH_SIZE]
        texts = [truncate(c["content"]) for c in batch]
        try:
            vectors = embed_batch(texts, model=EMBED_MODEL)
        except Exception as e:
            print(f"    ERROR batch {b}: {e}")
            fail += len(batch)
            break

        for i, ck in enumerate(batch):
            cs = hashlib.sha256(texts[i].encode("utf-8")).hexdigest()
            await create_chunk_embedding(
                conn, chunk_id=ck["id"], run_id=run_id,
                provider="litellm", model=EMBED_MODEL, dimension=EMBED_DIM,
                milvus_collection=MILVUS_TEST_COLL, milvus_pk="pending",
                content_sha256=cs, status="indexed",
                knowledge_scope_id=ck["knowledge_scope_id"] or scope.id,
                organization_id=ck["organization_id"] or scope.organization_id,
                workspace_id=ck["workspace_id"] or scope.workspace_id,
                project_id=ck["project_id"] or scope.project_id,
                vector_status="generated",
            )
            ok += 1

        rate = ok / (time.time() - start) if (time.time() - start) > 0 else 0
        print(f"    {ok}/{len(chunks)} ({rate:.1f}/s)", end="\r")

    print(f"\n    Done: {ok} OK, {fail} failed")
    await update_embedding_run(conn, run_id, "completed" if fail == 0 else "completed",
                               chunks_embedded=ok)
    return ok, fail


async def get_embed_count(conn, doc_id):
    from infrastructure.postgres.transaction import fetch_one as fo
    r = await fo(conn, """SELECT COUNT(*) as c FROM library_chunk_embeddings e
        JOIN library_document_chunks c ON c.id = e.chunk_id
        WHERE c.document_id = %(did)s AND e.status = 'indexed'""", {"did": doc_id})
    return r["c"] if r else 0


async def main():
    print(f"{'='*60}")
    print(f"  BATCH CORPUS EXPANSION — BRESLOV")
    print(f"{'='*60}")

    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            scope = await ensure_scope(conn)
            print(f"Scope: {scope.knowledge_scope_code} (id={scope.id})")

            # Step 1: Ingest new docs
            print(f"\n[1/3] Ingest new documents...")
            new_ids = []
            for nd in NEW_DOCS:
                doc_id = await ingest_new_doc(conn, nd, scope)
                if doc_id:
                    new_ids.append(doc_id)

            # Step 2: Embed all ES/EN docs
            print(f"\n[2/3] Generate embeddings...")
            all_ids = list(new_ids)
            from infrastructure.postgres.transaction import fetch_all as fa
            existing = await fa(conn, """
                SELECT id, title FROM library_documents 
                WHERE knowledge_scope_id = %(sid)s AND status = 'test_candidate'
                AND language IN ('es', 'en')
                ORDER BY title
            """, {"sid": scope.id})
            for d in existing:
                if str(d["id"]) not in all_ids:
                    all_ids.append(str(d["id"]))

            total_ok, total_fail = 0, 0
            for did in all_ids:
                ok, fail = await embed_document(conn, did, scope, pool)
                total_ok += ok
                total_fail += fail

            print(f"\n  Total embeddings generated: {total_ok}, failed: {total_fail}")

        # Step 3: Milvus upsert
        print(f"\n[3/3] Milvus upsert...")
        from infrastructure.postgres.transaction import fetch_one, fetch_all as fa2
        from modules.embeddings.client import embed_batch as eb
        from modules.library.indexing_service import ensure_collection
        from pymilvus import Collection

        ensure_collection(MILVUS_TEST_COLL, dimension=EMBED_DIM)

        async with pool.connection() as conn:
            doc_info = await fa2(conn, "SELECT id, title, source_type, source_sha256, language FROM library_documents WHERE knowledge_scope_id = %(sid)s AND language IN ('es', 'en') AND status = 'test_candidate'", {"sid": scope.id})

        for d in doc_info:
            async with pool.connection() as conn:
                chunks = await fa2(conn, """
                    SELECT c.id, c.chunk_uid, c.content, c.chunk_index, c.page_start, c.page_end,
                           e.id as eid
                    FROM library_document_chunks c
                    JOIN library_chunk_embeddings e ON e.chunk_id = c.id
                    WHERE c.document_id = %(did)s AND e.status = 'indexed' AND (e.milvus_primary_key IS NULL OR e.milvus_primary_key = 'pending')
                    ORDER BY c.chunk_index
                """, {"did": d["id"]})

            if not chunks:
                print(f"  {d['title'][:50]}: all in Milvus, skip")
                continue

            print(f"  {d['title'][:50]}: {len(chunks)} to index in Milvus")
            coll = Collection(MILVUS_TEST_COLL)
            coll.load()

            ok = 0
            for b in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[b:b+BATCH_SIZE]
                texts = [truncate(c["content"]) for c in batch]
                try:
                    vectors = eb(texts, model=EMBED_MODEL)
                except Exception as e:
                    print(f"    ERROR batch {b}: {e}")
                    break

                for i, ck in enumerate(batch):
                    embed_text = truncate(ck["content"])
                    cs = hashlib.sha256(embed_text.encode("utf-8")).hexdigest()
                    title = str(d["title"] or "")[:256]
                    preview = embed_text[:800]

                    ins = coll.insert([
                        [str(ck["chunk_uid"])], [str(ck["id"])], [str(d["id"])],
                        [str(SCOPE_CODE)], [str(d["language"] or "es")], [title],
                        ["pdf"], [str(d["source_sha256"] or "")], [str(cs)],
                        [int(ck["chunk_index"])], [int(ck.get("page_start") or 0)],
                        [int(ck.get("page_end") or 0)], [str(preview)],
                        [[float(v) for v in vectors[i]]],
                    ])
                    mpk = str(ins.primary_keys[0]) if ins.primary_keys else ""

                    async with pool.connection() as conn2:
                        from infrastructure.postgres.transaction import execute as exec2
                        await exec2(conn2, """
                            UPDATE library_chunk_embeddings
                            SET milvus_primary_key = %(pk)s, milvus_collection = %(coll)s,
                                vector_status = 'indexed_test', status = 'indexed'
                            WHERE id = %(eid)s
                        """, {"pk": mpk, "coll": MILVUS_TEST_COLL, "eid": ck["eid"]})
                    ok += 1

                print(f"    Milvus {ok}/{len(chunks)}", end="\r")

            coll.release()
            print(f"\n    Done: {ok}/{len(chunks)}")

            # Round-trip
            async with pool.connection() as conn:
                total = await fetch_one(conn, """SELECT COUNT(*) as c FROM library_chunk_embeddings e
                    JOIN library_document_chunks c ON c.id = e.chunk_id
                    WHERE c.document_id = %(did)s""", {"did": d["id"]})
                in_m = await fetch_one(conn, """SELECT COUNT(*) as c FROM library_chunk_embeddings e
                    JOIN library_document_chunks c ON c.id = e.chunk_id
                    WHERE c.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL AND e.milvus_primary_key != ''""", {"did": d["id"]})
                rt = f"{in_m['c']}/{total['c']}" if total else "?"
                print(f"    Round-trip: {rt}")

    finally:
        await close_pool(pool)

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
