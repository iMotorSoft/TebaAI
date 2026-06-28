#! /usr/bin/env python3
"""
CLI: Audit bibliographic metadata structure of loaded documents.

Reads from PostgreSQL only. Does NOT write to DB, Milvus, or files.
Reports page markers, heading candidates, chunk quality, and metadata gaps.

Usage:
    uv run python -m scripts.audit_bibliographic_structure --collection breslov
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
from collections import Counter
from typing import Any

HEADING_PATTERNS = [
    r"^#\s+", r"^##\s+", r"^###\s+",
    r"^CAP[IÍ]TULO\s", r"^Cap[íi]tulo\s",
    r"^LECCI[OÓ]N\s", r"^Lecci[óo]n\s",
    r"^HALAJ[ÁA]\s", r"^Halaj[áa]\s",
    r"^INTRODUCCI[OÓ]N", r"^Introducci[óo]n",
    r"^PREFACIO", r"^Prefacio",
    r"^PR[OÓ]LOGO", r"^Pr[óo]logo",
]

PAGE_PATTERNS = [
    r"(?i)p[áa]gina\s+\d+", r"(?i)page\s+\d+",
    r"-\s*\d+\s*-", r"\[\d+\]",
    r"^\d+\s*$",
]

CHAPTER_PATTERNS = [
    r"(?i)cap[íi]tulo\s+\d+", r"(?i)lecci[óo]n\s+\d+",
    r"(?i)halaj[áa]\s+\d+", r"(?i)sim[aá]n\s+\d+",
]

PDF_DIR = pathlib.Path("/media/issajar/DEVELOP/Download/Tora/Breslov")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit bibliographic metadata structure.")
    parser.add_argument("--collection", default="breslov", help="Collection code")
    parser.add_argument("--output-md", help="Path to write Markdown report")
    parser.add_argument("--output-json", help="Path to write JSON report")
    parser.add_argument("--sample-lines", type=int, default=5, help="Sample lines per document")
    parser.add_argument("--max-heading-candidates", type=int, default=30)
    parser.add_argument("--max-page-markers", type=int, default=30)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from psycopg.rows import dict_row

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
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

            docs = await _get_documents(conn, args.collection)
            audit_docs = []
            for doc in docs:
                audit_doc = await _audit_document(conn, doc, args)
                audit_docs.append(audit_doc)

            # Build report
            report = {
                "collection": args.collection,
                "total_documents": len(docs),
                "total_chunks": sum(d["chunk_count"] for d in audit_docs),
                "documents": audit_docs,
                "existing_metadata_summary": _summarize_metadata(audit_docs),
                "pdf_availability": _check_pdfs(),
            }

            # Output
            if args.output_json:
                with open(args.output_json, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, ensure_ascii=False, default=str)
                print(f"JSON report: {args.output_json}")

            if args.output_md:
                md = _build_markdown(report, args)
                with open(args.output_md, "w", encoding="utf-8") as f:
                    f.write(md)
                print(f"MD report:   {args.output_md}")

            # Console summary
            print(f"\n{'='*60}")
            print(f"Bibliographic Structure Audit — Collection: {args.collection}")
            print(f"{'='*60}")
            print(f"Documents: {len(docs)}")
            for ad in audit_docs:
                print(f"\n  {ad['title'][:50]}")
                print(f"    Chunks: {ad['chunk_count']}")
                print(f"    Page fields available: {ad['existing_metadata']['page_fields_available']}")
                print(f"    Chunks with page: {ad['existing_metadata']['chunks_with_page']}")
                print(f"    Chunks with chapter: {ad['existing_metadata']['chunks_with_chapter']}")
                print(f"    Page markers found: {len(ad['page_marker_candidates'])}")
                print(f"    Heading candidates found: {len(ad['heading_candidates'])}")
                print(f"    Confidence: {ad['confidence']}")
                print(f"    Strategy: {ad['recommended_strategy']}")

            return 0
    finally:
        await close_pool(pool)


async def _get_documents(conn, collection: str) -> list[dict]:
    from infrastructure.postgres.transaction import fetch_all
    return await fetch_all(
        conn,
        """
        SELECT d.id, d.title, d.source_uri, d.language, d.author,
               d.source_filename,
               COUNT(ch.id) AS chunk_count
        FROM library_documents d
        JOIN library_collections c ON c.id = d.collection_id
        LEFT JOIN library_document_chunks ch ON ch.document_id = d.id
        WHERE c.code = %(code)s AND d.status = 'ready'
        GROUP BY d.id, d.title, d.source_uri, d.language, d.author, d.source_filename
        ORDER BY d.title
        """,
        {"code": collection},
    )


async def _audit_document(conn, doc: dict, args: argparse.Namespace) -> dict[str, Any]:
    from infrastructure.postgres.transaction import fetch_one, fetch_all
    doc_id = doc["id"]

    # Full text content
    text_row = await fetch_one(
        conn,
        "SELECT content FROM library_document_texts WHERE document_id = %(id)s LIMIT 1",
        {"id": str(doc_id)},
    )
    content = (text_row or {}).get("content") or ""

    # Chunk analysis
    chunks = await fetch_all(
        conn,
        """
        SELECT chunk_index, content, content_length, char_start, char_end,
               page_start, page_end, chapter, section, metadata
        FROM library_document_chunks WHERE document_id = %(id)s
        ORDER BY chunk_index
        """,
        {"id": str(doc_id)},
    )

    chunk_count = len(chunks)
    chunks_with_page = sum(1 for c in chunks if c.get("page_start") is not None or c.get("page_end") is not None)
    chunks_with_chapter = sum(1 for c in chunks if c.get("chapter") is not None)
    chunks_with_section = sum(1 for c in chunks if c.get("section") is not None)

    content_lines = content.split("\n")
    sample_lines = content_lines[:max(1, args.sample_lines)]

    # Detect page markers
    import re
    page_markers = set()
    for line in content_lines:
        for pat in PAGE_PATTERNS:
            m = re.search(pat, line.strip())
            if m:
                page_markers.add(m.group().strip()[:80])
                break
    page_markers_list = sorted(page_markers)[:max(1, args.max_page_markers)]

    # Detect heading candidates
    heading_candidates = []
    heading_set = set()
    for line in content_lines:
        stripped = line.strip()
        if not stripped:
            continue
        for pat in HEADING_PATTERNS:
            if re.match(pat, stripped):
                heading_set.add(stripped[:120])
                break
    heading_candidates = sorted(heading_set)[:max(1, args.max_heading_candidates)]

    # Detect chapter patterns
    chapter_refs = set()
    for line in content_lines:
        for pat in CHAPTER_PATTERNS:
            m = re.search(pat, line)
            if m:
                chapter_refs.add(m.group()[:80])
    chapter_refs_list = sorted(chapter_refs)[:20]

    # Chunk quality observations
    chunk_obs = []
    lengths = [c["content_length"] for c in chunks if c["content_length"]]
    if lengths:
        avg = sum(lengths) / len(lengths)
        max_len = max(lengths)
        min_len = min(lengths)
        if min_len < 100:
            chunk_obs.append(f"{sum(1 for l in lengths if l < 100)} very short chunks (<100 chars)")
        if max_len > 5000:
            chunk_obs.append(f"{sum(1 for l in lengths if l > 5000)} very long chunks (>5000 chars)")

    # Content length
    content_length = len(content)

    # Determine confidence and strategy
    has_pages = chunks_with_page > chunk_count * 0.5
    has_chapters = chunks_with_chapter > chunk_count * 0.3
    has_page_markers = len(page_markers_list) > 5
    has_heading_candidates = len(heading_candidates) > 5

    if has_pages or (has_page_markers and has_heading_candidates):
        confidence = "medium"
        strategy = "Enrich chunks using existing page markers and heading structure"
    elif has_heading_candidates:
        confidence = "medium"
        strategy = "Infer chapter/section from heading candidates, pages from PDF re-extraction"
    elif has_page_markers:
        confidence = "low"
        strategy = "Pages detectable but unreliable; re-extract with page-aware chunking from PDF"
    else:
        confidence = "low"
        strategy = "Re-extract PDF with page-aware chunking using pymupdf4llm page ranges"

    return {
        "title": doc["title"],
        "author": doc.get("author"),
        "source_filename": doc.get("source_filename"),
        "content_length": content_length,
        "chunk_count": chunk_count,
        "existing_metadata": {
            "page_fields_available": chunks_with_page > 0,
            "chunks_with_page": chunks_with_page,
            "chunks_with_chapter": chunks_with_chapter,
            "chunks_with_section": chunks_with_section,
            "page_start_end_exists_in_db": True if chunks and chunks[0].get("page_start") is not None else False,
        },
        "page_marker_candidates": page_markers_list,
        "heading_candidates": heading_candidates,
        "chapter_references": chapter_refs_list,
        "sample_content_start": "\n".join(sample_lines)[:500] if sample_lines else "",
        "chunking_observations": chunk_obs,
        "chunk_lengths": {
            "avg": round(sum(lengths) / len(lengths), 1) if lengths else 0,
            "min": min_len if lengths else 0,
            "max": max_len if lengths else 0,
        },
        "confidence": confidence,
        "recommended_strategy": strategy,
    }


def _summarize_metadata(audit_docs: list[dict]) -> dict:
    total_chunks = sum(d["chunk_count"] for d in audit_docs)
    total_with_page = sum(d["existing_metadata"]["chunks_with_page"] for d in audit_docs)
    total_with_chapter = sum(d["existing_metadata"]["chunks_with_chapter"] for d in audit_docs)
    return {
        "total_chunks": total_chunks,
        "chunks_with_page": total_with_page,
        "chunks_with_chapter": total_with_chapter,
        "pct_with_page": round(total_with_page / total_chunks * 100, 1) if total_chunks else 0,
        "pct_with_chapter": round(total_with_chapter / total_chunks * 100, 1) if total_chunks else 0,
        "fields_available": {
            "page_start": audit_docs[0]["existing_metadata"]["page_start_end_exists_in_db"] if audit_docs else False,
            "chapter": audit_docs[0]["existing_metadata"]["chunks_with_chapter"] > 0 if audit_docs else False,
            "section": audit_docs[0]["existing_metadata"]["chunks_with_section"] > 0 if audit_docs else False,
        },
    }


def _check_pdfs() -> dict:
    expected = [
        "El Jardin de las Almas (Spanish - Rebe Najman de Breslov.pdf",
        "LA POTENCIA DE LA PLEGARIA Interior Print.pdf",
        "LIKUTEY HALAJOT LM II 8.pdf",
    ]
    results = {}
    for fname in expected:
        path = PDF_DIR / fname
        if path.is_file():
            results[fname] = {"exists": True, "size_bytes": path.stat().st_size}
        else:
            results[fname] = {"exists": False}
    return {"directory": str(PDF_DIR), "files": results}


def _build_markdown(report: dict, args: argparse.Namespace) -> str:
    lines = [
        "# TebaAI Breslov Bibliographic Structure Audit",
        "",
        f"**Collection:** {report['collection']}  "
        f"**Documents:** {report['total_documents']}  "
        f"**Total chunks:** {report['total_chunks']}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Field | Coverage |",
        "|-------|----------|",
    ]
    sm = report["existing_metadata_summary"]
    lines.append(f"| Chunks with page | {sm['chunks_with_page']}/{sm['total_chunks']} ({sm['pct_with_page']}%) |")
    lines.append(f"| Chunks with chapter | {sm['chunks_with_chapter']}/{sm['total_chunks']} ({sm['pct_with_chapter']}%) |")

    lines.extend(["", "| Field available in DB | Status |",
                  "|------------------------|--------|"])
    for field, avail in sm["fields_available"].items():
        status = "YES" if avail else "NO"
        lines.append(f"| `{field}` | {status} |")

    lines.extend(["", "## Documents", ""])
    for ad in report["documents"]:
        lines.extend([
            f"### {ad['title']}",
            "",
            f"- **Author:** {ad['author'] or 'N/A'}",
            f"- **Chunks:** {ad['chunk_count']}",
            f"- **Content length:** {ad['content_length']} chars",
            f"- **Confidence:** {ad['confidence']}",
            f"- **Strategy:** {ad['recommended_strategy']}",
            "",
            "#### Existing metadata",
            f"- Page fields: **{'YES' if ad['existing_metadata']['page_fields_available'] else 'NO'}** "
            f"({ad['existing_metadata']['chunks_with_page']} chunks have page)",
            f"- Chapter fields: {ad['existing_metadata']['chunks_with_chapter']} chunks have chapter",
            f"- Section fields: {ad['existing_metadata']['chunks_with_section']} chunks have section",
            "",
        ])
        if ad["page_marker_candidates"]:
            lines.extend(["#### Page marker candidates", ""])
            for m in ad["page_marker_candidates"][:10]:
                lines.append(f"  - `{m}`")
            lines.append("")
        if ad["heading_candidates"]:
            lines.extend(["#### Heading candidates", ""])
            for h in ad["heading_candidates"][:15]:
                lines.append(f"  - `{h[:80]}`")
            lines.append("")
        if ad["chunking_observations"]:
            lines.extend(["#### Chunking observations", ""])
            for obs in ad["chunking_observations"]:
                lines.append(f"  - {obs}")
            lines.append("")
        lines.append(f"**Chunk lengths:** avg={ad['chunk_lengths']['avg']}, min={ad['chunk_lengths']['min']}, max={ad['chunk_lengths']['max']}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## PDF Availability",
        "",
        f"Directory: {report['pdf_availability']['directory']}",
        "",
        "| File | Exists | Size |",
        "|------|--------|------|",
    ])
    for fname, info in report["pdf_availability"]["files"].items():
        size = f"{info['size_bytes']:,} bytes" if info["exists"] else "NOT FOUND"
        status = "YES" if info["exists"] else "NO"
        lines.append(f"| {fname[:60]} | {status} | {size} |")

    lines.extend([
        "",
        "---",
        "",
        "## Risks",
        "",
        "- Page markers from extracted text may be unreliable.",
        "- Heading detection is heuristic; not all headings are structural chapters.",
        "- PDF re-extraction would overwrite or duplicate existing chunks.",
        "- Enrichment requires careful merge strategy to avoid duplicating vectors.",
        "",
        "## Recommended next phase",
        "",
        "Enrich chunks with bibliographic metadata (page, chapter, section) by",
        "re-extracting PDFs with page-range awareness, then updating chunk records",
        "without duplicating content or losing existing FTS/vector state.",
    ])
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
