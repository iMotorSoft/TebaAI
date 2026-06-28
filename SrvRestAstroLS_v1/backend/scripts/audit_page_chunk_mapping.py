#! /usr/bin/env python3
"""
CLI: Audit page↔chunk mapping using PDF page-level extraction.

Reads PDFs page-by-page via PyMuPDF, matches existing chunks to page
ranges using text anchors. Reports confidence, ambiguities, and
heading candidates. Does NOT write to DB.

Usage:
    uv run python -m scripts.audit_page_chunk_mapping --collection breslov
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
HEADING_PATTERNS = [
    r"^#\s+", r"^##\s+", r"^###\s+",
    r"(?i)^cap[íi]tulo\s+\d+", r"(?i)^lecci[óo]n\s+\d+",
    r"(?i)^halaj[áa]\s+\d+", r"(?i)^sim[aá]n\s+\d+",
    r"(?i)^introducci[óo]n", r"^PREFACIO", r"^Prefacio",
    r"(?i)^pr[óo]logo",
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit page↔chunk mapping.")
    parser.add_argument("--collection", default="breslov")
    parser.add_argument("--pdf-root", default="/media/issajar/DEVELOP/Download/Tora/Breslov")
    parser.add_argument("--output-md", help="Path to Markdown report")
    parser.add_argument("--output-json", help="Path to JSON report")
    parser.add_argument("--sample-size", type=int, default=5, help="Sample mappings per document")
    parser.add_argument("--max-unmapped-samples", type=int, default=10)
    parser.add_argument("--max-heading-candidates", type=int, default=40)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def _normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _make_anchors(text: str, n: int = ANCHOR_CHARS) -> list[str]:
    """Generate text anchors from chunk content."""
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
    """Find which pages contain the anchor text."""
    hits = []
    for i, pt in enumerate(page_texts):
        if anchor in pt:
            hits.append(i + 1)
    return hits


def _detect_headings(text: str) -> list[str]:
    candidates = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        for pat in HEADING_PATTERNS:
            if re.match(pat, s):
                candidates.append(s[:120])
                break
    return candidates


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_all, fetch_one
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

            report_docs = []
            for doc in docs:
                print(f"Processing: {doc['title'][:50]}...")
                pdf_path = _find_pdf(doc, pdf_root)
                if not pdf_path:
                    print(f"  PDF not found, skipping")
                    continue

                # Read PDF pages
                pdf_doc = fitz.open(str(pdf_path))
                page_count = pdf_doc.page_count
                page_texts = []
                page_heading_candidates = set()
                for p in range(page_count):
                    text = pdf_doc.load_page(p).get_text()
                    norm = _normalize(text)
                    page_texts.append(norm)
                    for h in _detect_headings(text):
                        page_heading_candidates.add(h)
                pdf_doc.close()

                # Read chunks
                chunks = await fetch_all(
                    conn,
                    """
                    SELECT id, chunk_index, content, content_length,
                           char_start, char_end
                    FROM library_document_chunks
                    WHERE document_id = %(id)s
                    ORDER BY chunk_index
                    """,
                    {"id": str(doc["id"])},
                )

                # Match each chunk to pages
                mappings = []
                for chunk in chunks:
                    cid = str(chunk["id"])
                    content: str = chunk.get("content") or ""
                    if not content.strip():
                        mappings.append({"chunk_id": cid, "chunk_index": chunk["chunk_index"],
                                         "page_start": None, "page_end": None,
                                         "confidence": "none", "reason": "empty content"})
                        continue

                    anchors = _make_anchors(content)
                    page_hits: dict[int, int] = Counter()
                    for anchor in anchors:
                        for p in _match_anchor_in_pages(anchor, page_texts):
                            page_hits[p] += 1

                    if not page_hits:
                        mappings.append({"chunk_id": cid, "chunk_index": chunk["chunk_index"],
                                         "page_start": None, "page_end": None,
                                         "confidence": "none", "reason": "no anchor matched"})
                        continue

                    best_pages = sorted(page_hits.keys())
                    max_hits = max(page_hits.values())
                    total_anchors = len(anchors)

                    # Check ambiguity: anchors spread across non-adjacent pages
                    if len(best_pages) > 1 and (best_pages[-1] - best_pages[0] > 2):
                        # Ambiguous
                        mappings.append({"chunk_id": cid, "chunk_index": chunk["chunk_index"],
                                         "page_start": best_pages[0], "page_end": best_pages[-1],
                                         "confidence": "low", "reason": f"ambiguous: pages {best_pages[0]}-{best_pages[-1]}"})
                        continue

                    # Check if start anchor and end anchor map to different pages
                    start_anchors = _make_anchors(content[:min(300, len(content))], n=80)
                    end_anchors = _make_anchors(content[-min(300, len(content)):], n=80)
                    start_pages = set()
                    end_pages = set()
                    for a in start_anchors:
                        start_pages.update(_match_anchor_in_pages(a, page_texts))
                    for a in end_anchors:
                        end_pages.update(_match_anchor_in_pages(a, page_texts))

                    if start_pages and end_pages:
                        sp = min(start_pages)
                        ep = max(end_pages)
                        if sp != ep and max_hits >= total_anchors * 0.5:
                            mappings.append({"chunk_id": cid, "chunk_index": chunk["chunk_index"],
                                             "page_start": sp, "page_end": ep,
                                             "confidence": "high" if sp != ep else "medium",
                                             "reason": f"cross-page: start p{sp} end p{ep}"})
                            continue
                        elif sp == ep:
                            mappings.append({"chunk_id": cid, "chunk_index": chunk["chunk_index"],
                                             "page_start": sp, "page_end": sp,
                                             "confidence": "high" if max_hits >= total_anchors * 0.6 else "medium",
                                             "reason": f"single page p{sp} (hits={max_hits}/{total_anchors})"})
                            continue

                    # Fallback: use best page
                    bp = best_pages[0]
                    mappings.append({"chunk_id": cid, "chunk_index": chunk["chunk_index"],
                                     "page_start": bp, "page_end": bp,
                                     "confidence": "medium" if max_hits >= total_anchors * 0.4 else "low",
                                     "reason": f"best page p{bp} (hits={max_hits}/{total_anchors})"})

                # Compute coverage
                by_conf = Counter(m["confidence"] for m in mappings)
                ambiguous = sum(1 for m in mappings if "ambiguous" in m.get("reason", ""))
                unmapped = sum(1 for m in mappings if m["confidence"] == "none")
                useful = sum(1 for m in mappings if m["confidence"] in ("high", "medium"))

                samples = [m for m in mappings if m["confidence"] in ("high", "medium")][:args.sample_size]
                unmapped_samples = [m for m in mappings if m["confidence"] == "none"][:args.max_unmapped_samples]

                heading_list = sorted(page_heading_candidates)[:args.max_heading_candidates]

                report_docs.append({
                    "title": doc["title"],
                    "author": doc.get("author"),
                    "source_filename": doc.get("source_filename"),
                    "pdf_path": str(pdf_path),
                    "pdf_found": True,
                    "pdf_page_count": page_count,
                    "chunk_count": len(chunks),
                    "mapped_chunks": len(chunks) - unmapped,
                    "unmapped_chunks": unmapped,
                    "ambiguous_chunks": ambiguous,
                    "coverage": {
                        "high": by_conf.get("high", 0),
                        "medium": by_conf.get("medium", 0),
                        "low": by_conf.get("low", 0),
                        "none": by_conf.get("none", 0),
                    },
                    "useful_coverage_pct": round(useful / len(chunks) * 100, 1) if chunks else 0,
                    "heading_candidates": heading_list,
                    "sample_mappings": samples,
                    "unmapped_samples": unmapped_samples,
                })
                print(f"  pages={page_count} chunks={len(chunks)} useful={useful}/{len(chunks)} ({round(useful/len(chunks)*100,1)}%)")

        # Build report
        report = {
            "collection": args.collection,
            "pdf_root": str(pdf_root),
            "documents": report_docs,
            "summary": _summarize(report_docs),
        }

        # Output
        if args.output_json:
            _write_json(report, args.output_json)
        if args.output_md:
            _write_md(report, args.output_md)

        # Console
        print(f"\n{'='*60}")
        print(f"Page-Chunk Mapping Audit — {args.collection}")
        print(f"{'='*60}")
        for d in report_docs:
            print(f"\n  {d['title'][:50]}")
            print(f"    PDF pages: {d['pdf_page_count']:4d}  Chunks: {d['chunk_count']:4d}")
            print(f"    Coverage:  H={d['coverage']['high']:4d} M={d['coverage']['medium']:4d} L={d['coverage']['low']:4d} N={d['coverage']['none']:4d}")
            print(f"    Useful:    {d['useful_coverage_pct']}%  Ambiguous: {d['ambiguous_chunks']}")
        print(f"\n  TOTAL: {report['summary']['total_chunks']} chunks, {report['summary']['useful_pct']}% useful coverage")

        return 0
    finally:
        await close_pool(pool)


def _find_pdf(doc: dict, pdf_root: pathlib.Path) -> pathlib.Path | None:
    """Find PDF file for document by matching source_filename or title."""
    sf = doc.get("source_filename") or ""
    if sf:
        p = pdf_root / sf
        if p.is_file():
            return p
    # Try matching by title in filename
    title = doc.get("title", "")
    for f in pdf_root.iterdir():
        if f.is_file() and f.suffix.lower() == ".pdf" and title.lower() in f.stem.lower():
            return f
    return None


def _summarize(docs: list[dict]) -> dict:
    tc = sum(d["chunk_count"] for d in docs)
    tu = sum(d["coverage"]["high"] + d["coverage"]["medium"] for d in docs)
    return {"total_chunks": tc, "useful_chunks": tu, "useful_pct": round(tu / tc * 100, 1) if tc else 0}


def _write_json(report: dict, path: str) -> None:
    class _Encoder(json.JSONEncoder):
        def default(self, o):
            return str(o) if isinstance(o, (set, bytes)) else super().default(o)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, cls=_Encoder)
    print(f"JSON: {path}")


def _write_md(report: dict, path: str) -> None:
    lines = [
        "# TebaAI Breslov Page ↔ Chunk Mapping Audit",
        "",
        f"**Collection:** {report['collection']}  **PDF root:** {report['pdf_root']}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"Total chunks: {report['summary']['total_chunks']}  "
        f"Useful coverage (high+medium): {report['summary']['useful_pct']}%",
        "",
    ]
    for d in report["documents"]:
        lines.extend([
            f"### {d['title']}",
            "",
            f"- **PDF:** {d['pdf_page_count']} pages, found: {d['pdf_found']}",
            f"- **Chunks:** {d['chunk_count']} mapped: {d['mapped_chunks']} "
            f"unmapped: {d['unmapped_chunks']} ambiguous: {d['ambiguous_chunks']}",
            f"- **Coverage:** H={d['coverage']['high']} M={d['coverage']['medium']} "
            f"L={d['coverage']['low']} N={d['coverage']['none']}",
            f"- **Useful:** {d['useful_coverage_pct']}%",
            "",
        ])
        if d["heading_candidates"]:
            lines.extend(["#### Heading candidates", ""])
            for h in d["heading_candidates"][:20]:
                lines.append(f"  - `{h[:80]}`")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## Risks",
        "",
        "- Mapping depends on text extraction quality from PyMuPDF.",
        "- Ambiguous chunks may cross structural boundaries.",
        "- Low-confidence chunks should not be enriched without review.",
        "- Page numbers are physical PDF pages, not printed book pages.",
        "",
        "## Recommended enrichment plan",
        "",
        "1. Enrich high-confidence mapped chunks first.",
        "2. Validate medium-confidence chunks by sampling.",
        "3. Re-extract/chunk low-confidence documents with page-range awareness.",
        "4. Never invent page numbers or chapter labels.",
    ])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"MD:   {path}")


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
