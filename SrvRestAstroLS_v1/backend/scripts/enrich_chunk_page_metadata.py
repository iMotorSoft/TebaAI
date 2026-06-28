#! /usr/bin/env python3
"""
CLI: Enrich chunks with high-confidence page metadata from PDF audit.

Reads PDFs page-by-page, matches chunks to pages, filters by confidence,
and updates PostgreSQL. Dry-run by default.

Usage:
    uv run python -m scripts.enrich_chunk_page_metadata --collection breslov
    uv run python -m scripts.enrich_chunk_page_metadata --collection breslov --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import re
import sys
from collections import Counter
from typing import Any

import pymupdf as fitz

ANCHOR_CHARS = 150


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich chunks with page metadata.")
    parser.add_argument("--collection", default="breslov")
    parser.add_argument("--pdf-root", default="/media/issajar/DEVELOP/Download/Tora/Breslov")
    parser.add_argument("--confidence", default="high", choices=["high"])
    parser.add_argument("--document-title", help="Only process this document")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true", help="Actually write to DB")
    parser.add_argument("--limit", type=int, help="Max chunks to update")
    parser.add_argument("--output-json", help="Path to write JSON report")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def _normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _make_anchors(text: str, n: int = ANCHOR_CHARS) -> list[str]:
    norm = _normalize(text)
    anchors = []
    if len(norm) <= n * 3:
        anchors.append(norm)
    else:
        anchors.append(norm[:n])
        anchors.append(norm[-n:])
        mid = len(norm) // 2
        anchors.append(norm[mid - n // 2 : mid + n // 2])
        for i in range(0, len(norm), len(norm) // 3):
            anchors.append(norm[i : i + n])
    return list(set(a for a in anchors if len(a) >= 50))


def _match_anchor_in_pages(anchor: str, page_texts: list[str]) -> list[int]:
    hits = []
    for i, pt in enumerate(page_texts):
        if anchor in pt:
            hits.append(i + 1)
    return hits


def _get_confidence(mappings: list[dict], chunk_index: int) -> dict | None:
    for m in mappings:
        if m["chunk_index"] == chunk_index:
            return m
    return None


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one, execute
    from psycopg.rows import dict_row

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
        return 1

    pdf_root = pathlib.Path(args.pdf_root)
    if not pdf_root.is_dir():
        print(f"ERROR: PDF root not found: {pdf_root}", file=sys.stderr)
        return 1

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            cur = conn.cursor()
            await cur.execute("SELECT current_database()")
            db = (await cur.fetchone())["current_database"]
            assert db == "tebaai"

            docs = await fetch_all(
                conn,
                """
                SELECT d.id, d.title, d.source_filename, d.author, c.code
                FROM library_documents d
                JOIN library_collections c ON c.id = d.collection_id
                WHERE c.code = %(code)s AND d.status = 'ready'
                  AND d.title != 'Documento de prueba CLI'
                ORDER BY d.title
                """,
                {"code": args.collection},
            )

            if args.document_title:
                docs = [d for d in docs if args.document_title.lower() in d["title"].lower()]

            all_candidates = []
            all_updates = []

            for doc in docs:
                print(f"Processing: {doc['title'][:50]}...")
                pdf_path = _find_pdf(doc, pdf_root)
                if not pdf_path:
                    print("  PDF not found, skipping")
                    continue

                pdf_doc = fitz.open(str(pdf_path))
                page_count = pdf_doc.page_count
                page_texts = [_normalize(pdf_doc.load_page(p).get_text()) for p in range(page_count)]
                pdf_doc.close()

                chunks = await fetch_all(
                    conn,
                    """
                    SELECT id, chunk_index, content, content_length
                    FROM library_document_chunks
                    WHERE document_id = %(id)s
                    ORDER BY chunk_index
                    """,
                    {"id": str(doc["id"])},
                )

                for chunk in chunks:
                    content: str = chunk.get("content") or ""
                    if not content.strip():
                        continue

                    anchors = _make_anchors(content)
                    page_hits: dict[int, int] = Counter()
                    for anchor in anchors:
                        for p in _match_anchor_in_pages(anchor, page_texts):
                            page_hits[p] += 1

                    if not page_hits:
                        continue

                    best_pages = sorted(page_hits.keys())
                    if len(best_pages) > 1 and (best_pages[-1] - best_pages[0] > 2):
                        continue  # ambiguous

                    total_anchors = len(anchors)
                    max_hits = max(page_hits.values())

                    # Start/end anchor analysis for cross-page detection
                    start_anchors = _make_anchors(content[:min(300, len(content))], n=80)
                    end_anchors = _make_anchors(content[-min(300, len(content)):], n=80)
                    start_pages = set()
                    end_pages = set()
                    for a in start_anchors:
                        start_pages.update(_match_anchor_in_pages(a, page_texts))
                    for a in end_anchors:
                        end_pages.update(_match_anchor_in_pages(a, page_texts))

                    is_high = False
                    page_start = None
                    page_end = None
                    reason = ""

                    if start_pages and end_pages:
                        sp = min(start_pages)
                        ep = max(end_pages)
                        if sp != ep and max_hits >= total_anchors * 0.5:
                            is_high = True
                            page_start = sp
                            page_end = ep
                            reason = f"cross-page: start p{sp} end p{ep}"
                        elif sp == ep and max_hits >= total_anchors * 0.6:
                            is_high = True
                            page_start = sp
                            page_end = sp
                            reason = f"single page p{sp} (hits={max_hits}/{total_anchors})"
                        elif sp == ep and max_hits >= total_anchors * 0.4:
                            # medium - skip
                            pass

                    if not is_high:
                        continue

                    ref_label = f"PDF page {page_start}" if page_start == page_end else f"PDF pages {page_start}-{page_end}"
                    bib_meta = {
                        "page_mapping": {
                            "source": "local_pdf_page_aware_audit",
                            "confidence": "high",
                            "pdf_page_start": page_start,
                            "pdf_page_end": page_end,
                            "page_number_type": "pdf_physical_page",
                            "method": "anchor_match",
                            "audit_tool": "audit_page_chunk_mapping.py",
                            "applied_by": "enrich_chunk_page_metadata.py",
                        }
                    }

                    all_candidates.append({
                        "chunk_id": str(chunk["id"]),
                        "chunk_index": chunk["chunk_index"],
                        "document_title": doc["title"],
                        "page_start": page_start,
                        "page_end": page_end,
                        "reference_label": ref_label,
                        "reason": reason,
                    })
                    all_updates.append({
                        "chunk_id": str(chunk["id"]),
                        "page_start": page_start,
                        "page_end": page_end,
                        "reference_label": ref_label,
                        "bibliographic_metadata": json.dumps(bib_meta),
                    })

                print(f"  pages={page_count} chunks={len(chunks)} high={len(all_candidates)}")

            # Apply limit if set
            if args.limit and len(all_updates) > args.limit:
                all_updates = all_updates[:args.limit]
                all_candidates = all_candidates[:args.limit]

            # Report
            report = {
                "collection": args.collection,
                "mode": "dry-run" if not args.apply else "apply",
                "candidate_count": len(all_candidates),
                "candidates": all_candidates[:20],  # Limit samples in report
                "updates": [],
            }

            if args.apply and all_updates:
                # Execute in transaction
                async with pool.connection() as write_conn:
                    write_conn.row_factory = dict_row
                    try:
                        updated = 0
                        skipped = 0
                        for u in all_updates:
                            # Check if already has page_start
                            existing = await fetch_one(
                                write_conn,
                                "SELECT page_start FROM library_document_chunks WHERE id = %(id)s",
                                {"id": u["chunk_id"]},
                            )
                            if existing and existing.get("page_start") is not None:
                                skipped += 1
                                continue

                            await execute(
                                write_conn,
                                """
                                UPDATE library_document_chunks
                                SET page_start = %(page_start)s,
                                    page_end = %(page_end)s,
                                    reference_label = %(reference_label)s,
                                    bibliographic_metadata = %(bibliographic_metadata)s::jsonb,
                                    updated_at = NOW()
                                WHERE id = %(chunk_id)s
                                """,
                                u,
                            )
                            updated += 1

                        report["mode"] = "apply"
                        report["updated_count"] = updated
                        report["skipped_existing_count"] = skipped
                    except Exception as exc:
                        print(f"ERROR during apply (rolled back): {exc}")
                        return 1

            else:
                report["updated_count"] = 0
                report["skipped_existing_count"] = 0

            report["unmapped_count"] = sum(d["chunk_count"] for d in
                [{"chunk_count": await _count_chunks_by_doc(conn, d["id"])} for d in docs]
            ) - len(all_candidates)

            # Output
            if args.output_json:
                # Remove full candidates from JSON if verbose
                out = dict(report)
                if not args.verbose and "candidates" in out:
                    out["candidates"] = out["candidates"][:5]
                with open(args.output_json, "w", encoding="utf-8") as f:
                    json.dump(out, f, indent=2, ensure_ascii=False, default=str)
                print(f"JSON: {args.output_json}")

            print(f"\n{'='*60}")
            print(f"Page Metadata Enrichment — {args.collection}")
            print(f"{'='*60}")
            print(f"  Mode:         {'DRY-RUN' if not args.apply else 'APPLY'}")
            print(f"  Candidates:   {report['candidate_count']}")
            if args.apply:
                print(f"  Updated:      {report.get('updated_count', 0)}")
                print(f"  Skipped (exists): {report.get('skipped_existing_count', 0)}")

            return 0
    finally:
        await close_pool(pool)


async def _count_chunks_by_doc(conn, doc_id: str) -> int:
    from infrastructure.postgres.transaction import fetch_one
    r = await fetch_one(conn, "SELECT COUNT(*) AS cnt FROM library_document_chunks WHERE document_id = %(id)s", {"id": doc_id})
    return r["cnt"] if r else 0


def _find_pdf(doc: dict, pdf_root: pathlib.Path) -> pathlib.Path | None:
    sf = doc.get("source_filename") or ""
    if sf:
        p = pdf_root / sf
        if p.is_file():
            return p
    title = doc.get("title", "")
    for f in pdf_root.iterdir():
        if f.is_file() and f.suffix.lower() == ".pdf" and title.lower() in f.stem.lower():
            return f
    return None


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
