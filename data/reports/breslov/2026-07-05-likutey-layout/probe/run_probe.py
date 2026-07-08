#!/usr/bin/env python3
"""
Likutey Halajot Layout Probe — Phase 0 to Phase 6.

Read-only analysis of PDF layout, zones, blocks, classification.
"""
import json, sys, re
from pathlib import Path
from collections import defaultdict

# Add backend to path for hebrew_tex_decoder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "SrvRestAstroLS_v1" / "backend"))

import fitz
from probe_common import *

OUT_DIR = Path(__file__).parent

def analyze_page(doc, pg_idx: int) -> dict:
    """Extract detailed block-level info for one page."""
    page = doc[pg_idx]
    page_width = page.rect.width
    page_height = page.rect.height
    text_full = page.get_text('text')
    blocks = page.get_text('blocks', sort=True)

    result = {
        "pdf_index": pg_idx,
        "page_size": {"w": page_width, "h": page_height},
        "total_blocks": len(blocks),
        "full_text_length": len(text_full),
        "printed_page_number": None,
        "blocks": [],
    }

    # Detect printed page number
    for b in blocks:
        x0, y0, x1, y1, btext, _, _ = b
        if y0 < 60:
            pn = extract_page_number(btext)
            if pn:
                result["printed_page_number"] = pn
                break

    for i, b in enumerate(blocks):
        x0, y0, x1, y1, text, block_no, block_type = b
        block_w = x1 - x0
        block_h = y1 - y0
        lang = detect_language(text)
        block_cls = classify_block(x0, y0, x1, y1)

        # Refine classification
        if block_cls == "main_explanation_es" and is_notes_marker(text):
            block_cls = "notes_marker"
        if block_cls == "page_header" and is_section_marker(text):
            block_cls = "section_marker"
        if block_cls == "main_explanation_es" and is_marginal_style(block_w, block_h, x0):
            block_cls = "marginal_source"

        blk = {
            "block_index": i,
            "bbox": [round(x0), round(y0), round(x1), round(y1)],
            "width": round(block_w),
            "height": round(block_h),
            "pdf_block_type": block_type,
            "classified_type": block_cls,
            "language": lang,
            "text_preview": text[:150].replace("\n", " | "),
            "text_length": len(text),
            "has_notes_marker": is_notes_marker(text),
            "has_section_marker": is_section_marker(text),
        }
        result["blocks"].append(blk)

    return result


def main():
    doc = fitz.open(PDF_PATH)
    total_pages = len(doc)
    print(f"PDF: {PDF_PATH}")
    print(f"Total pages: {total_pages}")
    print(f"Page size: {PAGE_W} x {PAGE_H}")
    print()

    # ── Build printed → PDF mapping ──
    print("=== Building page mapping ===")
    mapping = build_page_mapping(doc)
    pdf_to_printed = {v: k for k, v in mapping.items()}
    print(f"  Mapped {len(mapping)} printed pages")
    # Show every 10th
    for pp in sorted(mapping):
        if pp % 5 == 0 or pp <= 5:
            print(f"    Printed page {pp} → PDF index {mapping[pp]}")
    print()

    # ── Sample pages to analyze ──
    # Key pages: 23, 32, 37 (plus intro, front, transition pages)
    target_printed = [1, 2, 3, 4, 18, 22, 23, 24, 31, 32, 33, 36, 37, 38, 40, 45, 50, 55, 60, 65, 70, 75, 80]
    sample_pdf_indices = set()
    for pp in target_printed:
        if pp in mapping:
            sample_pdf_indices.add(mapping[pp])
    # Also add pages around key pages
    for kp in [23, 32, 37]:
        if kp in mapping:
            idx = mapping[kp]
            for offset in [-1, 0, 1]:
                if 0 <= idx + offset < total_pages:
                    sample_pdf_indices.add(idx + offset)

    # Add front matter
    for pg in range(0, 6):
        sample_pdf_indices.add(pg)

    sample_pdf_indices = sorted(sample_pdf_indices)
    print(f"=== Analyzing {len(sample_pdf_indices)} sample pages ===")
    print()

    all_results = {}

    for pg_idx in sample_pdf_indices:
        result = analyze_page(doc, pg_idx)
        pp = result["printed_page_number"] or "?"
        print(f"PDF index {pg_idx:3d} → Printed page {str(pp):>4s}: {result['total_blocks']:2d} blocks, {result['full_text_length']:5d} chars")
        all_results[str(pg_idx)] = result

        # Save individual page JSON
        base = f"page_{pg_idx:03d}"
        if pp != "?":
            base = f"page_{pg_idx:03d}_printed_{pp:03d}"

        # Full blocks JSON
        save_json(f"{base}_blocks.json", result)

        # Raw text
        page = doc[pg_idx]
        raw_text = page.get_text('text')
        txt_path = OUT_DIR / f"{base}_text.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        print(f"  Saved {txt_path}")

        # Classification summary
        cls_counts = defaultdict(int)
        for blk in result["blocks"]:
            cls_counts[blk["classified_type"]] += 1
        print(f"  Types: {dict(cls_counts)}")
        print()

    # ── Summary table ──
    print("\n=== SUMMARY TABLE ===")
    print(f"{'PDF Idx':>8s} | {'Printed':>8s} | {'Blocks':>6s} | {'Chars':>6s} | {'Header':>12s} | {'Hebr':>6s} | {'Esp':>6s} | {'Marg':>6s} | {'Foot':>6s} | {'NotesM':>6s} | Eval")
    print("-" * 95)
    for pg_idx in sample_pdf_indices:
        r = all_results[str(pg_idx)]
        pp = r["printed_page_number"] or "?"
        blocks = r["blocks"]
        header_cnt = sum(1 for b in blocks if b["classified_type"] == "page_header")
        hebr_cnt = sum(1 for b in blocks if b["language"] in ("he", "he_si960"))
        esp_cnt = sum(1 for b in blocks if b["language"] == "es")
        marg_cnt = sum(1 for b in blocks if b["classified_type"] == "marginal_source")
        foot_cnt = sum(1 for b in blocks if b["classified_type"] == "footnote_area")
        notes_m = sum(1 for b in blocks if b["has_notes_marker"])

        # Evaluate
        has_marg = marg_cnt > 0
        has_foot = foot_cnt > 0
        has_he = hebr_cnt > 0
        has_notes_marker = notes_m > 0

        if has_marg and has_foot and has_he:
            eval_str = "PASS"
        elif has_foot and has_he:
            eval_str = "WARN"
        else:
            eval_str = "FAIL"

        print(f"{pg_idx:8d} | {str(pp):>8s} | {len(blocks):6d} | {r['full_text_length']:6d} | {header_cnt:12d} | {hebr_cnt:6d} | {esp_cnt:6d} | {marg_cnt:6d} | {foot_cnt:6d} | {notes_m:6d} | {eval_str}")

    # ── Save compiled results ──
    compiled = {
        "pdf_path": PDF_PATH,
        "total_pages": total_pages,
        "page_mapping": {str(k): v for k, v in sorted(mapping.items())},
        "sample_pages": {str(k): all_results[str(k)] for k in sample_pdf_indices},
    }
    save_json("compiled_probe_results.json", compiled)
    save_json("page_mapping.json", mapping)

    print("\n=== Done ===")
    print(f"  Total pages: {total_pages}")
    print(f"  Mapped printed pages: {len(mapping)}")
    print(f"  Sample pages analyzed: {len(sample_pdf_indices)}")

    doc.close()


if __name__ == "__main__":
    main()
