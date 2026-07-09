#!/usr/bin/env python3
"""
PDF Page Probe — KITZUR CreateSpace.

Probe read-only que analiza un PDF para determinar si es apto
para ingesta V2 con page markers confiables.

Uso:
    uv run python scripts/ingestion_v2_pdf_page_probe.py \
      --pdf "/path/to/file.pdf" \
      --report-dir "../../data/reports/breslov/..."
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def probe_pymupdf(path: str) -> dict[str, Any]:
    """Probe PDF using PyMuPDF (fitz)."""
    import fitz

    doc = fitz.open(path)
    total = len(doc)
    results: dict[str, Any] = {
        "method": "pymupdf_fitz",
        "total_pages": total,
        "pages_with_text": 0,
        "pages_empty": 0,
        "total_chars": 0,
        "page_samples": [],
        "detected_numbers": [],
        "warnings": [],
    }

    for i in range(total):
        page = doc.load_page(i)
        text = page.get_text("text")
        char_count = len(text.strip())
        results["total_chars"] += char_count

        if char_count == 0:
            results["pages_empty"] += 1
        else:
            results["pages_with_text"] += 1

        # Sample first 5, last 5, and some middle pages
        is_sample = (
            i < 5
            or i >= total - 5
            or (total > 20 and i in (total // 4, total // 2, 3 * total // 4))
        )
        if is_sample:
            sample = {
                "page_index": i,
                "chars": char_count,
                "preview": text[:300].strip(),
                "has_text": char_count > 0,
            }
            results["page_samples"].append(sample)

        # Detect printed page numbers in text
        numbers = re.findall(r"(?:^|\n)\s*(\d{1,4})\s*(?:\n|$)", text)
        for n in numbers:
            results["detected_numbers"].append({"pdf_index": i, "printed_number": int(n)})

    doc.close()
    return results


def probe_pymupdf4llm(path: str) -> dict[str, Any]:
    """Probe PDF using pymupdf4llm with page markers."""
    try:
        import pymupdf4llm

        md_text = pymupdf4llm.to_markdown(path, page_chunks=True, show_progress=False)
        results: dict[str, Any] = {
            "method": "pymupdf4llm",
            "total_pages": len(md_text),
            "pages_with_text": 0,
            "pages_empty": 0,
            "total_chars": 0,
            "page_samples": [],
            "marker_detected": 0,
            "warnings": [],
        }

        for i, chunk in enumerate(md_text):
            page_num = chunk.get("metadata", {}).get("page", i)
            text = chunk.get("text", "")
            char_count = len(text.strip())
            results["total_chars"] += char_count

            if char_count == 0:
                results["pages_empty"] += 1
            else:
                results["pages_with_text"] += 1

            # Sample
            total = len(md_text)
            is_sample = (
                i < 5 or i >= total - 5
                or (total > 20 and i in (total // 4, total // 2, 3 * total // 4))
            )
            if is_sample:
                results["page_samples"].append({
                    "page_index": i,
                    "metadata_page": page_num,
                    "chars": char_count,
                    "preview": text[:300].strip() if text else "(empty)",
                    "has_text": char_count > 0,
                })

            if "## Page " in text or "## page " in text:
                results["marker_detected"] += 1

        return results
    except ImportError:
        return {"method": "pymupdf4llm", "error": "pymupdf4llm not installed"}
    except Exception as exc:
        return {"method": "pymupdf4llm", "error": str(exc)}


def probe_with_markers(path: str) -> dict[str, Any]:
    """Extract with controlled page markers using fitz page-by-page."""
    import fitz

    doc = fitz.open(path)
    total = len(doc)
    pages = []
    total_chars = 0
    empty_count = 0

    for i in range(total):
        page = doc.load_page(i)
        text = page.get_text("text")
        marked = f"## Page {i + 1}\n\n{text.strip()}"
        char_count = len(text.strip())
        total_chars += char_count
        if char_count == 0:
            empty_count += 1
        pages.append({
            "page_number": i + 1,
            "text": text.strip(),
            "char_count": char_count,
            "has_text": char_count > 0,
        })

    doc.close()

    # Detect sections from combined text
    full_text = "\n".join(p["text"] for p in pages if p["has_text"])
    section_candidates = set()
    for m in re.findall(r"(?:^|\n)\s*(?:\d+[.)]\s*)?([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s]{3,60})(?:\n|$)", full_text):
        m = m.strip()
        if len(m) > 5 and not re.search(r"\d{4}", m):
            section_candidates.add(m)

    return {
        "method": "fitz_with_markers",
        "total_pages": total,
        "total_chars": total_chars,
        "pages_with_text": total - empty_count,
        "pages_empty": empty_count,
        "avg_chars_per_page": round(total_chars / max(total - empty_count, 1), 1),
        "section_candidates": sorted(section_candidates)[:50],
        "page_details": pages[:5] + ["..."] + pages[-5:] if total > 10 else pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF Page Probe for Ingestion V2")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--report-dir", required=True, help="Report output directory")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return 1

    print(f"PDF: {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")
    print(f"Report: {report_dir}\n")

    # ── Probe 1: PyMuPDF ──
    print("=== Probe 1: PyMuPDF (fitz) ===")
    r1 = probe_pymupdf(str(pdf_path))
    print(f"  Pages: {r1['total_pages']}")
    print(f"  With text: {r1['pages_with_text']}")
    print(f"  Empty: {r1['pages_empty']}")
    print(f"  Total chars: {r1['total_chars']}")
    print(f"  Printed numbers detected: {len(r1['detected_numbers'])}")

    # ── Probe 2: pymupdf4llm ──
    print("\n=== Probe 2: pymupdf4llm ===")
    r2 = probe_pymupdf4llm(str(pdf_path))
    print(f"  Method: {r2['method']}")
    if r2.get("error"):
        print(f"  ERROR: {r2['error']}")
    else:
        print(f"  Pages: {r2['total_pages']}")
        print(f"  With text: {r2['pages_with_text']}")
        print(f"  Empty: {r2['pages_empty']}")
        print(f"  Markers detected: {r2.get('marker_detected', 0)}")

    # ── Probe 3: fitz with markers ──
    print("\n=== Probe 3: Fitz with controlled markers ===")
    r3 = probe_with_markers(str(pdf_path))
    print(f"  Pages: {r3['total_pages']}")
    print(f"  With text: {r3['pages_with_text']}")
    print(f"  Empty: {r3['pages_empty']}")
    print(f"  Avg chars/page: {r3['avg_chars_per_page']}")
    print(f"  Section candidates: {len(r3.get('section_candidates', []))}")

    # ── Assessment ──
    print("\n=== Assessment ===")
    has_text = r1["pages_with_text"] > 0
    text_ratio = r1["pages_with_text"] / max(r1["total_pages"], 1)
    assessment = {
        "page_count": r1["total_pages"],
        "pages_with_text": r1["pages_with_text"],
        "pages_empty": r1["pages_empty"],
        "text_coverage_ratio": round(text_ratio, 3),
        "total_chars": r1["total_chars"],
        "avg_chars_per_page": r3.get("avg_chars_per_page", 0),
        "has_embedded_text": has_text,
        "requires_ocr": not has_text and text_ratio < 0.1,
        "pymupdf4llm_available": r2.get("error") is None,
        "pymupdf4llm_markers": r2.get("marker_detected", 0) if not r2.get("error") else 0,
        "section_candidates_count": len(r3.get("section_candidates", [])),
        "printed_numbers_detected": len(r1.get("detected_numbers", [])),
    }

    if text_ratio >= 0.9:
        assessment["page_markers_verdict"] = "PASS"
        assessment["page_markers_detail"] = "High text coverage, reliable page markers achievable"
    elif text_ratio >= 0.5:
        assessment["page_markers_verdict"] = "WARN"
        assessment["page_markers_detail"] = f"Partial text coverage ({text_ratio:.0%})"
    else:
        assessment["page_markers_verdict"] = "FAIL"
        assessment["page_markers_detail"] = f"Low text coverage ({text_ratio:.0%}), may need OCR"

    print(f"  Text coverage: {text_ratio:.0%}")
    print(f"  Has embedded text: {has_text}")
    print(f"  Requires OCR: {assessment['requires_ocr']}")
    print(f"  Page markers: {assessment['page_markers_verdict']}")
    print(f"  Section candidates: {assessment['section_candidates_count']}")

    # ── Save report ──
    report = {
        "pdf_path": str(pdf_path),
        "pdf_size_kb": pdf_path.stat().st_size // 1024,
        "probe_pymupdf": r1,
        "probe_pymupdf4llm": r2,
        "probe_markers": r3,
        "assessment": assessment,
    }
    (report_dir / "pdf_inventory.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    # Sample pages markdown
    sample_lines = ["# Sample Pages\n", f"PDF: {pdf_path}\n", f"Total pages: {r1['total_pages']}\n"]
    for s in r1["page_samples"]:
        preview = s["preview"][:200].replace("\n", " | ")
        sample_lines.append(f"### Page {s['page_index'] + 1} ({s['chars']} chars)\n")
        sample_lines.append(f"{preview}\n\n")
    (report_dir / "sample_pages.md").write_text("\n".join(sample_lines))

    # Section candidates
    sec_lines = ["# Section Candidates\n", f"Found: {len(r3.get('section_candidates', []))}\n"]
    for i, sec in enumerate(r3.get("section_candidates", [])[:30], 1):
        sec_lines.append(f"{i}. {sec}\n")
    (report_dir / "section_candidates.md").write_text("\n".join(sec_lines))

    # Warnings
    warnings = []
    if assessment["requires_ocr"]:
        warnings.append("PDF appears to be scanned (no embedded text)")
    if text_ratio < 0.9:
        warnings.append(f"Text coverage is only {text_ratio:.0%}")
    if r2.get("error"):
        warnings.append(f"pymupdf4llm extraction failed: {r2['error']}")
    if assessment["page_markers_verdict"] == "FAIL":
        warnings.append("Page markers not viable with current extraction methods")
    (report_dir / "warnings.md").write_text("# Warnings\n\n" + "\n".join(f"- {w}" for w in warnings) if warnings else "# Warnings\n\nNone\n")

    print(f"\nReport saved to {report_dir}")
    return 0


if __name__ == "__main__":
    main()
