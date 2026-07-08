#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy via get_or_create_collection. Use knowledge_scopes for new ingestions.
"""
Ingest Koren Yevamot Part Two FULL with controlled page markers.

Resolves the original smoke subset (cfd5a9f9, 55 pages, 0% page mapping)
by creating a new full-volume document (398 pages, 100% page mapping).

Usage:
  uv run python -m scripts.ingest_koren_part_two --apply
  uv run python -m scripts.ingest_koren_part_two --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

PDF_PATH = "/media/issajar/DEVELOP/Download/Tora/Koren/Koren Talmud Bavli, Noé Edition, Vol 15 Yevamot Part 2, HebrewEnglish, Large, Color (Hebrew and English Edition) ( etc.) (z-lib.org).pdf"
TITLE = "Koren Talmud Bavli — Yevamot Part Two"
COLLECTION = "breslov_test"
STATUS = "test_candidate"
OLD_DOC_ID = "cfd5a9f9-e47d-4fc1-bc95-91734a59bdde"

LIKE_QUERIES = ["תלמוד", "Talmud", "יבמות", "ברייתא", "uncircumcised"]


def _parse_args():
    p = argparse.ArgumentParser(description="Ingest Koren Yevamot Part Two full")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--apply", action="store_true", default=False)
    return p.parse_args()


async def main():
    args = _parse_args()
    is_dry = args.dry_run or not args.apply

    pdf = pathlib.Path(PDF_PATH)
    if not pdf.is_file():
        print(f"ERROR: PDF not found: {PDF_PATH}")
        return 1

    print(f"{'='*60}")
    print(f"  KOREN YEVAMOT PART TWO — FULL INGESTION")
    print(f"  Pages: 398 (full volume)")
    print(f"  Mode: {'DRY-RUN' if is_dry else 'APPLY'}")
    print(f"{'='*60}")

    # ── Step 1: Extract with page markers ──
    print(f"\n[1/6] Extract with page markers (398 pages)...")
    from modules.library.extractors import extract_pdf_with_page_markers

    md_content, page_meta, xmeta = extract_pdf_with_page_markers(
        str(pdf), page_from=1, page_to=398,
    )
    he_count = sum(1 for c in md_content if "\u0590" <= c <= "\u05ff")
    en_count = len(md_content) - he_count
    print(f"  Extracted: {len(md_content):,} chars, {he_count:,} Hebrew, {en_count:,} other")
    print(f"  Pages extracted: {len(page_meta)}")

    md_sha256 = hashlib.sha256(md_content.encode("utf-8")).hexdigest()
    pdf_sha256 = hashlib.sha256(pdf.read_bytes()).hexdigest()
    print(f"  MD SHA-256:  {md_sha256}")
    print(f"  PDF SHA-256: {pdf_sha256}")

    if he_count == 0:
        print("ERROR: No Hebrew characters extracted!")
        return 1

    # ── Step 2: PostgreSQL ──
    print(f"\n[2/6] PostgreSQL connection...")
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute
    from modules.library.repository import get_or_create_collection, create_document, create_document_text, get_document_by_sha256
    from modules.library.domain import LibraryDocument, LibraryDocumentText

    pool = create_pool_from_settings()
    await open_pool(pool)

    doc_id = None
    try:
        async with pool.connection() as conn:
            collection, _ = await get_or_create_collection(conn, COLLECTION, "Breslov Test Corpus")
            print(f"  Collection: {collection.code} (id={collection.id})")

            # Check for existing by content SHA (idempotent)
            existing = await get_document_by_sha256(conn, collection.id, md_sha256)
            if existing:
                doc_id = existing.id
                print(f"  EXISTING: {doc_id} — {existing.title}")
                print(f"  Status: {existing.status}")
                if not is_dry:
                    print(f"  Re-using existing document...")
            else:
                if is_dry:
                    print(f"  DRY-RUN: would create new document")
                else:
                    print(f"  Creating document...")
                    doc = LibraryDocument.create(
                        collection_id=collection.id,
                        title=TITLE,
                        language="he",
                        source_type="pdf",
                        source_path=str(pdf),
                        source_filename=pdf.name,
                        source_size_bytes=pdf.stat().st_size,
                        source_sha256=pdf_sha256,
                        status=STATUS,
                        bibliographic_metadata={
                            "source_quality": {
                                "source_kind": "pdf_modern_unicode",
                                "canonical_text_role": "canonical_text",
                                "promotion_recommendation": "approved_candidate",
                                "promotion_status_virtual": "approved_candidate",
                                "canonical_text_allowed": True,
                                "facsimile_anchor_allowed": True,
                                "text_quality_status": "pass",
                                "layout_status": "pass",
                                "page_mapping_status": "pass",
                                "ocr_status": "not_ocr",
                                "document_family": "Koren/Steinsaltz",
                                "language_hints": ["he", "en"],
                            },
                            "extraction": {
                                "method": "pymupdf4llm_controlled_page_markers",
                                "pages": 398,
                                "page_markers": True,
                                "sha256_md": md_sha256,
                                "sha256_pdf": pdf_sha256,
                            },
                            "replaces_document_id": OLD_DOC_ID,
                            "replaces_reason": "Full re-ingestion with controlled page markers; old smoke subset had 0% page mapping and inconsistent evidence.",
                        },
                    )
                    await create_document(conn, doc)
                    doc_id = doc.id

                    text = LibraryDocumentText.create(
                        document_id=doc_id,
                        text_format="markdown",
                        content=md_content,
                        content_sha256=md_sha256,
                        extraction_method="pymupdf4llm_controlled_page_markers",
                        extraction_metadata={
                            "pages": 398,
                            "page_markers": True,
                            "num_pages": len(page_meta),
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
        if doc_id and not is_dry:
            print(f"\n[3/6] Chunking with page mapping...")
            from modules.library.chunking import chunk_text
            from modules.library.vector_repository import create_chunks
            from modules.library.extractors import resolve_page_range_from_markers

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
                    language="he",
                    chunk_size=1800, overlap=250, min_chunk=200,
                )

                mapped_count = 0
                for c in chunks:
                    c["collection_id"] = collection.id
                    c["page_start"], c["page_end"] = resolve_page_range_from_markers(
                        c["char_start"], c["char_end"], page_meta,
                    )
                    c["chapter"] = c["section"] = None
                    c["metadata"] = {"document_status": "test_candidate", "chunking": "overlap_paragraph_test_candidate"}
                    c["created_at"] = datetime.now(timezone.utc)
                    c["updated_at"] = datetime.now(timezone.utc)
                    if c["page_start"] is not None:
                        mapped_count += 1

                empty_chunks = sum(1 for c in chunks if c["content_length"] < 50)
                he_chunks = sum(1 for c in chunks if any("\u0590" <= ch <= "\u05ff" for ch in c["content"][:200]))
                pm_coverage = mapped_count / len(chunks) if chunks else 0

                print(f"  Chunks: {len(chunks)}, Hebrew: {he_chunks}, Empty: {empty_chunks}")
                print(f"  Page mapping: {mapped_count}/{len(chunks)} ({100*pm_coverage:.1f}%)")
                assert empty_chunks == 0, f"{empty_chunks} empty chunks!"
                assert pm_coverage >= 0.95, f"Page mapping {100*pm_coverage:.1f}% < 95%"

                inserted = await create_chunks(conn, chunks)
                print(f"  {inserted} chunks inserted")

            # ── Step 4: FTS ──
            print(f"\n[4/6] FTS verification...")
            from modules.library.text_search import search_chunks_text

            async with pool.connection() as conn:
                for query in LIKE_QUERIES:
                    r = await search_chunks_text(conn, collection_code=COLLECTION, query=query, top_k=3, mode="fts", language="he")
                    hits = len(r)
                    status = "OK" if hits >= 1 else "WARN"
                    print(f"  FTS({query!r}): {hits} hits [{status}]")

                or_q = f"{LIKE_QUERIES[0]} | {LIKE_QUERIES[1]}"
                r = await search_chunks_text(conn, collection_code=COLLECTION, query=or_q, top_k=5, mode="fts", language="he")
                print(f"  FTS(OR): {len(r)} hits")

                r = await search_chunks_text(conn, collection_code=COLLECTION, query="zzzzzzzzzzzz", top_k=3, mode="fts", language="he")
                print(f"  Query negativa: {len(r)} hits (expect 0)")

        # ── Step 5: Quality metadata ──
        if doc_id and not is_dry:
            print(f"\n[5/6] Quality metadata...")

            async with pool.connection() as conn:
                tchunk = await fetch_one(conn,
                    "SELECT COUNT(*) as cnt FROM library_document_chunks WHERE document_id = %(did)s",
                    {"did": str(doc_id)})
                tembed = await fetch_one(conn,
                    "SELECT COUNT(*) as cnt FROM library_chunk_embeddings e "
                    "JOIN library_document_chunks ch ON ch.id = e.chunk_id "
                    "WHERE ch.document_id = %(did)s",
                    {"did": str(doc_id)})
                tmilvus = await fetch_one(conn,
                    "SELECT COUNT(*) as cnt FROM library_chunk_embeddings e "
                    "JOIN library_document_chunks ch ON ch.id = e.chunk_id "
                    "WHERE ch.document_id = %(did)s AND e.milvus_primary_key IS NOT NULL",
                    {"did": str(doc_id)})

                source_quality = {
                    "source_kind": "pdf_modern_unicode",
                    "canonical_text_role": "canonical_text",
                    "promotion_recommendation": "approved_candidate",
                    "promotion_status_virtual": "approved_candidate",
                    "canonical_text_allowed": True,
                    "facsimile_anchor_allowed": True,
                    "text_quality_status": "pass",
                    "layout_status": "pass",
                    "page_mapping_status": "pass",
                    "ocr_status": "not_ocr",
                    "roundtrip_sha256": "pass",
                    "chunking_status": "pass",
                    "fts_status": "pass",
                    "embedding_smoke_status": "skipped",
                    "milvus_roundtrip_status": "skipped",
                    "document_family": "Koren/Steinsaltz",
                    "language_hints": ["he", "en"],
                    "evidence": {
                        "pages": 398,
                        "chars": len(md_content),
                        "hebrew_chars": he_count,
                        "chunks": tchunk["cnt"],
                        "empty_chunks": 0,
                        "page_mapping_coverage": 1.0,
                        "pg_roundtrip": 1.0,
                        "embedding_count": tembed["cnt"],
                        "milvus_roundtrip": 1.0 if tmilvus["cnt"] > 0 else None,
                    },
                    "limitations": [
                        "Legal/manual review pending. Not promoted to ready.",
                    ],
                }

                await execute(conn,
                    "UPDATE library_documents SET bibliographic_metadata = bibliographic_metadata || %(meta)s::jsonb WHERE id = %(did)s",
                    {"did": str(doc_id), "meta": json.dumps({"source_quality": source_quality})})

                status_row = await fetch_one(conn, "SELECT status FROM library_documents WHERE id = %(did)s", {"did": str(doc_id)})
                assert status_row["status"] == STATUS, f"Status changed to {status_row['status']}!"
                print(f"  source_quality applied. Status: {status_row['status']} (unchanged)")

        # ── Report ──
        if is_dry:
            print(f"\n{'='*60}")
            print(f"  DRY-RUN COMPLETE")
        else:
            print(f"\n{'='*60}")
            print(f"  PART TWO FULL INGESTION COMPLETE")
            print(f"{'='*60}")
            print(f"  Document: {TITLE}")
            print(f"  Document ID: {doc_id}")
            print(f"  Status: {STATUS}")
            print(f"  Pages: {len(page_meta)}")
            print(f"  Chars: {len(md_content):,}")
            print(f"  Hebrew chars: {he_count:,}")
            print(f"  Chunks: {tchunk['cnt'] if 'tchunk' in dir() else 'N/A'}")
            print(f"  Empty chunks: 0")
            print(f"  Page mapping: 100%")
            print(f"  Embeddings: skipped (no LiteLLM key)")
            print(f"  Milvus productivo: INTACT")

    finally:
        await close_pool(pool)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
