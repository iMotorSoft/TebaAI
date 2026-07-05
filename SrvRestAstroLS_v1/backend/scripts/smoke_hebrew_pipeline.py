#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Reproducible Hebrew/bilingual pipeline smoke test — small, fast, idempotent.

Validates:
  PDF → PyMuPDF4LLM (modern) OR fitz + SI-960 (legacy) → Markdown UTF-8
  → PostgreSQL (library_document_texts)
  → chunking → FTS → embeddings (LiteLLM) → Milvus test
  → round-trip PG↔Milvus → text retrieval.

Usage:
    # Default: Tanaj SI-960 PDF (LITELLM_MASTER_KEY from environment is sufficient)
    uv run python -m scripts.smoke_hebrew_pipeline

    # Koren modern bilingual PDF with PyMuPDF4LLM
    uv run python -m scripts.smoke_hebrew_pipeline \\
        --pdf-path "/path/to/koren.pdf" \\
        --title "SMOKE — Koren test" \\
        --extraction-mode pymupdf4llm \\
        --limit-pages 10 --limit-chunks 5

    # Other options
    uv run python -m scripts.smoke_hebrew_pipeline --skip-embed --cleanup

Requirements:
  - Services: PostgreSQL, Milvus, LiteLLM (all running)
  - LITELLM_MASTER_KEY in the environment (global convention).
    TEBAAI_LITELLM_API_KEY is accepted as fallback.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import pathlib
import sys
from datetime import datetime
from uuid import uuid4

DEFAULT_PDF = "/media/issajar/DEVELOP/Download/Tora/tnk Massoretic Text.pdf"
DEFAULT_TITLE = "SMOKE TEST — Tanakh pages 1-25 (remove me)"
MILVUS_COLL = "tebaai_breslov_test_chunks_v1"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hebrew/bilingual pipeline smoke test")
    p.add_argument("--pdf-path", type=str, default=DEFAULT_PDF, help="Path to PDF file")
    p.add_argument("--title", type=str, default=DEFAULT_TITLE, help="Document title")
    p.add_argument("--page-start", type=int, default=1, help="First page to extract (1-indexed, default: 1)")
    p.add_argument("--limit-pages", type=int, default=25, help="Max pages to extract from --page-start (default: 25)")
    p.add_argument("--limit-chunks", type=int, default=10, help="Chunks to embed (default: 10)")
    p.add_argument("--skip-embed", action="store_true", help="Skip LiteLLM + Milvus steps")
    p.add_argument("--cleanup", action="store_true", help="Remove smoke test data")
    p.add_argument("--extraction-mode", choices=["pymupdf4llm", "fitz-si960", "auto"], default="auto",
                    help="Extraction mode: pymupdf4llm (modern Unicode PDF), fitz-si960 (Tiqwah TeX), auto (try pymupdf4llm first)")
    p.add_argument("--page-markers", choices=["auto", "force", "off"], default="auto",
                    help="Page marker insertion: auto (for fitz-si960 mode), force (wrap each page with ## Page N), off (no markers)")
    return p.parse_args(argv)


async def _main(args: argparse.Namespace) -> int:
    pdf = pathlib.Path(args.pdf_path)
    if not pdf.is_file():
        print(f"ERROR: PDF not found at {args.pdf_path}")
        return 1

    print(f"=== Hebrew/Bilingual Pipeline Smoke Test ===")
    print(f"PDF: {args.pdf_path}")
    page_from = args.page_start
    page_to = page_from + args.limit_pages - 1
    assert page_from >= 1, "page-start must be >= 1"
    print(f"Pages: {page_from}-{page_to} ({args.limit_pages} pages)")
    print(f"Mode: {args.extraction_mode}")
    print()

    # ── Step 1: Extract ──
    mode = args.extraction_mode
    md_content = ""
    he_count = 0
    artifacts: dict = {}

    page_meta = []
    markers_used = False

    if mode == "pymupdf4llm" or (mode == "auto"):
        # Try PyMuPDF4LLM first (modern Unicode PDFs)
        try:
            if args.page_markers == "force":
                from modules.library.extractors import extract_pdf_with_page_markers
                md_content, page_meta, xmeta = extract_pdf_with_page_markers(
                    str(pdf), page_from=page_from, page_to=page_to,
                )
                he_count = sum(1 for c in md_content if "\u0590" <= c <= "\u05ff")
                print(f"  Page-by-page with markers: {len(md_content)} chars, {he_count} Hebrew, {len(page_meta)} pages")
                markers_used = True
            else:
                import pymupdf4llm
                pages_list = list(range(page_from, min(page_to + 1, 9999)))
                md_content = pymupdf4llm.to_markdown(str(pdf), pages=pages_list)
                he_count = sum(1 for c in md_content if "\u0590" <= c <= "\u05ff")
                print(f"  PyMuPDF4LLM direct: {len(md_content)} chars, {he_count} Hebrew")
            if he_count > 0 or mode == "pymupdf4llm":
                if not markers_used:
                    print(f"  Using PyMuPDF4LLM direct (no page markers)")
                artifacts = {}
            else:
                raise ValueError(f"PyMuPDF4LLM produced 0 Hebrew chars, falling back to SI-960 decoder")
        except Exception as fallback_err:
            if mode == "pymupdf4llm":
                print(f"  PyMuPDF4LLM failed: {fallback_err}")
                raise
            print(f"  {fallback_err}")
            mode = "fitz-si960"

    if mode == "fitz-si960" or (mode == "auto" and he_count == 0):
        print(f"  Using fitz + SI-960 decoder...")
        import pymupdf as fitz
        from modules.library.hebrew_tex_decoder import (
            decode_hebrew_text_selective,
            scan_unknown_characters,
        )
        doc = fitz.open(str(pdf))
        pages_text = []
        for i in range(page_from - 1, min(page_to, doc.page_count)):
            raw = doc.load_page(i).get_text()
            decoded = decode_hebrew_text_selective(raw)
            pages_text.append(f"## Page {i + 1}\n\n{decoded}")
        doc.close()
        md_content = "\n\n".join(pages_text)
        he_count = sum(1 for c in md_content if "\u0590" <= c <= "\u05ff")
        artifacts = scan_unknown_characters(md_content)
        print(f"  SI-960 decoded: {len(md_content)} chars, {he_count} Hebrew, {len(artifacts)} artifact types")
    else:
        artifacts = {}

    assert he_count > 0, "No Hebrew characters extracted!"

    # ── Step 2: Ingest to PostgreSQL ──
    print("[2/7] Ingest to PostgreSQL (breslov_test)...")
    from modules.library.domain import LibraryDocument, LibraryDocumentText
    from modules.library.repository import get_or_create_collection, create_document, create_document_text, get_document_by_sha256
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute

    md_sha256 = hashlib.sha256(md_content.encode("utf-8")).hexdigest()

    pool = create_pool_from_settings()
    await open_pool(pool)

    doc_id = None
    try:
        async with pool.connection() as conn:
            collection, _ = await get_or_create_collection(conn, "breslov_test", "Breslov Test Corpus")

            # Idempotent: find or create
            existing = await get_document_by_sha256(conn, collection.id, md_sha256)
            if existing:
                doc_id = existing.id
                print(f"  Found existing document {doc_id}")
                # Remove old chunks for clean re-test
                await execute(conn,
                    "DELETE FROM library_chunk_embeddings WHERE chunk_id IN (SELECT id FROM library_document_chunks WHERE document_id = %(did)s)",
                    {"did": str(doc_id)})
                await execute(conn,
                    "DELETE FROM library_document_chunks WHERE document_id = %(did)s",
                    {"did": str(doc_id)})
                print(f"  Cleared old chunks for {doc_id}")
            else:
                doc = LibraryDocument.create(
                    collection_id=collection.id,
                    title=args.title,
                    language="he",
                    source_type="pdf",
                    source_sha256=md_sha256,
                    source_path=str(pdf),
                    source_filename=pdf.name,
                    source_size_bytes=pdf.stat().st_size,
                    status="test_candidate",
                    bibliographic_metadata={
                        "pages": f"{page_from}-{page_to}",
                        "test_type": "smoke",
                        "created_at": datetime.utcnow().isoformat(),
                    },
                )
                await create_document(conn, doc)
                doc_id = doc.id
                extraction_method = "pymupdf4llm+page_markers" if markers_used else ("pymupdf4llm" if mode == "pymupdf4llm" else "si960_decoder")
                text = LibraryDocumentText.create(
                    document_id=doc_id,
                    text_format="markdown",
                    content=md_content,
                    content_sha256=md_sha256,
                    extraction_method=extraction_method,
                    extraction_metadata={
                        "pages": f"{page_from}-{page_to}",
                        "page_markers": markers_used,
                        "num_pages": len(page_meta) if page_meta else (page_to - page_from + 1),
                    },
                )
                await create_document_text(conn, text)
                print(f"  Created document {doc_id}")

            # Verify round-trip
            text_row = await fetch_one(conn,
                "SELECT content, content_sha256 FROM library_document_texts WHERE document_id = %(did)s ORDER BY created_at DESC LIMIT 1",
                {"did": str(doc_id)})
            read_sha = text_row["content_sha256"]
            assert read_sha == md_sha256, f"SHA mismatch: {read_sha} vs {md_sha256}"
            print(f"  SHA-256 round-trip: OK")

            # ── Step 3: Chunk ──
            print("[3/7] Chunking...")
            from modules.library.chunking import chunk_text
            from modules.library.vector_repository import create_chunks, count_chunks

            text_row2 = await fetch_one(conn,
                "SELECT id, content FROM library_document_texts WHERE document_id = %(did)s ORDER BY created_at DESC LIMIT 1",
                {"did": str(doc_id)})

            chunks = chunk_text(
                text_row2["content"],
                document_id=doc_id,
                text_id=text_row2["id"],
                language="he",
                chunk_size=1800, overlap=250, min_chunk=200,
            )

            # Page mapping
            if page_meta:
                from modules.library.extractors import resolve_page_range_from_markers
                print(f"  Using page_meta-based mapping ({len(page_meta)} pages)")
                for c in chunks:
                    c["collection_id"] = collection.id
                    c["page_start"], c["page_end"] = resolve_page_range_from_markers(
                        c["char_start"], c["char_end"], page_meta,
                    )
                    c["chapter"] = c["section"] = None
                    c["metadata"] = {"chunking": "overlap_paragraph_smoke"}
                    c["created_at"] = c["updated_at"] = datetime.utcnow()
            else:
                import re
                page_map = {m.start(): int(m.group(1)) for m in re.finditer(r"^## Page (\d+)", text_row2["content"], re.MULTILINE)}
                print(f"  Using regex-based page mapping ({len(page_map)} markers)")

                def resolve_page_range(cs, ce, pmap):
                    if not pmap:
                        return None, None
                    offsets = sorted(pmap.keys())
                    sp, ep = None, None
                    for i, off in enumerate(offsets):
                        pg = pmap[off]
                        if off <= cs:
                            sp = pg
                        if off <= ce:
                            ep = pg
                        next_off = offsets[i + 1] if i + 1 < len(offsets) else float("inf")
                        if off <= ce < next_off:
                            ep = pg
                            break
                    return sp, ep

                for c in chunks:
                    c["collection_id"] = collection.id
                    c["page_start"], c["page_end"] = resolve_page_range(c["char_start"], c["char_end"], page_map)
                    c["chapter"] = c["section"] = None
                    c["metadata"] = {"chunking": "overlap_paragraph_smoke"}
                    c["created_at"] = c["updated_at"] = datetime.utcnow()

            empty = sum(1 for c in chunks if c["content_length"] < 50)
            he_chunks = sum(1 for c in chunks if any("\u0590" <= ch <= "\u05ff" for ch in c["content"][:200]))
            assert empty == 0, f"{empty} empty chunks!"
            print(f"  {len(chunks)} chunks, {he_chunks} with Hebrew, {empty} empty")

            inserted = await create_chunks(conn, chunks)
            print(f"  {inserted} chunks inserted")

            # ── Step 4: FTS test ──
            print("[4/7] FTS test...")
            from modules.library.text_search import search_chunks_text

            # Find actual Hebrew tokens from the content
            he_words = [w for w in md_content.split() if any("\u0590" <= c <= "\u05ff" for c in w) and len(w) >= 3]
            fts_tokens = []
            for w in he_words[:20]:
                token = "".join(c for c in w if 0x0590 <= ord(c) <= 0x05ff or 0x05b0 <= ord(c) <= 0x05bb)
                if len(token) >= 3:
                    fts_tokens.append(token)

            if fts_tokens:
                test_token = fts_tokens[0]
                r = await search_chunks_text(conn, collection_code="breslov_test", query=test_token, top_k=3, mode="fts", language="he")
                print(f"  FTS({test_token!r}): {len(r)} hits (any ≥0 expected)")

            # OR test
            if len(fts_tokens) >= 2:
                from scripts.hebrew_test_pipeline import _build_tsquery_or
                or_str = _build_tsquery_or(fts_tokens[:2])
                row = await fetch_one(conn,
                    "SELECT to_tsquery('simple', %(q)s) AS tsq", {"q": or_str})
                assert row["tsq"] is not None
                print(f"  OR query OK: {or_str}")

            # Reject || — wrapped in savepoint to avoid aborting the transaction
            # which would roll back all prior chunk inserts.
            await execute(conn, "SAVEPOINT pipe_guard")
            try:
                row = await fetch_one(conn,
                    "SELECT to_tsquery('simple', %(q)s) AS tsq",
                    {"q": " || ".join(fts_tokens[:2])})
                await execute(conn, "RELEASE SAVEPOINT pipe_guard")
                print(f"  WARNING: || did not fail - got {row['tsq']}")
            except Exception:
                await execute(conn, "ROLLBACK TO SAVEPOINT pipe_guard")
                print(f"  || correctly rejected by PostgreSQL")

    finally:
        await close_pool(pool)

    # ── Step 5-6: Embeddings + Milvus (optional) ──
    if not args.skip_embed:
        print("[5/7] Embeddings via LiteLLM...")
        from modules.embeddings.client import embed_batch
        from globalVar import EMBEDDINGS_MODEL_ALIAS, EMBEDDINGS_DIMENSION, EMBEDDINGS_BATCH_SIZE

        pool2 = create_pool_from_settings()
        await open_pool(pool2)
        try:
            async with pool2.connection() as conn:
                unindexed = await fetch_all(conn, """
                    SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256, ch.chunk_index,
                           ch.page_start, ch.page_end, ch.language, d.id AS document_id, d.title
                    FROM library_document_chunks ch
                    JOIN library_documents d ON d.id = ch.document_id
                    WHERE d.id = %(did)s
                      AND NOT EXISTS (SELECT 1 FROM library_chunk_embeddings e WHERE e.chunk_id = ch.id)
                    ORDER BY ch.chunk_index LIMIT %(lim)s
                """, {"did": str(doc_id), "lim": args.limit_chunks})

                if not unindexed:
                    print("  No unindexed chunks")
                else:
                    from modules.library.vector_repository import create_embedding_run as cer, create_chunk_embedding as cce, update_embedding_run as uer

                    run_id = uuid4()
                    await cer(conn, {
                        "id": run_id, "collection_code": "breslov_test",
                        "milvus_collection": MILVUS_COLL,
                        "embedding_provider": "litellm",
                        "embedding_model": EMBEDDINGS_MODEL_ALIAS,
                        "embedding_dimension": EMBEDDINGS_DIMENSION,
                        "status": "running", "chunks_total": 0,
                    })

                    texts = [c["content"][:1200] for c in unindexed]
                    embeddings = embed_batch(texts, model=EMBEDDINGS_MODEL_ALIAS)
                    assert len(embeddings) == len(unindexed), "Embedding count mismatch"
                    dim = len(embeddings[0])
                    assert dim == EMBEDDINGS_DIMENSION, f"Dimension {dim} != {EMBEDDINGS_DIMENSION}"
                    print(f"  {len(embeddings)} embeddings, dim={dim}")

                    print("[6/7] Index to Milvus test collection...")
                    from infrastructure.milvus.client import create_connection, ensure_collection, insert_vectors

                    create_connection()
                    ensure_collection(MILVUS_COLL, dimension=EMBEDDINGS_DIMENSION)

                    vectors = []
                    for j, c in enumerate(unindexed):
                        vectors.append({
                            "pk": c["chunk_uid"], "chunk_id": str(c["id"]),
                            "document_id": str(c["document_id"]), "collection_code": "breslov_test",
                            "language": c["language"], "title": c["title"],
                            "source_type": "pdf", "source_sha256": "",
                            "content_sha256": c["content_sha256"],
                            "chunk_index": c["chunk_index"],
                            "page_start": c["page_start"] or 0, "page_end": c["page_end"] or 0,
                            "content_preview": c["content"][:200],
                            "embedding": embeddings[j],
                        })

                    inserted = insert_vectors(MILVUS_COLL, vectors)
                    print(f"  {inserted} vectors indexed")

                    for c in unindexed:
                        await cce(conn, chunk_id=c["id"], run_id=run_id,
                                  provider="litellm", model=EMBEDDINGS_MODEL_ALIAS,
                                  dimension=EMBEDDINGS_DIMENSION,
                                  milvus_collection=MILVUS_COLL, milvus_pk=c["chunk_uid"],
                                  content_sha256=c["content_sha256"], status="indexed")
                    await uer(conn, run_id, "completed",
                              chunks_embedded=len(unindexed), chunks_indexed=inserted)

                    # ── Step 7: Round-trip ──
                    print("[7/7] Round-trip PG↔Milvus...")
                    from modules.embeddings.client import embed_text
                    from infrastructure.milvus.client import search_vectors

                    rt_pass = 0
                    for c in unindexed:
                        qv = embed_text(c["content"][:200])
                        hits = search_vectors(MILVUS_COLL, qv, 5,
                                              expr=f'pk == "{c["chunk_uid"]}"',
                                              output_fields=["pk", "content_sha256"])
                        in_mv = len(hits) > 0 and hits[0].get("content_sha256") == c["content_sha256"]
                        if in_mv:
                            rt_pass += 1

                    rt_pct = 100.0 * rt_pass / len(unindexed)
                    print(f"  Round-trip: {rt_pass}/{len(unindexed)} = {rt_pct:.0f}%")
                    assert rt_pass == len(unindexed), f"Round-trip {rt_pass}/{len(unindexed)}"

        finally:
            await close_pool(pool2)
    else:
        print("[5-7/7] Skipped (--skip-embed)")

    # ── Cleanup ──
    if args.cleanup:
        print()
        print("Cleaning up smoke test data...")
        pool3 = create_pool_from_settings()
        await open_pool(pool3)
        try:
            async with pool3.connection() as conn:
                await execute(conn,
                    "DELETE FROM library_chunk_embeddings WHERE chunk_id IN (SELECT id FROM library_document_chunks WHERE document_id = %(did)s)",
                    {"did": str(doc_id)})
                await execute(conn,
                    "DELETE FROM library_document_chunks WHERE document_id = %(did)s",
                    {"did": str(doc_id)})
                await execute(conn,
                    "DELETE FROM library_document_texts WHERE document_id = %(did)s",
                    {"did": str(doc_id)})
                await execute(conn,
                    "DELETE FROM library_documents WHERE id = %(did)s",
                    {"did": str(doc_id)})
                print(f"  Removed document {doc_id} and all related data")
        finally:
            await close_pool(pool3)

    print()
    print("=== Smoke test PASSED ===")
    return 0


def main() -> int:
    args = _parse_args()
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
