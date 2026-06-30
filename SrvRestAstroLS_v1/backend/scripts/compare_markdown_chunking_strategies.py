#! /usr/bin/env python3
"""
CLI: Compare chunking strategies on persisted Markdown from library_document_texts.

Reads Markdown from PostgreSQL (not from PDF). Dry-run only.

Usage:
    uv run python -m scripts.compare_markdown_chunking_strategies \\
        --collection breslov_test \\
        --document-title "Kokhavey Ohr" \\
        --strategies generic,heading-aware,chapter-aware \\
        --output-json /tmp/report.json --output-md /tmp/report.md
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass, field, asdict
from typing import Any
from uuid import UUID, uuid4


DEFAULT_CHUNK_SIZE = 1800
DEFAULT_CHUNK_OVERLAP = 250
DEFAULT_MIN_CHUNK = 200
LARGE_THRESHOLD = 2200
TINY_THRESHOLD = 150


@dataclass
class TempChunk:
    content: str
    char_start: int
    char_end: int
    content_length: int = 0
    section_type: str | None = None
    section_number: int | None = None
    section_label: str | None = None
    section_title: str | None = None
    source_strategy: str = "generic"
    chunk_index: int = 0


@dataclass
class Metrics:
    chunks: int = 0
    avg_chars: float = 0.0
    median_chars: float = 0.0
    min_chars: int = 0
    max_chars: int = 0
    empty_chunks: int = 0
    duplicate_chunks: int = 0
    sections_detected: int = 0
    chunks_with_section_metadata: int = 0
    chunks_crossing_sections: int = 0
    large_chunks: int = 0
    tiny_chunks: int = 0
    total_chars: int = 0
    heading_count: int = 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare Markdown chunking strategies.")
    p.add_argument("--collection", default="breslov_test")
    p.add_argument("--document-title", required=True)
    p.add_argument("--strategies", default="generic,heading-aware")
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    p.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    p.add_argument("--min-chunk", type=int, default=DEFAULT_MIN_CHUNK)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


async def _load_markdown(collection: str, title: str) -> str | None:
    """Fetch persisted Markdown from PostgreSQL."""
    from globalVar import POSTGRES_DSN
    import psycopg

    conn = await psycopg.AsyncConnection.connect(POSTGRES_DSN)
    cur = conn.cursor()
    await cur.execute("""
        SELECT t.content, d.bibliographic_metadata
        FROM library_documents d
        JOIN library_collections c ON c.id = d.collection_id
        JOIN library_document_texts t ON t.document_id = d.id
        WHERE c.code = %s AND d.title = %s
    """, (collection, title))
    row = await cur.fetchone()
    await cur.close()
    await conn.close()
    if row:
        meta = row[1] or {}
        text_extraction = meta.get("text_extraction", {})
        if text_extraction.get("engine") != "pymupdf4llm" or text_extraction.get("format") != "markdown":
            print(f"WARNING: text_extraction={text_extraction} — expected pymupdf4llm/markdown",
                  file=sys.stderr)
        return row[0]
    return None


def _detect_sections(md: str, strategy: str) -> list[dict]:
    """Detect section boundaries based on strategy."""
    sections = []

    if strategy == "heading-aware":
        for m in re.finditer(r'^#{1,3}\s+(.+)', md, re.MULTILINE):
            label = m.group(1).strip()
            sections.append({
                "position": m.start(),
                "type": "heading",
                "number": None,
                "label": label,
                "title": label,
            })

    elif strategy == "chapter-aware":
        for m in re.finditer(r'(?i)^#{0,3}\s*(?:chapter|section|part)\s+(\d+)', md, re.MULTILINE):
            label = m.group(0).strip()
            sections.append({
                "position": m.start(),
                "type": "chapter",
                "number": int(m.group(1)),
                "label": label,
                "title": label,
            })
        for m in re.finditer(r'(?i)^#{0,3}\s*(?:cap[íi]tulo|secci[óo]n)\s+(\d+)', md, re.MULTILINE):
            label = m.group(0).strip()
            sections.append({
                "position": m.start(),
                "type": "chapter",
                "number": int(m.group(1)),
                "label": label,
                "title": label,
            })

    elif strategy == "lesson-aware":
        for m in re.finditer(r'(?i)^#{0,3}\s*(?:lecci[óo]n|lesson|tor[áa]|tora)\s+(\d+)', md, re.MULTILINE):
            label = m.group(0).strip()
            sections.append({
                "position": m.start(),
                "type": "lesson",
                "number": int(m.group(1)),
                "label": label,
                "title": label,
            })

    elif strategy == "section-aware":
        for m in re.finditer(r'^#{1,3}\s+(.+)', md, re.MULTILINE):
            sections.append({
                "position": m.start(),
                "type": "section",
                "number": None,
                "label": m.group(1).strip(),
                "title": m.group(1).strip(),
            })

    return sorted(sections, key=lambda x: x["position"])


def _generic_chunks(md: str, chunk_size: int, overlap: int, min_chunk: int) -> list[TempChunk]:
    """Generic paragraph-based chunking on Markdown."""
    paragraphs = re.split(r'\n\n+', md)
    chunks: list[TempChunk] = []
    current = ""
    start = 0
    idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > chunk_size:
            if len(current) >= min_chunk:
                chunks.append(TempChunk(
                    content=current.strip(), char_start=start, char_end=start + len(current),
                    content_length=len(current), source_strategy="generic", chunk_index=idx,
                ))
                idx += 1
            overlap_text = current[-overlap:] if overlap > 0 and len(current) > overlap else ""
            start = max(0, start + len(current) - overlap)
            current = overlap_text
        if current:
            current += "\n\n" + para
        else:
            current = para
            start = md.find(para)

    if current.strip() and len(current.strip()) >= min_chunk:
        chunks.append(TempChunk(
            content=current.strip(), char_start=start, char_end=start + len(current),
            content_length=len(current), source_strategy="generic", chunk_index=idx,
        ))
    return chunks


def _structure_aware_chunks(md: str, sections: list[dict],
                             chunk_size: int, overlap: int, min_chunk: int,
                             strategy: str) -> list[TempChunk]:
    """Structure-aware chunking using detected section boundaries."""
    if not sections:
        return _generic_chunks(md, chunk_size, overlap, min_chunk)

    chunks: list[TempChunk] = []
    idx = 0

    for i, sec in enumerate(sections):
        sec_start = sec["position"]
        sec_end = sections[i + 1]["position"] if i + 1 < len(sections) else len(md)
        sec_content = md[sec_start:sec_end].strip()

        if not sec_content:
            continue

        sec_type = sec["type"]
        sec_num = sec["number"]
        sec_label = sec.get("label", "") or ""

        # If section is short enough, keep as one chunk
        if len(sec_content) <= chunk_size * 1.2:
            chunks.append(TempChunk(
                content=sec_content, char_start=sec_start, char_end=sec_end,
                content_length=len(sec_content),
                section_type=sec_type, section_number=sec_num,
                section_label=sec_label, section_title=sec_label,
                source_strategy=strategy, chunk_index=idx,
            ))
            idx += 1
        else:
            # Split section content into chunks
            heading_match = re.match(r'(#{1,3}\s+.*?)(?:\n|$)', sec_content)
            heading_line = heading_match.group(1) if heading_match else ""

            remaining = sec_content[len(heading_line):].strip() if heading_line else sec_content
            current = heading_line
            current_start = sec_start
            paras = re.split(r'\n\n+', remaining)

            for para in paras:
                para = para.strip()
                if not para:
                    continue
                if current and len(current) + len(para) + 2 > chunk_size:
                    if len(current) >= min_chunk or (not chunks and heading_line):
                        chunks.append(TempChunk(
                            content=current.strip(),
                            char_start=current_start,
                            char_end=current_start + len(current),
                            content_length=len(current),
                            section_type=sec_type, section_number=sec_num,
                            section_label=sec_label, section_title=sec_label,
                            source_strategy=strategy, chunk_index=idx,
                        ))
                        idx += 1
                    overlap_text = current[-overlap:] if overlap > 0 and len(current) > overlap else ""
                    current_start = max(0, current_start + len(current) - overlap)
                    current = overlap_text
                if current:
                    current += "\n\n" + para
                else:
                    current = para

            if current.strip() and len(current.strip()) >= min_chunk:
                chunks.append(TempChunk(
                    content=current.strip(), char_start=current_start,
                    char_end=current_start + len(current),
                    content_length=len(current),
                    section_type=sec_type, section_number=sec_num,
                    section_label=sec_label, section_title=sec_label,
                    source_strategy=strategy, chunk_index=idx,
                ))
                idx += 1

    return chunks


def _compute_metrics(chunks: list[TempChunk], strategy: str) -> Metrics:
    m = Metrics()
    if not chunks:
        return m

    lengths = [c.content_length for c in chunks]
    m.chunks = len(chunks)
    m.avg_chars = round(statistics.mean(lengths), 1) if lengths else 0.0
    m.median_chars = round(statistics.median(lengths), 1) if lengths else 0.0
    m.min_chars = min(lengths)
    m.max_chars = max(lengths)
    m.empty_chunks = sum(1 for c in lengths if c == 0)
    m.total_chars = sum(lengths)

    seen = set()
    for c in chunks:
        h = hashlib.sha256(c.content.encode()).hexdigest()
        if h in seen:
            m.duplicate_chunks += 1
        seen.add(h)

    detected: set[int] = set()
    for c in chunks:
        if c.section_type and c.section_number is not None:
            detected.add(c.section_number)
            m.chunks_with_section_metadata += 1
        elif c.section_type:
            m.chunks_with_section_metadata += 1

    m.sections_detected = len(detected)

    for i in range(len(chunks) - 1):
        if (chunks[i].section_type and chunks[i + 1].section_type
                and chunks[i].section_number != chunks[i + 1].section_number
                and chunks[i].char_end > chunks[i + 1].char_start):
            m.chunks_crossing_sections += 1

    m.large_chunks = sum(1 for c in lengths if c > LARGE_THRESHOLD)
    m.tiny_chunks = sum(1 for c in lengths if c < TINY_THRESHOLD)

    # Count headings in markdown
    m.heading_count = len(re.findall(r'^#{1,3}\s+', (chunks[0].content if chunks else ""), re.MULTILINE))

    return m


async def _run(args: argparse.Namespace) -> int:
    md = await _load_markdown(args.collection, args.document_title)
    if md is None:
        print(f"ERROR: Document '{args.document_title}' not found in '{args.collection}'", file=sys.stderr)
        return 1

    print(f"Markdown: {len(md):,} chars, {md.count(chr(10)):,} lines")
    print(f"Document: {args.document_title} @ {args.collection}")

    strategies = [s.strip() for s in args.strategies.split(",")]
    results = {}

    for strat in strategies:
        if args.verbose:
            print(f"\n  Strategy: {strat}")

        if strat == "generic":
            chunks = _generic_chunks(md, args.chunk_size, args.chunk_overlap, args.min_chunk)
        else:
            sections = _detect_sections(md, strat)
            if args.verbose:
                print(f"    Sections detected: {len(sections)}")
            chunks = _structure_aware_chunks(md, sections, args.chunk_size, args.chunk_overlap, args.min_chunk, strat)

        metrics = _compute_metrics(chunks, strat)
        results[strat] = asdict(metrics)
        results[strat]["chunks_count"] = metrics.chunks
        if args.verbose:
            print(f"    Chunks: {metrics.chunks}, avg={metrics.avg_chars}, "
                  f"section_meta={metrics.chunks_with_section_metadata}, "
                  f"crossing={metrics.chunks_crossing_sections}")

    report = {
        "collection": args.collection,
        "document_title": args.document_title,
        "markdown_chars": len(md),
        "strategies": results,
    }

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"JSON: {args.output_json}")

    if args.output_md:
        _write_md(report, args.output_md)

    print(f"\n── Comparison complete (dry-run) ──")
    for s, r in results.items():
        print(f"  {s}: {r['chunks']} chunks, avg={r['avg_chars']}, "
              f"sections={r['sections_detected']}, meta={r['chunks_with_section_metadata']}, "
              f"cross={r['chunks_crossing_sections']}")

    return 0


def _write_md(report: dict, path: str) -> None:
    lines = [
        f"# Markdown Chunking Strategy: {report['document_title']}",
        "",
        f"**Collection**: {report['collection']}",
        f"**Markdown chars**: {report['markdown_chars']:,}",
        "",
        "## Strategies",
        "",
        "| Strategy | Chunks | Avg chars | Max chars | Sections | Section meta | Crossing |",
        "|----------|------:|----------:|----------:|--------:|------------:|--------:|",
    ]
    for s, r in sorted(report["strategies"].items()):
        lines.append(
            f"| {s} | {r['chunks']} | {r['avg_chars']} | {r['max_chars']} "
            f"| {r['sections_detected']} | {r['chunks_with_section_metadata']} "
            f"| {r['chunks_crossing_sections']} |"
        )
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"MD: {path}")


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
