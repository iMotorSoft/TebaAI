#! /usr/bin/env python3
"""
CLI: Enrich chunks with high-confidence page metadata from PDF audit.

Supports collection breslov (ready docs) and breslov_test (test_candidate).
For test_candidate chunks, preserves existing metadata.section and
metadata.chunking in bibliographic_metadata when writing page_mapping.

Usage:
    uv run python -m scripts.enrich_chunk_page_metadata \\
        --collection breslov_test \\
        --document-title "El Alma del Rebe Najmán" \\
        --strategy normalization_plus --dry-run

    uv run python -m scripts.enrich_chunk_page_metadata \\
        --collection breslov_test \\
        --document-title "El Alma del Rebe Najmán" \\
        --strategy normalization_plus --apply
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
    parser.add_argument("--strategy", default="anchor_match", choices=["anchor_match", "normalization_plus"])
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


def _normalization_plus(text: str) -> str:
    """Enhanced normalization for PDF anchor matching.

    Applies unicode NFKC, lowercase, unaccent, space collapse,
    line-break normalization, dash/hyphen normalization, quote
    normalization, markdown heading stripping, and Sija heading
    normalization.
    """
    import unicodedata
    t = unicodedata.normalize("NFKC", text)
    t = t.lower()
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ü': 'u', 'ñ': 'n', 'Á': 'a', 'É': 'e', 'Í': 'i',
        'Ó': 'o', 'Ú': 'u', 'Ü': 'u', 'Ñ': 'n',
        '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '-',
        '\u2014': '-', '\u2015': '-',
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u00ab': '"', '\u00bb': '"',
    }
    for old, new in replacements.items():
        t = t.replace(old, new)
    # Strip markdown headings
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'\*+', '', t)
    t = re.sub(r'_+', '', t)
    # Normalize Sija headings
    t = re.sub(r'sij[áa]\s+#?\s*(\d+)', r'sija \1', t)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def _make_anchors(text: str, n: int = ANCHOR_CHARS, strategy: str = "anchor_match") -> list[str]:
    norm_fn = _normalization_plus if strategy == "normalization_plus" else _normalize
    norm = norm_fn(text)
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


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one, execute
    from psycopg.rows import dict_row

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: PostgreSQL not enabled via globalVar.py", file=sys.stderr)
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

            # Allow test_candidate docs for *_test collections
            if args.collection.endswith("_test"):
                status_filter = "d.status IN ('ready', 'test_candidate')"
            else:
                status_filter = "d.status = 'ready'"

            docs = await fetch_all(
                conn,
                f"""
                SELECT d.id, d.title, d.source_filename, d.author, c.code
                FROM library_documents d
                JOIN library_collections c ON c.id = d.collection_id
                WHERE c.code = %(code)s AND {status_filter}
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

                norm_fn = _normalization_plus if args.strategy == "normalization_plus" else _normalize

                pdf_doc = fitz.open(str(pdf_path))
                page_count = pdf_doc.page_count
                page_texts = [norm_fn(pdf_doc.load_page(p).get_text()) for p in range(page_count)]
                pdf_doc.close()

                chunks = await fetch_all(
                    conn,
                    """
                    SELECT id, chunk_index, content, content_length, metadata
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

                    anchors = _make_anchors(content, strategy=args.strategy)
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

                    start_anchors = _make_anchors(content[:min(300, len(content))], n=80, strategy=args.strategy)
                    end_anchors = _make_anchors(content[-min(300, len(content)):], n=80, strategy=args.strategy)
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

                    if not is_high:
                        continue

                    # Build reference label with section awareness
                    existing_meta = chunk.get("metadata") or {}
                    section_info = existing_meta.get("section", {})
                    section_label = section_info.get("section_label") or ""
                    section_type = section_info.get("section_type") or ""

                    page_str = f"PDF page {page_start}" if page_start == page_end else f"PDF pages {page_start}-{page_end}"
                    if section_type == "sija" and section_label:
                        ref_label = f"{section_label} · {page_str}"
                    elif section_label:
                        ref_label = f"{section_label} · {page_str}"
                    else:
                        ref_label = page_str

                    # Build bibliographic_metadata preserving section and chunking
                    chunking_info = existing_meta.get("chunking", {})
                    page_mapping_entry = {
                        "page_mapping": {
                            "source": "local_pdf_page_aware_audit",
                            "confidence": "high",
                            "strategy": args.strategy,
                            "pdf_page_start": page_start,
                            "pdf_page_end": page_end,
                            "page_number_type": "pdf_physical_page",
                            "method": "anchor_match",
                            "document_status": "test_candidate" if args.collection.endswith("_test") else "ready",
                            "chunking_strategy": chunking_info.get("strategy", "generic"),
                            "applied_by": "enrich_chunk_page_metadata.py",
                        }
                    }

                    # Merge: preserve existing bib_metadata but add page_mapping
                    bib_base: dict = {}
                    if chunking_info:
                        bib_base["chunking"] = chunking_info
                    if section_info:
                        bib_base["section"] = section_info
                    bib_base.update(page_mapping_entry)
                    bib_meta = json.dumps(bib_base)

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
                        "bibliographic_metadata": bib_meta,
                    })

                print(f"  pages={page_count} chunks={len(chunks)} high={len(all_candidates)}")

            if args.limit and len(all_updates) > args.limit:
                all_updates = all_updates[:args.limit]
                all_candidates = all_candidates[:args.limit]

            report = {
                "collection": args.collection,
                "strategy": args.strategy,
                "mode": "dry-run" if not args.apply else "apply",
                "candidate_count": len(all_candidates),
                "candidates": all_candidates[:20],
                "updates": [],
            }

            if args.apply and all_updates:
                async with pool.connection() as write_conn:
                    write_conn.row_factory = dict_row
                    try:
                        updated = 0
                        skipped = 0
                        for u in all_updates:
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

            if args.output_json:
                out = dict(report)
                if not args.verbose and "candidates" in out:
                    out["candidates"] = out["candidates"][:5]
                with open(args.output_json, "w", encoding="utf-8") as f:
                    json.dump(out, f, indent=2, ensure_ascii=False, default=str)
                print(f"JSON: {args.output_json}")

            print(f"\n{'='*60}")
            print(f"Page Metadata Enrichment — {args.collection} [{args.strategy}]")
            print(f"{'='*60}")
            print(f"  Mode:         {'DRY-RUN' if not args.apply else 'APPLY'}")
            print(f"  Candidates:   {report['candidate_count']}")
            if args.apply:
                print(f"  Updated:      {report.get('updated_count', 0)}")
                print(f"  Skipped (exists): {report.get('skipped_existing_count', 0)}")

            return 0
    finally:
        await close_pool(pool)


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
