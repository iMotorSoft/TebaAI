#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Hebrew document test pipeline for TebaAI.

Usage:
    uv run python -m scripts.hebrew_test_pipeline --phase preflight
    uv run python -m scripts.hebrew_test_pipeline --phase extract --page-from 700 --page-to 720
    uv run python -m scripts.hebrew_test_pipeline --phase extract --hebrew-only --page-from 700
    uv run python -m scripts.hebrew_test_pipeline --phase ingest
    uv run python -m scripts.hebrew_test_pipeline --phase chunk
    uv run python -m scripts.hebrew_test_pipeline --phase fts
    uv run python -m scripts.hebrew_test_pipeline --phase embed --limit-chunks 20
    uv run python -m scripts.hebrew_test_pipeline --phase milvus
    uv run python -m scripts.hebrew_test_pipeline --phase roundtrip --limit-chunks 10
    uv run python -m scripts.hebrew_test_pipeline --phase search
    uv run python -m scripts.hebrew_test_pipeline --phase all --page-from 700 --page-to 720
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import pathlib
import sys
from datetime import datetime

logger = logging.getLogger("hebrew_test_pipeline")

PDF_PATH = "/media/issajar/DEVELOP/Download/Tora/tnk Massoretic Text.pdf"
OUTPUT_DIR = pathlib.Path("/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/data")
REPORT_DIR = OUTPUT_DIR / "reports"
PROCESSED_DIR = OUTPUT_DIR / "processed"

PHASES = ["preflight", "extract", "ingest", "chunk", "fts", "embed", "milvus", "roundtrip", "search", "all"]

DOCUMENT_TITLE = "Masoretic Text (Hebrew test)"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hebrew document test pipeline")
    parser.add_argument("--phase", choices=PHASES, default="all", help="Pipeline phase to run")
    parser.add_argument("--page-from", type=int, default=None, help="First page to process (1-indexed)")
    parser.add_argument("--page-to", type=int, default=None, help="Last page to process (1-indexed, inclusive)")
    parser.add_argument("--hebrew-only", action="store_true", help="Only process pages detected as SI-960 Hebrew")
    parser.add_argument("--limit-pages", type=int, default=None, help="Only process first N pages (from start or page-from)")
    parser.add_argument("--limit-chunks", type=int, default=None, help="Only process first N chunks")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    parser.add_argument("--output-json", type=str, default=None, help="Save full report to JSON file")
    parser.add_argument("--output-dir", type=str, default=str(REPORT_DIR), help="Output directory")
    return parser.parse_args(argv)


# ── Phase: Preflight ──────────────────────────────────────────────────────

async def phase_preflight(args: argparse.Namespace) -> dict:
    from scripts.preflight_pdf_books import _preflight_pdf

    pdf_path = pathlib.Path(PDF_PATH)
    print(f"preflight: {pdf_path.name}")
    report = _preflight_pdf(pdf_path, sample_chars=300)

    he_unicode_chars = sum(1 for c in report.get("samples", [{}])[0].get("text", "") if "\u0590" <= c <= "\u05ff") if report.get("samples") else 0
    he_pages = []
    for s in report.get("samples", []):
        text = s.get("text", "")
        he_count = sum(1 for c in text if "\u0590" <= c <= "\u05ff")
        he_pages.append({"page": s["page"], "he_chars": he_count})

    has_rtl = False
    has_niqqud = False
    has_taamim = False
    for s in report.get("samples", []):
        t = s.get("text", "")
        for c in t:
            if "\u0590" <= c <= "\u05ff":
                has_rtl = True
            if "\u05b0" <= c <= "\u05bb":
                has_niqqud = True
            if "\u0591" <= c <= "\u05af":
                has_taamim = True

    report["hebrew_analysis"] = {
        "he_unicode_chars_total_estimate": he_unicode_chars,
        "he_pages_detected": he_pages,
        "has_rtl_detected": has_rtl,
        "has_niqqud_detected": has_niqqud,
        "has_taamim_cantillation_detected": has_taamim,
    }

    output_path = REPORT_DIR / "preflight_tnk_hebrew.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"  saved: {output_path}")
    print(f"  pages={report['page_count']} chars={report['total_chars']} lang={report['detected_language']}")
    print(f"  hebrew: niqqud={'yes' if has_niqqud else 'no'} taamim={'yes' if has_taamim else 'no'}")
    return report


# ── Phase: Extract with selective SI-960 decoding ─────────────────────────

def phase_extract(args: argparse.Namespace) -> dict:
    import pymupdf as fitz
    from modules.library.hebrew_tex_decoder import (
        decode_hebrew_text_selective,
        is_likely_si960_encoded,
        decode_hebrew_text,
    )

    pdf_path = pathlib.Path(PDF_PATH)
    print(f"extract: {pdf_path.name}")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count

    page_from = (args.page_from or 1) - 1  # 0-indexed
    page_to = min(args.page_to or total_pages, total_pages)
    limit = args.limit_pages
    if limit is not None:
        page_to = min(page_from + limit, page_to)

    # First: try canonical PyMuPDF4LLM on a sample page
    pymupdf4llm_hebrew = 0
    pymupdf4llm_usable = False
    try:
        import pymupdf4llm
        sample_pg = page_from if page_from < page_to else 0
        sample = doc.load_page(sample_pg)
        md_sample = pymupdf4llm.to_markdown(str(pdf_path), pages=[sample_pg + 1])
        pymupdf4llm_hebrew = sum(1 for c in md_sample if "\u0590" <= c <= "\u05ff")
        pymupdf4llm_usable = pymupdf4llm_hebrew > 100
        print(f"  pymupdf4llm sample: {len(md_sample)} chars, {pymupdf4llm_hebrew} hebrew chars")
    except Exception as exc:
        print(f"  pymupdf4llm unavailable/error: {exc}")

    tex_exception = not pymupdf4llm_usable and pymupdf4llm_hebrew == 0
    if tex_exception:
        print(f"  -> SI-960 / Tiqwah TeX font exception (0 Hebrew chars from PyMuPDF4LLM)")
        print(f"  -> Using SI-960 decoder for Hebrew pages")

    markdown_pages = []
    page_log = []

    for i in range(page_from, page_to):
        page = doc.load_page(i)
        raw_text = page.get_text()

        if args.hebrew_only and not is_likely_si960_encoded(raw_text):
            page_log.append({
                "page": i + 1,
                "raw_chars": len(raw_text),
                "decoded_chars": len(raw_text),
                "he_chars": 0,
                "decoded": False,
                "reason": "not_si960",
            })
            continue

        decoded_text = decode_hebrew_text_selective(raw_text)
        is_decoded = decoded_text != raw_text
        he_chars = sum(1 for c in decoded_text if "\u0590" <= c <= "\u05ff")

        markdown_pages.append(f"## Page {i + 1}\n\n{decoded_text}")
        page_log.append({
            "page": i + 1,
            "raw_chars": len(raw_text),
            "decoded_chars": len(decoded_text),
            "he_chars": he_chars,
            "decoded": is_decoded,
            "reason": "si960_decoded" if is_decoded else "preserved",
        })

        if (i + 1) % 100 == 0:
            print(f"  page {i + 1}/{page_to}")

    doc.close()

    md_text = "\n\n".join(markdown_pages) if markdown_pages else ""
    md_path = PROCESSED_DIR / "tnk_massoretic_text_decoded.md"
    md_path.write_text(md_text, encoding="utf-8")
    print(f"  saved: {md_path} ({len(md_text)} chars)")

    log_path = PROCESSED_DIR / "tnk_massoretic_text_decoded_pages.json"
    log_path.write_text(json.dumps(page_log, indent=2, ensure_ascii=False), encoding="utf-8")

    decoded_count = sum(1 for p in page_log if p.get("decoded"))

    result = {
        "pages_in_range": len(page_log),
        "pages_decoded": decoded_count,
        "total_chars": len(md_text),
        "total_he_chars": sum(p["he_chars"] for p in page_log),
        "pymupdf4llm_tried": True,
        "pymupdf4llm_hebrew_chars": pymupdf4llm_hebrew,
        "tex_tiqwah_exception": tex_exception,
        "extraction_method": "si960_decoder" if tex_exception else "pymupdf4llm",
        "markdown_path": md_path.name,
        "page_log_path": log_path.name,
    }
    print(f"  pages={result['pages_in_range']} decoded={decoded_count} chars={result['total_chars']} he_chars={result['total_he_chars']}")
    return result


# ── Phase: Ingest document ────────────────────────────────────────────────

async def phase_ingest(args: argparse.Namespace) -> dict:
    from modules.library.service import ingest_document
    from modules.library.schemas import IngestDocumentRequest
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

    md_path = PROCESSED_DIR / "tnk_massoretic_text_decoded.md"
    if not md_path.is_file():
        print(f"ERROR: decoded markdown not found at {md_path}. Run extract phase first.", file=sys.stderr)
        return {"error": "decoded markdown not found"}

    print("ingest: breslov_test collection")
    req = IngestDocumentRequest(
        file_path=str(md_path),
        title=DOCUMENT_TITLE,
        language="he",
        collection="breslov_test",
        source_type="pdf",
        status="test_candidate",
        dry_run=args.dry_run,
    )

    if args.dry_run:
        result = {
            "dry_run": True,
            "collection": req.collection,
            "title": req.title,
            "language": req.language,
            "source_type": req.source_type,
            "status": req.status,
        }
        print(f"  dry-run: collection={req.collection} title={req.title}")
        return result

    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            result = await ingest_document(conn, req)
    finally:
        await close_pool(pool)

    print(f"  document_id={result.document_id}")
    print(f"  content_sha256={result.content_sha256}")
    print(f"  content_length={result.content_length}")
    print(f"  status={result.status} is_new={result.is_new}")
    return result.model_dump() if hasattr(result, "model_dump") else dict(result._asdict())


# ── Phase: Chunk with page mapping ────────────────────────────────────────

async def phase_chunk(args: argparse.Namespace) -> dict:
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one
    from modules.library.chunking import chunk_text
    from modules.library.vector_repository import create_chunks, count_chunks

    print("chunk: breslov_test collection")
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            doc = await fetch_one(
                conn,
                "SELECT d.id AS doc_id, t.id AS text_id, d.language, d.title, "
                "c.id AS collection_id "
                "FROM library_documents d "
                "JOIN library_document_texts t ON t.document_id = d.id "
                "JOIN library_collections_legacy c ON c.id = d.collection_id "
                "WHERE c.code = 'breslov_test' AND d.title = %(title)s "
                "ORDER BY d.created_at DESC LIMIT 1",
                {"title": DOCUMENT_TITLE},
            )
            if not doc:
                return {"error": "document not found in breslov_test"}

            text_row = await fetch_one(
                conn,
                "SELECT content FROM library_document_texts WHERE id = %(text_id)s",
                {"text_id": str(doc["text_id"])},
            )
            content = text_row["content"] if text_row else ""

            if args.limit_chunks:
                estimate_len = args.limit_chunks * 1800
                content = content[:estimate_len]

            chunks = chunk_text(
                content,
                document_id=doc["doc_id"],
                text_id=doc["text_id"],
                language="he",
                chunk_size=1800,
                overlap=250,
                min_chunk=200,
            )

            # Derive page mapping from markdown page markers (## Page N)
            page_from_md = _extract_page_map(content)

            for c in chunks:
                c["collection_id"] = doc["collection_id"]
                c["page_start"], c["page_end"] = _resolve_page_range(
                    c["char_start"], c["char_end"], page_from_md
                )
                c["chapter"] = None
                c["section"] = None
                c["metadata"] = {
                    "page_mapping": f"pg{c['page_start']}-{c['page_end']}" if c["page_start"] else "unknown",
                    "chunking": "overlap_paragraph",
                }
                c["created_at"] = datetime.utcnow()
                c["updated_at"] = datetime.utcnow()

            if args.dry_run:
                he_chunks = sum(
                    1 for c in chunks
                    if any("\u0590" <= ch <= "\u05ff" for ch in c["content"][:200])
                )
                mapped = sum(1 for c in chunks if c["page_start"] is not None)
                result = {
                    "dry_run": True,
                    "document_id": str(doc["doc_id"]),
                    "chunks_prepared": len(chunks),
                    "chunks_with_hebrew": he_chunks,
                    "chunks_with_page_mapping": mapped,
                    "avg_length": round(sum(c["content_length"] for c in chunks) / max(1, len(chunks)), 1) if chunks else 0,
                }
                print(f"  dry-run: {result['chunks_prepared']} chunks, {result['chunks_with_page_mapping']} mapped, {result['chunks_with_hebrew']} hebrew")
                return result

            inserted = await create_chunks(conn, chunks)
            total = await count_chunks(conn, collection_id=doc["collection_id"])
            avg_len = round(sum(c["content_length"] for c in chunks) / max(1, len(chunks)), 1) if chunks else 0
            empty = sum(1 for c in chunks if c["content_length"] < 50)
            he_detected = sum(
                1 for c in chunks
                if any("\u0590" <= ch <= "\u05ff" for ch in c["content"][:200])
            )
            mapped = sum(1 for c in chunks if c["page_start"] is not None)

            result = {
                "document_id": str(doc["doc_id"]),
                "chunks_inserted": inserted,
                "total_chunks_in_collection": total,
                "avg_length": avg_len,
                "empty_chunks": empty,
                "hebrew_detected_chunks": he_detected,
                "chunks_with_page_mapping": mapped,
            }
            print(f"  inserted={inserted} total={total} avg_len={avg_len} mapped={mapped} he_chunks={he_detected}")
            return result
    finally:
        await close_pool(pool)


def _extract_page_map(content: str) -> dict[int, int]:
    """Build char_offset -> page_number map from ``## Page N`` markers.

    Returns {char_offset: page_number}.
    """
    import re
    result = {}
    pat = re.compile(r"^## Page (\d+)", re.MULTILINE)
    for m in pat.finditer(content):
        page_num = int(m.group(1))
        result[m.start()] = page_num
    return result


def _resolve_page_range(
    char_start: int,
    char_end: int,
    page_map: dict[int, int],
) -> tuple[int | None, int | None]:
    """Find page_start/page_end for a char range using offset-based page map."""
    if not page_map:
        return None, None
    offsets = sorted(page_map.keys())
    start_page = None
    end_page = None
    for i, offset in enumerate(offsets):
        page = page_map[offset]
        if offset <= char_start:
            start_page = page
        if offset <= char_end:
            end_page = page
        next_offset = offsets[i + 1] if i + 1 < len(offsets) else float("inf")
        if offset <= char_end < next_offset:
            end_page = page
            break
    return start_page, end_page


# ── Helper: safe OR builder for to_tsquery ────────────────────────────────

_HAS_PIPE_RE = None  # lazy import in _build_tsquery_or


def _build_tsquery_or(terms: list[str], config: str = "simple") -> str:
    """Build a safe ``to_tsquery`` string with OR (``|``) operator.

    Guards against the common mistake of using ``||`` (SQL concatenation)
    instead of ``|`` (to_tsquery OR operator).

    Raises ``ValueError`` if any term contains ``||`` or ``|``.
    """
    for t in terms:
        if "||" in t:
            raise ValueError(
                f"Term {t!r} contains SQL-level `||`. "
                "Use `|` for OR inside to_tsquery, not `||`."
            )
        if "|" in t:
            raise ValueError(
                f"Term {t!r} contains `|`. OR must be expressed across "
                "separate list items, not embedded in a single term."
            )
    return " | ".join(terms)


# ── Phase: FTS validation ─────────────────────────────────────────────────

async def phase_fts(args: argparse.Namespace) -> dict:
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one
    from modules.library.text_search import search_chunks_text

    print("fts: breslov_test collection")
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            # Note: Hebrew text in chunks contains niqqud (combining marks).
            # Plain queries without niqqud won't match ILIKE/FTS due to extra
            # combining characters. We test with book/verse numbers (no niqqud)
            # and verify the OR/tsquery patterns work correctly.
            # Full Hebrew search with niqqud stripping is out of scope for this phase.
            he_elohim = "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd"
            he_yhwh = "\u05d9\u05d4\u05d5\u05d4"
            he_garbage = "\u05d6\u05d6\u05d6\u05d6\u05d6\u05d6\u05d6"

            results_fts_elohim = await search_chunks_text(
                conn, collection_code="breslov_test", query=he_elohim,
                top_k=5, mode="fts", language="he",
            )
            results_phrase = await search_chunks_text(
                conn, collection_code="breslov_test", query=he_elohim,
                top_k=5, mode="phrase", language="he",
            )
            # Also test with numbers (no niqqud issue)
            results_fts_num = await search_chunks_text(
                conn, collection_code="breslov_test", query="684",
                top_k=5, mode="fts", language="he",
            )
            results_phrase_num = await search_chunks_text(
                conn, collection_code="breslov_test", query="684",
                top_k=5, mode="phrase", language="he",
            )

            # Correct OR: use | (pipe) as to_tsquery OR operator
            correct_or_query = _build_tsquery_or([he_elohim, he_yhwh])
            row = await fetch_one(
                conn,
                "SELECT to_tsquery('simple', %(q)s) AS tsq",
                {"q": correct_or_query},
            )
            tsq_or_valid = row["tsq"] if row else None

            # Guard test: || should NOT be used inside to_tsquery
            pipe_delim_query = f"{he_elohim} || {he_yhwh}"
            try:
                _build_tsquery_or([pipe_delim_query])
                pipe_delim_caught = False
            except ValueError:
                pipe_delim_caught = True

            # websearch_to_tsquery (exploratory for Hebrew)
            try:
                row3 = await fetch_one(
                    conn,
                    "SELECT websearch_to_tsquery('simple', %(q)s) AS tsq",
                    {"q": f"{he_elohim} or {he_yhwh}"},
                )
                wtsq = row3["tsq"] if row3 else None
            except Exception as exc:
                wtsq = f"error: {exc}"

            # Negative query
            row4 = await fetch_one(
                conn,
                "SELECT to_tsquery('simple', %(q)s) AS tsq",
                {"q": he_garbage},
            )
            no_match_tsq = row4["tsq"] if row4 else None

            # Run || test LAST — it crashes the transaction intentionally
            try:
                row2 = await fetch_one(
                    conn,
                    "SELECT to_tsquery('simple', %(q)s) AS tsq",
                    {"q": pipe_delim_query},
                )
                tsq_bad_or = row2["tsq"] if row2 else None
            except Exception as exc:
                tsq_bad_or = f"expected_error: {exc}"
                await conn.rollback()

            result = {
                "he_elohim_query": he_elohim,
                "fts_elohim_count": len(results_fts_elohim),
                "phrase_elohim_count": len(results_phrase),
                "fts_number_query_684": len(results_fts_num),
                "phrase_number_query_684": len(results_phrase_num),
                "to_tsquery_or_correct": str(tsq_or_valid) if tsq_or_valid else None,
                "to_tsquery_or_correct_valid": tsq_or_valid is not None and len(str(tsq_or_valid)) > 0 if tsq_or_valid else False,
                "pipe_delim_guard_triggered": pipe_delim_caught,
                "to_tsquery_pipe_delim_result": str(tsq_bad_or) if tsq_bad_or else None,
                "websearch_to_tsquery_result": str(wtsq) if wtsq else None,
                "no_match_tsquery": str(no_match_tsq) if no_match_tsq else None,
                "fts_samples": [
                    {"chunk_id": str(r["chunk_id"]), "rank": r.get("rank"),
                     "excerpt": r.get("plain_excerpt", "")[:150]}
                    for r in results_fts_elohim[:3]
                ],
            }
            print(f"  fts_hits={result['fts_elohim_count']} phrase_hits={result['phrase_elohim_count']}")
            print(f"  or={'ok' if result['to_tsquery_or_correct_valid'] else 'fail'} "
                  f"guard={'ok' if result['pipe_delim_guard_triggered'] else 'WARN'}")
            return result
    finally:
        await close_pool(pool)


# ── Phase: Embeddings via LiteLLM (from DB chunks) ────────────────────────

async def phase_embed(args: argparse.Namespace) -> dict:
    from modules.embeddings.client import embed_batch
    from globalVar import EMBEDDINGS_MODEL_ALIAS, EMBEDDINGS_DIMENSION
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one
    from modules.library.vector_repository import create_chunk_embedding, create_embedding_run, update_embedding_run
    from uuid import uuid4

    print("embed: breslov_test chunks from PostgreSQL")
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            collection_row = await fetch_one(
                conn,
                "SELECT id FROM library_collections_legacy WHERE code = 'breslov_test'",
            )
            if not collection_row:
                return {"error": "breslov_test collection not found"}
            collection_id = collection_row["id"]

            chunks = await fetch_all(
                conn,
                """
                SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256,
                       ch.chunk_index, d.title, d.language
                FROM library_document_chunks ch
                JOIN library_documents d ON d.id = ch.document_id
                WHERE ch.collection_id = %(cid)s
                  AND NOT EXISTS (
                    SELECT 1 FROM library_chunk_embeddings e
                    WHERE e.chunk_id = ch.id
                  )
                ORDER BY ch.chunk_index
                """,
                {"cid": collection_id},
            )

            if not chunks:
                return {"error": "no unindexed chunks found in breslov_test"}

            limit = args.limit_chunks or len(chunks)
            sample = chunks[:limit]

            model = EMBEDDINGS_MODEL_ALIAS
            texts = [c["content"][:1800] for c in sample]
            print(f"  model={model} dim={EMBEDDINGS_DIMENSION} chunks={len(texts)}")

            embeddings = embed_batch(texts, model=model)

            if not embeddings:
                return {"error": "embedding returned empty list"}

            actual_dim = len(embeddings[0])
            dim_valid = actual_dim == EMBEDDINGS_DIMENSION

            if args.dry_run:
                result = {
                    "dry_run": True,
                    "chunks_read": len(sample),
                    "chunks_to_embed": len(texts),
                    "expected_dimension": EMBEDDINGS_DIMENSION,
                    "actual_dimension": actual_dim,
                    "dimension_valid": dim_valid,
                }
                print(f"  dry-run: {result['chunks_to_embed']} chunks, dim={actual_dim}, valid={dim_valid}")
                return result

            run_id = uuid4()
            await create_embedding_run(
                conn,
                {
                    "id": run_id,
                    "collection_code": "breslov_test",
                    "milvus_collection": "tebaai_breslov_test_chunks_v1",
                    "embedding_provider": "litellm",
                    "embedding_model": model,
                    "embedding_dimension": actual_dim,
                    "status": "running",
                    "chunks_total": 0,
                },
            )
            for i, chunk in enumerate(sample):
                await create_chunk_embedding(
                    conn,
                    chunk_id=chunk["id"],
                    run_id=run_id,
                    provider="litellm",
                    model=model,
                    dimension=actual_dim,
                    milvus_collection="tebaai_breslov_test_chunks_v1",
                    milvus_pk=chunk["chunk_uid"],
                    content_sha256=chunk["content_sha256"],
                    status="indexed",
                )
            await update_embedding_run(conn, run_id, "completed",
                chunks_embedded=len(sample), chunks_indexed=0,
            )

            result = {
                "model": model,
                "expected_dimension": EMBEDDINGS_DIMENSION,
                "actual_dimension": actual_dim,
                "dimension_valid": dim_valid,
                "chunks_read": len(sample),
                "chunks_embedded": len(embeddings),
                "embeddings_tracked_in_pg": len(sample),
                "run_id": str(run_id),
                "sample_vector_first_5": embeddings[0][:5],
            }
            print(f"  read={result['chunks_read']} embedded={result['chunks_embedded']} dim={actual_dim} valid={dim_valid}")
            return result
    finally:
        await close_pool(pool)


# ── Phase: Milvus test index ──────────────────────────────────────────────

async def phase_milvus(args: argparse.Namespace) -> dict:
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one
    from modules.library.indexing_service import index_existing_chunks
    from infrastructure.milvus.client import collection_exists
    from uuid import UUID

    milvus_collection = "tebaai_breslov_test_chunks_v1"

    if "_test_" not in milvus_collection:
        return {"error": f"Milvus collection '{milvus_collection}' must contain '_test_' - rejected"}

    print(f"milvus: collection={milvus_collection}")
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            collection_row = await fetch_one(
                conn,
                "SELECT id FROM library_collections_legacy WHERE code = 'breslov_test'",
            )
            if not collection_row:
                return {"error": "breslov_test collection not found"}
            collection_id = collection_row["id"]

            if args.dry_run:
                result_ix = await index_existing_chunks(
                    conn,
                    collection_id=collection_id,
                    collection_code="breslov_test",
                    milvus_collection_name=milvus_collection,
                    dry_run=True,
                )
                print(f"  dry-run: {result_ix.get('chunks_to_index', 0)} chunks ready")
                return result_ix

            result_ix = await index_existing_chunks(
                conn,
                collection_id=collection_id,
                collection_code="breslov_test",
                milvus_collection_name=milvus_collection,
            )
            exists = collection_exists(milvus_collection)
            result = {
                "milvus_collection": milvus_collection,
                "collection_exists": exists,
                **result_ix,
            }
            print(f"  status={result_ix.get('status')} embedded={result_ix.get('chunks_embedded')} "
                  f"indexed={result_ix.get('chunks_indexed')}")
            return result
    finally:
        await close_pool(pool)


# ── Phase: Round-trip PG ↔ Milvus ─────────────────────────────────────────

async def phase_roundtrip(args: argparse.Namespace) -> dict:
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one
    from infrastructure.milvus.client import create_connection, search_vectors, collection_exists
    from modules.embeddings.client import embed_text

    milvus_collection = "tebaai_breslov_test_chunks_v1"
    print(f"roundtrip: pg <-> {milvus_collection}")

    create_connection()
    if not collection_exists(milvus_collection):
        return {"error": f"Milvus collection '{milvus_collection}' does not exist"}

    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            chunks = await fetch_all(
                conn,
                """
                SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256, ch.chunk_index
                FROM library_document_chunks ch
                JOIN library_collections_legacy c ON c.id = ch.collection_id
                WHERE c.code = 'breslov_test'
                  AND EXISTS (
                    SELECT 1 FROM library_chunk_embeddings e
                    WHERE e.chunk_id = ch.id
                  )
                ORDER BY ch.chunk_index
                """,
            )
            if not chunks:
                return {"error": "no indexed chunks found"}

            limit = args.limit_chunks or len(chunks)
            sample_chunks = chunks[:limit]

            results = []
            for ch in sample_chunks:
                uid = ch["chunk_uid"]
                content = ch["content"]
                sha256_original = ch["content_sha256"]

                milvus_hits = search_vectors(
                    collection_name=milvus_collection,
                    query_embedding=embed_text(content[:200]),
                    top_k=5,
                    output_fields=["chunk_id", "content_sha256", "chunk_uid", "chunk_index"],
                    expr=f'chunk_uid == "{uid}"',
                )
                in_milvus = len(milvus_hits) > 0
                milvus_sha256 = milvus_hits[0].get("content_sha256", "") if milvus_hits else None
                sha256_match = milvus_sha256 == sha256_original if milvus_sha256 else False

                pg_row = await fetch_one(
                    conn,
                    "SELECT content, content_sha256 FROM library_document_chunks WHERE id = %(id)s",
                    {"id": str(ch["id"])},
                )
                pg_sha256 = pg_row["content_sha256"] if pg_row else None
                pg_content_match = pg_row["content"] == content if pg_row else False

                results.append({
                    "chunk_id": str(ch["id"]),
                    "chunk_uid": uid,
                    "chunk_index": ch["chunk_index"],
                    "in_milvus": in_milvus,
                    "milvus_content_sha256": milvus_sha256,
                    "sha256_match_pg_milvus": sha256_match,
                    "pg_content_sha256": pg_sha256,
                    "pg_content_retrieved_match": pg_content_match,
                })

            passed = sum(1 for r in results if r["sha256_match_pg_milvus"] and r["in_milvus"])
            result = {
                "chunks_checked": len(results),
                "passed": passed,
                "failed": len(results) - passed,
                "details": results[:10],
            }
            print(f"  checked={result['chunks_checked']} passed={result['passed']} failed={result['failed']}")
            return result
    finally:
        await close_pool(pool)


# ── Phase: Search smoke tests ─────────────────────────────────────────────

async def phase_search(args: argparse.Namespace) -> dict:
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.milvus.client import create_connection, search_vectors, ensure_collection, collection_exists
    from modules.embeddings.client import embed_text
    from modules.library.text_search import search_chunks_text
    from modules.library.hybrid_search import search_chunks_hybrid
    from globalVar import EMBEDDINGS_DIMENSION

    milvus_collection = "tebaai_breslov_test_chunks_v1"
    print("search: smoke tests for breslov_test")
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            queries = [
                ("\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd", "\"elohim\" - basic fts"),
                ("\u05d9\u05d4\u05d5\u05d4", "\"yhwh\" - fts hit expected"),
                ("\u05d6\u05d6\u05d6\u05d6\u05d6\u05d6\u05d6\u05d6\u05d6", "negative - no results expected"),
            ]

            fts_results = {}
            for q, label in queries:
                res = await search_chunks_text(
                    conn, collection_code="breslov_test", query=q,
                    top_k=5, mode="fts", language="he",
                )
                fts_results[label] = {
                    "query": q,
                    "count": len(res),
                    "sample_chunk_ids": [str(r["chunk_id"]) for r in res[:3]],
                }

            create_connection()
            if collection_exists(milvus_collection):
                vec_query = embed_text("\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd")
                ensure_collection(milvus_collection, dimension=EMBEDDINGS_DIMENSION)
                milvus_hits = search_vectors(
                    collection_name=milvus_collection,
                    query_embedding=vec_query,
                    top_k=5,
                    expr='collection_code == "breslov_test"',
                    output_fields=["chunk_id", "title", "content_preview", "chunk_index", "content_sha256"],
                )
                vector_results = [
                    {"chunk_id": h.get("chunk_id", ""), "distance": h.get("distance", 0.0),
                     "content_preview": h.get("content_preview", "")[:100]}
                    for h in milvus_hits
                ]
            else:
                vector_results = []
                milvus_hits = []

            hybrid_results = []
            if collection_exists(milvus_collection) and milvus_collection:
                try:
                    hybrid = await search_chunks_hybrid(
                        conn,
                        collection_code="breslov_test",
                        query="\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd",
                        top_k=5,
                        language="he",
                        milvus_collection=milvus_collection,
                    )
                    hybrid_results = [
                        {"chunk_id": str(r["chunk_id"]), "match_type": r.get("match_type", ""),
                         "hybrid_score": r.get("hybrid_score", 0.0),
                         "source_signals": r.get("source_signals", [])}
                        for r in hybrid[:5]
                    ]
                except Exception as exc:
                    hybrid_results = [{"error": str(exc)}]

            result = {
                "fts_smoke": fts_results,
                "vector_smoke": {
                    "query": "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd",
                    "results": vector_results,
                },
                "hybrid_smoke": {
                    "query": "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd",
                    "results": hybrid_results,
                },
            }
            counts = {k: v["count"] for k, v in fts_results.items()}
            print(f"  fts: {', '.join(f'{k}={c}' for k, c in counts.items())}")
            print(f"  vector: {len(vector_results)} hits")
            print(f"  hybrid: {len(hybrid_results)} results")
            return result
    finally:
        await close_pool(pool)


# ── Run all ───────────────────────────────────────────────────────────────

async def run_all(args: argparse.Namespace) -> dict:
    print("=" * 60)
    print("HEBREW TEST PIPELINE - ALL PHASES")
    print("=" * 60)

    report = {"pipeline": "hebrew_test_pipeline", "started_at": datetime.utcnow().isoformat(), "phases": {}}

    phases_order = ["preflight", "extract", "ingest", "chunk", "fts", "embed", "milvus", "roundtrip", "search"]

    for phase_name in phases_order:
        print()
        print(f">>> Phase: {phase_name}")
        print("-" * 40)
        try:
            fn = globals()[f"phase_{phase_name}"]
            if asyncio.iscoroutinefunction(fn):
                result = await fn(args)
            else:
                result = fn(args)
            report["phases"][phase_name] = result
            status = "ok" if "error" not in (result or {}) else "FAIL"
            print(f"<<< {phase_name}: {status}")
        except Exception as exc:
            logger.exception("Phase %s failed", phase_name)
            report["phases"][phase_name] = {"error": str(exc)}
            print(f"<<< {phase_name}: ERROR - {exc}")

    report["finished_at"] = datetime.utcnow().isoformat()
    report["overall"] = "ok" if not any(
        "error" in (p or {}) for p in report["phases"].values()
    ) else "partial_failure"

    print()
    print("=" * 60)
    print(f"Pipeline complete: {report['overall']}")
    print(f"  phases: {', '.join(f'{k}: {"ok" if "error" not in (v or {}) else "FAIL"}' for k, v in report['phases'].items())}")
    print("=" * 60)
    return report


# ── Main ──────────────────────────────────────────────────────────────────

async def _run(args: argparse.Namespace) -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    phase_map = {
        "preflight": phase_preflight,
        "extract": phase_extract,
        "ingest": phase_ingest,
        "chunk": phase_chunk,
        "fts": phase_fts,
        "embed": phase_embed,
        "milvus": phase_milvus,
        "roundtrip": phase_roundtrip,
        "search": phase_search,
        "all": run_all,
    }
    # embed is now async; phase_embed.__name__ is already "phase_embed"
    # but we need to make sure the phase_map entry is the async function.
    # It already is since we defined it with async def above.

    fn = phase_map[args.phase]

    if asyncio.iscoroutinefunction(fn):
        result = await fn(args)
    else:
        result = fn(args)

    if args.output_json:
        path = pathlib.Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"report: {path}")

    if result and isinstance(result, dict) and result.get("error"):
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
