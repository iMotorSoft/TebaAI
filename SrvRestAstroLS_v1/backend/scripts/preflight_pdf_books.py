#! /usr/bin/env python3
"""
CLI: Preflight PDF books — read-only audit of structure, text quality, language.

Usage:
    uv run python -m scripts.preflight_pdf_books \\
        --pdf "/path/to/book1.pdf" --pdf "/path/to/book2.pdf" \\
        --output-json /tmp/preflight.json --output-md /tmp/preflight.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight PDF books (read-only).")
    parser.add_argument("--pdf", action="append", required=True, help="PDF path (repeatable)")
    parser.add_argument("--output-json", help="Write JSON report")
    parser.add_argument("--output-md", help="Write Markdown report")
    parser.add_argument("--sample-chars", type=int, default=300, help="Max chars per sample")
    return parser.parse_args(argv)


def _detect_language(text: str) -> str:
    """Basic language detection based on character frequency."""
    if not text.strip():
        return "unknown"
    en_score = 0
    es_score = 0
    he_score = 0
    for ch in text[:3000]:
        if "a" <= ch <= "z" or "A" <= ch <= "Z":
            en_score += 1
        if ch in "áéíóúüñÁÉÍÓÚÜÑ":
            es_score += 1
        elif ch in "¿¡":
            es_score += 2
        if "\u05d0" <= ch <= "\u05ea":
            he_score += 1
    if he_score > max(en_score, es_score):
        return "he"
    if es_score > 5 and es_score > en_score * 0.03:
        return "es"
    if en_score > 0:
        return "en"
    return "unknown"


def _detect_structure(text: str, language: str) -> dict:
    """Detect structural signals in text."""
    lines = text.split("\n")
    headings = []
    chapter_count = 0
    lesson_count = 0
    section_count = 0
    index_lines = 0
    footnote_signals = 0
    introduction_signals = False
    glossary_signals = False

    heading_patterns = [
        r"^#{1,3}\s+",           # Markdown heading
        r"^[A-Z][A-Z\s]{2,}$",   # ALL CAPS line
        r"^\d+\.\s+[A-Z]",       # Numbered heading
    ]

    for line in lines:
        s = line.strip()
        if not s:
            continue
        for pat in heading_patterns:
            if re.match(pat, s):
                headings.append(s[:80])
                break

        if language == "en":
            if re.match(r"(?i)^chapter\s+\d+", s):
                chapter_count += 1
            elif re.match(r"(?i)^section\s+\d+", s):
                section_count += 1
            elif re.match(r"(?i)^lesson\s+\d+", s):
                lesson_count += 1
            elif re.match(r"(?i)^(introduction|preface|appendix|index|glossary)", s):
                if re.match(r"(?i)^introduction|preface|appendix", s):
                    introduction_signals = True
                if re.match(r"(?i)^(glossary|index)", s):
                    glossary_signals = True
        else:
            if re.match(r"(?i)^(cap[íi]tulo|lecci[óo]n|tor[áa]|secci[óo]n)\s+\d+", s):
                chapter_count += 1
            if re.match(r"(?i)^(introducci[óo]n|pr[oó]logo|ap[eé]ndice|[íi]ndice|glosario)", s):
                introduction_signals = True
            if re.match(r"(?i)^(glosario|bibliograf[íi]a|ap[eé]ndice)", s):
                glossary_signals = True

        if re.search(r"(?i)\b(footnote|^\[note|^[0-9]+\s)", s[:30]):
            footnote_signals += 1

    return {
        "total_lines": len(lines),
        "heading_candidates": len(headings),
        "headings_sample": headings[:20],
        "chapter_count": chapter_count,
        "lesson_count": lesson_count,
        "section_count": section_count,
        "index_lines": index_lines,
        "footnote_signals": footnote_signals,
        "introduction_signals": introduction_signals,
        "glossary_signals": glossary_signals,
        "has_outline": False,
    }


def _preflight_pdf(pdf_path: pathlib.Path, sample_chars: int = 300) -> dict:
    import pymupdf as fitz

    doc = fitz.open(str(pdf_path))
    page_count = doc.page_count
    metadata = doc.metadata
    outline = doc.get_toc(simple=True)

    all_text = ""
    page_texts = []
    empty_pages = 0
    samples = []

    for i in range(page_count):
        page = doc.load_page(i)
        text = page.get_text()
        page_texts.append(text)
        all_text += text + "\n"

        if not text.strip():
            empty_pages += 1
            continue

        if len(samples) < 3 or i >= page_count - 3:
            samples.append({
                "page": i + 1,
                "text": text[:sample_chars],
            })

    total_chars = len(all_text)
    total_words = len(all_text.split())
    avg_chars_per_page = total_chars / max(1, page_count - empty_pages)
    language = _detect_language(all_text)
    structure = _detect_structure(all_text, language)

    # Look for table of contents by finding "contents" or "indice"
    toc_detected = False
    for t in page_texts[:5]:
        if re.search(r"(?i)\b(contents|table of contents|índice|indice)\b", t[:500]):
            toc_detected = True
            break

    # Estimate if OCR needed (very low text density = likely scanned)
    avg_empty_page_chars = total_chars / max(1, page_count)
    needs_ocr = avg_empty_page_chars < 100

    doc.close()

    return {
        "filename": pdf_path.name,
        "path": str(pdf_path),
        "file_size_bytes": pdf_path.stat().st_size,
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "page_count": page_count,
        "pdf_metadata": {k: v for k, v in metadata.items() if v},
        "outline_count": len(outline),
        "outline_sample": outline[:20] if outline else [],
        "total_chars": total_chars,
        "total_words": total_words,
        "empty_pages": empty_pages,
        "avg_chars_per_page": round(avg_chars_per_page, 1),
        "avg_chars_per_nonempty_page": round(avg_chars_per_page, 1),
        "detected_language": language,
        "needs_ocr": needs_ocr,
        "toc_detected": toc_detected,
        "structure": structure,
        "samples": samples,
    }


async def _run(args: argparse.Namespace) -> int:
    results = []
    for pdf_arg in args.pdf:
        path = pathlib.Path(pdf_arg)
        if not path.is_file():
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            return 1
        print(f"Processing: {path.name}...")
        r = _preflight_pdf(path, sample_chars=args.sample_chars)
        results.append(r)
        print(f"  pages={r['page_count']} chars={r['total_chars']} lang={r['detected_language']} "
              f"empty={r['empty_pages']} toc={'yes' if r['toc_detected'] else 'no'}")

    report = {
        "books": results,
        "total_books": len(results),
    }

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"JSON: {args.output_json}")

    if args.output_md:
        _write_md(report, args.output_md)

    return 0


def _write_md(report: dict, path: str) -> None:
    lines = ["# Breslov PDF Books Preflight", "", f"**Total books:** {report['total_books']}", ""]
    for b in report["books"]:
        lines += [
            f"## {b['filename']}",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Path | `{b['path']}` |",
            f"| Size | {b['file_size_bytes']:,} bytes |",
            f"| Pages | {b['page_count']} |",
            f"| Chars | {b['total_chars']:,} |",
            f"| Words (approx) | {b['total_words']:,} |",
            f"| Empty pages | {b['empty_pages']} |",
            f"| Avg chars/page | {b['avg_chars_per_nonempty_page']} |",
            f"| Language | {b['detected_language']} |",
            f"| Needs OCR | {'Yes' if b['needs_ocr'] else 'No'} |",
            f"| TOC detected | {'Yes' if b['toc_detected'] else 'No'} |",
            f"| Outline/bookmarks | {b['outline_count']} |",
            f"| Headings detected | {b['structure']['heading_candidates']} |",
            f"| Chapters | {b['structure']['chapter_count']} |",
            f"| Lessons | {b['structure']['lesson_count']} |",
            "",
        ]
        if b["outline_sample"]:
            lines += ["### Outline sample", ""]
            for o in b["outline_sample"][:10]:
                lines.append(f"- Level {o[0]}: {o[1]}")
            lines.append("")

        if b["structure"]["headings_sample"]:
            lines += ["### Heading samples", ""]
            for h in b["structure"]["headings_sample"][:15]:
                lines.append(f"- {h[:80]}")
            lines.append("")

        lines += ["### Text samples", ""]
        for s in b["samples"][:6]:
            lines.append(f"**Page {s['page']}:**")
            lines.append(f"```{s['text'][:200]}```")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"MD: {path}")


def main() -> int:
    args = _parse_args()
    import asyncio
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
