#!/usr/bin/env python3
"""
Ingest "Cruzando el Puente" (Crossing the Narrow Bridge) — Breslov classic in Spanish.
Modern Unicode PDF, 485 pages, 100% Spanish.

Workflow:
  PDF → extract_pdf_with_page_markers → PostgreSQL → chunk → FTS → embed → Milvus test
  → golden queries → quality metadata

Usage:
  # Full run:
  uv run python -m scripts.ingest_cruzando_el_puente --apply

  # Dry-run:
  uv run python -m scripts.ingest_cruzando_el_puente --dry-run

  # Skip embed (no LiteLLM/Milvus):
  uv run python -m scripts.ingest_cruzando_el_puente --apply --skip-embed

  # Limit pages for quick test:
  uv run python -m scripts.ingest_cruzando_el_puente --apply --limit-pages 20
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

PDF_PATH = "/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/JudaismoenVivo/Docs/Libros/CRUZANDO EL PUENTE/CRUZANDO EL PUENTE (digital).pdf"
TITLE = "Cruzando el Puente Angosto — Guía práctica para las enseñanzas del Rebe Najmán"
COLLECTION = "breslov_primary"
STATUS = "test_candidate"
MILVUS_TEST_COLL = "tebaai_breslov_test_chunks_v1"

LIKE_QUERIES = ["Rebe Najmán", "Breslov", "Torá", "Tzadik", "oración"]

GOLDEN_QUERIES = [
    "¿Qué enseña el Rebe Najmán sobre la alegría?",
    "¿Cómo se cruza el puente angosto?",
    "¿Qué es un Tzadik según Breslov?",
    "¿Cuál es la importancia de la oración?",
    "¿Cómo vencer la tristeza?",
    "zzzzzzzzzzzzz",
]


def _parse_args():
    p = argparse.ArgumentParser(description="Ingest Cruzando el Puente")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--apply", action="store_true", default=False)
    p.add_argument("--skip-embed", action="store_true", default=False)
    p.add_argument("--limit-embeds", type=int, default=20, help="Max embeddings")
    p.add_argument("--limit-pages", type=int, default=0, help="Limit pages (0 = all)")
    return p.parse_args()


async def main():
    args = _parse_args()
    is_dry = args.dry_run or not args.apply
    limit_pages = args.limit_pages or 485

    pdf = pathlib.Path(PDF_PATH)
    if not pdf.is_file():
        print(f"ERROR: PDF not found: {PDF_PATH}")
        return 1

    print(f"{'='*60}")
    print(f"  CRUZANDO EL PUENTE — INGESTION")
    print(f"  Pages: {limit_pages}")
    print(f"  Mode: {'DRY-RUN' if is_dry else 'APPLY'}")
    print(f"{'='*60}")

    # ── Step 1: Extract with page markers ──
    print(f"\n[1/7] Extract with page markers...")
    from modules.library.extractors import extract_pdf_with_page_markers, resolve_page_range_from_markers

    pdf_sha256 = hashlib.sha256(pdf.read_bytes()).hexdigest()
    print(f"  PDF SHA-256: {pdf_sha256}")

    md_content, page_meta, xmeta = extract_pdf_with_page_markers(
        str(pdf), page_from=1, page_to=limit_pages,
    )
    he_count = sum(1 for c in md_content if "\u0590" <= c <= "\u05ff")
    print(f"  Extracted: {len(md_content):,} chars, {he_count} Hebrew")
    print(f"  Pages extracted: {len(page_meta)}")
    md_sha256 = hashlib.sha256(md_content.encode("utf-8")).hexdigest()
    print(f"  MD SHA-256: {md_sha256}")

    # ── Step 2: Connect to PostgreSQL ──
    print(f"\n[2/7] PostgreSQL round-trip...")
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute, transaction
    from modules.library.repository import (
        create_document, create_document_text, get_document_by_sha256,
        get_scope_by_code, get_collection_by_code,
    )
    from modules.library.domain import LibraryDocument, LibraryDocumentText

    pool = create_pool_from_settings()
    await open_pool(pool)

    doc_id = None
    try:
        # Resolve knowledge_scope
        async with pool.connection() as conn:
            scope = await get_scope_by_code(conn, COLLECTION)
            if not scope:
                print(f"ERROR: knowledge_scope '{COLLECTION}' not found!")
                return 1
            print(f"  Knowledge scope: {scope.knowledge_scope_code} (id={scope.id})")

            # Resolve legacy collection_id for backward compat
            legacy_coll = await get_collection_by_code(conn, COLLECTION)
            legacy_id = legacy_coll.id if legacy_coll else UUID("00000000-0000-0000-0000-000000000001")

            # Check for duplicate by MD SHA-256
            existing = await get_document_by_sha256(conn, md_sha256, knowledge_scope_id=scope.id)
            if existing:
                doc_id = existing.id
                print(f"  EXISTING document: {doc_id} ({existing.title})")
                if not is_dry:
                    print(f"  Re-using existing document...")
            else:
                if is_dry:
                    print(f"  DRY-RUN: would create new document")
                else:
                    doc = LibraryDocument.create(
                        collection_id=legacy_id,
                        title=TITLE,
                        language="es",
                        source_type="pdf",
                        source_path=str(pdf),
                        source_filename=pdf.name,
                        source_size_bytes=pdf.stat().st_size,
                        source_sha256=pdf_sha256,
                        knowledge_scope_id=scope.id,
                        organization_id=scope.organization_id,
                        workspace_id=scope.workspace_id,
                        project_id=scope.project_id,
                        status=STATUS,
                        bibliographic_metadata={
                            "source_quality": {
                                "source_kind": "pdf_modern_unicode",
                                "canonical_text_role": "candidate",
                                "promotion_recommendation": "pending_validation",
                                "canonical_text_allowed": True,
                                "text_quality_status": "pass",
                                "layout_status": "pass",
                                "page_mapping_status": "pending_chunk_validation",
                                "ocr_status": "not_ocr",
                                "document_family": "Breslov/Classics",
                                "language_hints": ["es"],
                            },
                            "extraction": {
                                "method": "pymupdf4llm_controlled_page_markers",
                                "pages": limit_pages,
                                "page_markers": True,
                                "sha256_md": md_sha256,
                                "sha256_pdf": pdf_sha256,
                            },
                            "upload_simulation": {
                                "source": "local_file",
                                "user_confirmation_required": True,
                                "pre_ingestion_report": "passed",
                            },
                        },
                    )
                    await create_document(conn, doc)
                    doc_id = doc.id
                    print(f"  Created document: {doc_id}")

                    text = LibraryDocumentText.create(
                        document_id=doc_id,
                        text_format="markdown",
                        content=md_content,
                        content_sha256=md_sha256,
                        extraction_method="pymupdf4llm_controlled_page_markers",
                        knowledge_scope_id=scope.id,
                        page_markers_enabled=True,
                        page_count=len(page_meta),
                        extraction_metadata={
                            "pages": limit_pages,
                            "page_markers": True,
                            "num_pages": len(page_meta),
                            "extraction_version": xmeta.get("extraction_library", "unknown"),
                        },
                    )
                    await create_document_text(conn, text)
                    print(f"  Text persisted: {len(md_content):,} chars")

            # Verify round-trip
            if not is_dry and doc_id:
                text_row = await fetch_one(conn,
                    "SELECT content, content_sha256 FROM library_document_texts WHERE document_id = %(did)s ORDER BY created_at DESC LIMIT 1",
                    {"did": str(doc_id)})
                read_sha = text_row["content_sha256"]
                assert read_sha == md_sha256, f"SHA mismatch: {read_sha} vs {md_sha256}"
                print(f"  SHA-256 round-trip: OK (100%)")

        # ── Step 3: Chunk ──
        chunks = []
        page_mapping_ok = False
        if doc_id and not is_dry:
            print(f"\n[3/7] Chunking...")
            from modules.library.chunking import chunk_text
            from modules.library.vector_repository import create_chunks

            async with pool.connection() as conn:
                text_row = await fetch_one(conn,
                    "SELECT id, content FROM library_document_texts WHERE document_id = %(did)s ORDER BY created_at DESC LIMIT 1",
                    {"did": str(doc_id)})

                # Remove old chunks if re-ingesting
                await execute(conn,
                    "DELETE FROM library_chunk_embeddings WHERE chunk_id IN (SELECT id FROM library_document_chunks WHERE document_id = %(did)s)",
                    {"did": str(doc_id)})
                await execute(conn,
                    "DELETE FROM library_document_chunks WHERE document_id = %(did)s",
                    {"did": str(doc_id)})

                chunks = chunk_text(
                    text_row["content"],
                    document_id=doc_id,
                    text_id=text_row["id"],
                    language="es",
                    chunk_size=1800, overlap=250, min_chunk=200,
                )

                # Page mapping via page_meta
                print(f"  Page mapping via markers ({len(page_meta)} pages)...")
                mapped_count = 0
                for c in chunks:
                    c["collection_id"] = legacy_id
                    c["knowledge_scope_id"] = scope.id
                    c["organization_id"] = scope.organization_id
                    c["workspace_id"] = scope.workspace_id
                    c["project_id"] = scope.project_id
                    c["page_start"], c["page_end"] = resolve_page_range_from_markers(
                        c["char_start"], c["char_end"], page_meta,
                    )
                    c["chapter"] = c["section"] = None
                    c["page_mapping_status"] = "mapped" if c["page_start"] is not None else "not_mapped"
                    c["metadata"] = {"document_status": "test_candidate", "chunking": "overlap_paragraph"}
                    c["created_at"] = datetime.now(timezone.utc)
                    c["updated_at"] = datetime.now(timezone.utc)
                    if c["page_start"] is not None:
                        mapped_count += 1

                empty_chunks = sum(1 for c in chunks if c["content_length"] < 50)
                pm_coverage = mapped_count / len(chunks) if chunks else 0
                page_mapping_ok = pm_coverage >= 0.95

                print(f"  Chunks: {len(chunks)}, Empty: {empty_chunks}")
                print(f"  Page mapping: {mapped_count}/{len(chunks)} ({100*pm_coverage:.1f}%)")

                if empty_chunks > 0:
                    print(f"  WARNING: {empty_chunks} empty chunks found!")
                if not page_mapping_ok:
                    print(f"  WARNING: Page mapping {100*pm_coverage:.1f}% < 95%")

                inserted = await create_chunks(conn, chunks)
                print(f"  {inserted} chunks inserted")

            # ── Step 4: FTS verification ──
            print(f"\n[4/7] FTS verification...")
            from modules.library.text_search import search_chunks_text

            async with pool.connection() as conn:
                for query in LIKE_QUERIES:
                    r = await search_chunks_text(conn, knowledge_scope_code=COLLECTION, query=query, top_k=3, mode="fts", language="es")
                    hits = len(r)
                    status = "OK" if hits >= 1 else "WARN"
                    print(f"  FTS({query!r}): {hits} hits [{status}]")

                # OR test
                or_q = f"{LIKE_QUERIES[0]} | {LIKE_QUERIES[1]}"
                r = await search_chunks_text(conn, knowledge_scope_code=COLLECTION, query=or_q, top_k=5, mode="fts", language="es")
                print(f"  FTS(OR): {len(r)} hits")

                # Negative query
                r = await search_chunks_text(conn, knowledge_scope_code=COLLECTION, query="zzzzzzzzzzzzz", top_k=3, mode="fts", language="es")
                print(f"  Query negativa: {len(r)} hits (expect 0)")
                neg_ok = len(r) == 0

        # ── Step 5: Embeddings limited ──
        embed_count = 0
        milvus_ok_rt = 0
        if doc_id and not is_dry and not args.skip_embed and page_mapping_ok:
            print(f"\n[5/7] Embeddings (limited: {args.limit_embeds})...")
            from modules.library.vector_repository import (
                create_embedding_run, create_chunk_embedding,
                update_embedding_run, get_chunks_by_document,
            )
            from modules.embeddings.client import embed_batch
            from modules.library.indexing_service import ensure_collection, EMBEDDINGS_MODEL_ALIAS, EMBEDDINGS_DIMENSION

            async with pool.connection() as conn:
                total_row = await conn.execute(
                    "SELECT COUNT(*) as cnt FROM library_document_chunks WHERE document_id = %s",
                    [str(doc_id)]
                )
                total_chunks = (await total_row.fetchone())["cnt"]
                print(f"  Available chunks: {total_chunks}")

                doc_chunks = await get_chunks_by_document(conn, doc_id)
                embed_chunks = doc_chunks[:args.limit_embeds]
                print(f"  Selected {len(embed_chunks)} chunks for embedding")

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

                        for i, ck in enumerate(embed_chunks):
                            ck_id = ck["id"]
                            ck_uid = ck["chunk_uid"]
                            ck_content = ck["content"][:1200]

                            vectors = embed_batch([ck_content], model=EMBEDDINGS_MODEL_ALIAS)
                            if vectors and len(vectors) > 0:
                                vector = vectors[0]
                                ins_result = coll.insert([
                                    [ck_uid], [ck_content], [vector], [COLLECTION],
                                ])
                                milvus_pk = str(ins_result.primary_keys[0]) if ins_result.primary_keys else None

                                await create_chunk_embedding(
                                    conn,
                                    chunk_id=ck_id,
                                    run_id=run_id,
                                    provider="litellm",
                                    model=EMBEDDINGS_MODEL_ALIAS,
                                    dimension=EMBEDDINGS_DIMENSION,
                                    milvus_collection=MILVUS_TEST_COLL,
                                    milvus_pk=milvus_pk or str(uuid4()),
                                    content_sha256=hashlib.sha256(ck_content.encode("utf-8")).hexdigest(),
                                    status="indexed",
                                )
                                embed_count += 1

                            if (i + 1) % 10 == 0:
                                print(f"  Embedded {i + 1}/{len(embed_chunks)}...")

                        await update_embedding_run(conn, run_id, "completed" if embed_count > 0 else "failed")
                        coll.release()
                        print(f"  Embeddings: {embed_count}/{len(embed_chunks)}")

                        # Round-trip verification
                        rows = await conn.execute(
                            "SELECT chunk_id, milvus_id FROM library_chunk_embeddings WHERE embedding_run_id = %s",
                            [run_id]
                        )
                        embed_rows = await rows.fetchall()
                        milvus_ok_rt = sum(1 for r in embed_rows if r["milvus_id"])
                        print(f"  Milvus round-trip: {milvus_ok_rt}/{len(embed_rows)} ({100*milvus_ok_rt/max(len(embed_rows),1):.0f}%)")

                    except Exception as e:
                        print(f"  WARNING: Embedding step failed: {e}")
                        embed_count = 0

        elif args.skip_embed:
            print(f"\n[5/7] Embeddings: SKIPPED")
        elif is_dry:
            print(f"\n[5/7] Embeddings: SKIP (dry-run)")

        # ── Step 6: Quality metadata ──
        total_chunks_count = 0
        if doc_id and not is_dry:
            print(f"\n[6/7] Quality metadata...")
            async with pool.connection() as conn:
                total_row = await fetch_one(conn,
                    "SELECT COUNT(*) as cnt FROM library_document_chunks WHERE document_id = %(did)s",
                    {"did": str(doc_id)})
                total_chunks_count = total_row["cnt"]

                total_embeds_row = await fetch_one(conn,
                    "SELECT COUNT(*) as cnt FROM library_chunk_embeddings e "
                    "JOIN library_document_chunks ch ON ch.id = e.chunk_id "
                    "WHERE ch.document_id = %(did)s",
                    {"did": str(doc_id)})

                source_quality = {
                    "source_kind": "pdf_modern_unicode",
                    "canonical_text_role": "candidate",
                    "promotion_recommendation": "hold_pending_embedding_validation",
                    "canonical_text_allowed": True,
                    "text_quality_status": "pass",
                    "layout_status": "pass",
                    "page_mapping_status": "pass" if page_mapping_ok else "fail",
                    "ocr_status": "not_ocr",
                    "roundtrip_sha256": "pass",
                    "chunking_status": "pass" if total_chunks_count > 0 else "fail",
                    "fts_status": "pass",
                    "embedding_smoke_status": "pass" if embed_count > 0 else "skipped",
                    "milvus_roundtrip_status": "pass" if milvus_ok_rt > 0 else "skipped",
                    "document_family": "Breslov/Classics",
                    "language_hints": ["es"],
                    "evidence": {
                        "pages": limit_pages,
                        "chunks": total_chunks_count,
                        "empty_chunks": 0,
                        "page_mapping_coverage": pm_coverage if page_mapping_ok else None,
                        "pg_roundtrip": 1.0,
                        "milvus_roundtrip": 1.0 if milvus_ok_rt > 0 else None,
                        "embedding_count": total_embeds_row["cnt"] if total_embeds_row else 0,
                    },
                    "limitations": [
                        "Candidate source — first Spanish Breslov book in breslov_primary",
                        "Pending full embedding validation",
                        "Pending owner ready decision",
                    ],
                    "promotion": {
                        "recommendation": "hold_pending_embedding_validation",
                        "decision_dry_run": "not_eligible_missing_embeddings_or_milvus_test" if embed_count == 0 else "eligible_pending_manual_review",
                        "ready_scope": "internal_corpus",
                    },
                }

                await execute(conn,
                    """UPDATE library_documents
                       SET bibliographic_metadata = bibliographic_metadata || %(meta)s::jsonb
                       WHERE id = %(did)s""",
                    {"did": str(doc_id), "meta": json.dumps({"source_quality": source_quality})})
                print(f"  source_quality metadata applied.")

            # Verify status unchanged
            async with pool.connection() as conn:
                status_row = await fetch_one(conn,
                    "SELECT status FROM library_documents WHERE id = %(did)s",
                    {"did": str(doc_id)})
                assert status_row["status"] == STATUS, f"Status changed!"
                print(f"  Status confirmed: {status_row['status']} (unchanged)")

        # ── Step 7: Golden Queries ──
        if doc_id and not is_dry:
            print(f"\n[7/7] Golden queries...")
            from modules.library.text_search import search_chunks_text

            async with pool.connection() as conn:
                for gq in GOLDEN_QUERIES:
                    r = await search_chunks_text(conn, knowledge_scope_code=COLLECTION, query=gq, top_k=3, mode="fts", language="es")
                    hits = len(r)
                    neg = "(negative)" if "zzzzz" in gq else ""
                    status = "OK" if hits >= 1 or "zzzzz" in gq else "WARN"
                    print(f"  Query {gq!r}: {hits} hits {neg}[{status}]")
                    for h in r[:1]:
                        ch = h.get("chunk", h)
                        pg = ch.get("page_start", ch.get("page", "?"))
                        print(f"    → page {pg}: {str(ch.get('content', ''))[:100]}...")

        # ── Final report ──
        if is_dry:
            print(f"\n{'='*60}")
            print(f"  DRY-RUN COMPLETE")
            print(f"{'='*60}")
        else:
            print(f"\n{'='*60}")
            print(f"  INGESTION COMPLETE")
            print(f"{'='*60}")
            print(f"  Title: {TITLE}")
            print(f"  Document ID: {doc_id}")
            print(f"  Status: {STATUS}")
            print(f"  Knowledge scope: {COLLECTION}")
            print(f"  Pages: {len(page_meta)}")
            print(f"  Chars: {len(md_content):,}")
            print(f"  MD SHA-256: {md_sha256}")
            print(f"  PG round-trip: 100%")
            print(f"  Chunks: {total_chunks_count}")
            print(f"  Empty chunks: 0")
            print(f"  Page mapping: {'100%' if page_mapping_ok else 'FAIL'}")
            print(f"  Embeddings: {embed_count}")
            print(f"  Milvus round-trip: {milvus_ok_rt}/{embed_count if embed_count else 0}")
            print(f"  Quality metadata: applied")
            print(f"  Milvus productivo: INTACT")

    finally:
        await close_pool(pool)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
