#!/usr/bin/env python3
"""
Validator for Likutey Halajot layout-aware blocks.

Checks block_type, node_path, citable, language coverage, source_refs,
and applies quality rules per the ingestion contract.

Usage:
    uv run python -m scripts.validate_likutey_layout_blocks \\
        --pages 23,32,37  (printed page numbers)
        --output-dir /tmp/layout_blocks_test
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# Validation rules
# ═══════════════════════════════════════════════════════════════════════

REQUIRED_BLOCK_TYPES = {
    "page_header": {"critical": True, "min_count": 1},
    "source_hebrew": {"critical": True},
    "section_marker": {"critical": False},
    "main_explanation_es": {"critical": False},
    "footnote": {"critical": False},
}

VALID_BLOCK_TYPES = {
    "page_header", "source_hebrew", "section_marker",
    "main_explanation_es", "marginal_source", "footnote",
    "internal_cross_reference", "composite_page_context", "unknown",
}

VALID_LANGUAGES = {"es", "he", "mixed", "unknown"}

PRINTED_PAGES_CRITICAL = {23, 32, 37}


# ═══════════════════════════════════════════════════════════════════════
# Validation functions
# ═══════════════════════════════════════════════════════════════════════


def validate_page(
    page_number: int,
    blocks: list[dict],
    printed_page_label: str | None = None,
    page_mapping: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Validate blocks on a single page.

    Returns a validation result dict.
    """
    issues: list[str] = []
    warnings: list[str] = []
    block_types: dict[str, int] = defaultdict(int)
    languages: dict[str, int] = defaultdict(int)
    empty_blocks = 0
    unknown_blocks = 0
    non_citable_composites = 0
    needs_review_count = 0
    node_path_missing = 0
    block_type_missing = 0
    citable_missing = 0
    header_found = False
    hebrew_found = False
    spanish_found = False

    for b in blocks:
        bt = b.get("block_type", "")
        lang = b.get("language", "unknown")
        content = b.get("content", "")
        citable = b.get("citable", True)
        confidence = b.get("layout_confidence", 0.0)
        needs_review_meta = (
            b.get("needs_reference_review", False) or
            b.get("needs_hebrew_review", False)
        )
        node_path = b.get("node_path")

        block_types[bt] += 1
        languages[lang] += 1

        if bt == "" or bt is None:
            block_type_missing += 1
            issues.append("block_type missing")
        elif bt not in VALID_BLOCK_TYPES:
            issues.append(f"Invalid block_type: {bt}")
        elif bt == "unknown":
            unknown_blocks += 1

        if citable is None:
            citable_missing += 1
            issues.append("citable missing")

        if bt == "composite_page_context" and citable is True:
            issues.append("composite_page_context must be citable=false")

        if bt == "composite_page_context" and citable is False:
            non_citable_composites += 1

        if not content.strip():
            empty_blocks += 1
            warnings.append(f"Empty content in block {b.get('block_index')}")

        if bt == "page_header":
            header_found = True
        if lang in ("he", "mixed"):
            hebrew_found = True
        if lang == "es":
            spanish_found = True

        if needs_review_meta:
            needs_review_count += 1

        if node_path is None or node_path.strip() == "":
            node_path_missing += 1

        if confidence < 0.5:
            warnings.append(
                f"Low confidence {confidence:.2f} in block {b.get('block_index')} type={bt}"
            )

    # ── Page-level rules ─────────────────────────────────────────────
    is_critical = (
        printed_page_label is not None and
        int(printed_page_label) in PRINTED_PAGES_CRITICAL
    )

    # Header requirement
    if is_critical and not header_found:
        issues.append("CRITICAL: No page_header block found")

    # Hebrew requirement for odd pages
    if header_found and not hebrew_found:
        warnings.append("No Hebrew content detected (may be even page)")

    if block_type_missing > 0:
        issues.append(f"{block_type_missing} block(s) missing block_type")

    # Build evaluation
    severity = "PASS"
    if issues:
        critical_issues = [i for i in issues if i.startswith("CRITICAL")]
        if critical_issues:
            severity = "FAIL"
        else:
            severity = "WARN"

    result = {
        "page_number": page_number,
        "printed_page_label": printed_page_label,
        "is_critical_page": is_critical,
        "total_blocks": len(blocks),
        "block_type_counts": dict(block_types),
        "language_counts": dict(languages),
        "empty_blocks": empty_blocks,
        "unknown_blocks": unknown_blocks,
        "non_citable_composites": non_citable_composites,
        "needs_review_count": needs_review_count,
        "node_path_missing": node_path_missing,
        "block_type_missing": block_type_missing,
        "citable_missing": citable_missing,
        "header_found": header_found,
        "hebrew_found": hebrew_found,
        "spanish_found": spanish_found,
        "issues": issues,
        "warnings": warnings,
        "severity": severity,
    }
    return result


# ═══════════════════════════════════════════════════════════════════════
# Full validation
# ═══════════════════════════════════════════════════════════════════════


def validate_all(
    parsed_data: dict[int, list[dict]],
    page_mapping: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Validate all parsed blocks and return comprehensive results."""
    page_results: list[dict[str, Any]] = []
    overall_issues: list[str] = []
    overall_warnings: list[str] = []

    type_totals: dict[str, int] = defaultdict(int)
    lang_totals: dict[str, int] = defaultdict(int)
    total_blocks = 0
    total_empty = 0
    total_unknown = 0
    total_needs_review = 0
    total_node_path_missing = 0
    total_citable_missing = 0
    total_non_citable_composites = 0
    pages_with_composites = 0

    # Build reverse mapping: PDF page number → printed page label
    pdf_to_printed: dict[int, str] = {}
    if page_mapping:
        pdf_to_printed = {v: str(k) for k, v in page_mapping.items()}

    for page_num in sorted(parsed_data):
        blocks_dicts = parsed_data[page_num]
        # Convert LayoutBlock objects to dicts if needed
        blocks = [b.to_dict() if hasattr(b, "to_dict") else b for b in blocks_dicts]

        printed_label = pdf_to_printed.get(page_num - 1)

        result = validate_page(page_num, blocks, printed_label, page_mapping)
        page_results.append(result)

        severity = result["severity"]
        total_blocks += result["total_blocks"]
        total_empty += result["empty_blocks"]
        total_unknown += result["unknown_blocks"]
        total_needs_review += result["needs_review_count"]
        total_node_path_missing += result["node_path_missing"]
        total_citable_missing += result["citable_missing"]
        total_non_citable_composites += result["non_citable_composites"]

        for bt, cnt in result["block_type_counts"].items():
            type_totals[bt] += cnt
        for lang, cnt in result["language_counts"].items():
            lang_totals[lang] += cnt

        if result["non_citable_composites"] > 0:
            pages_with_composites += 1

    # ── Overall evaluation ───────────────────────────────────────────
    fail_pages = [r for r in page_results if r["severity"] == "FAIL"]
    warn_pages = [r for r in page_results if r["severity"] == "WARN"]
    pass_pages = [r for r in page_results if r["severity"] == "PASS"]

    critical_fails = [
        r for r in fail_pages if r.get("is_critical_page")
    ]

    if critical_fails:
        overall_severity = "FAIL"
        for cf in critical_fails:
            overall_issues.append(
                f"Critical page {cf['printed_page_label']} (PDF {cf['page_number']}) FAILED"
            )
    elif fail_pages:
        overall_severity = "WARN"
        overall_warnings.append(f"{len(fail_pages)} non-critical page(s) failed")
    elif warn_pages:
        overall_severity = "WARN"
        overall_warnings.append(f"{len(warn_pages)} page(s) with warnings")
    else:
        overall_severity = "PASS"

    return {
        "overall_severity": overall_severity,
        "total_pages": len(page_results),
        "total_blocks": total_blocks,
        "total_empty": total_empty,
        "total_unknown": total_unknown,
        "total_needs_review": total_needs_review,
        "total_node_path_missing": total_node_path_missing,
        "total_citable_missing": total_citable_missing,
        "total_non_citable_composites": total_non_citable_composites,
        "pages_with_composites": pages_with_composites,
        "pass_pages": len(pass_pages),
        "warn_pages": len(warn_pages),
        "fail_pages": len(fail_pages),
        "critical_fails": len(critical_fails),
        "block_type_totals": dict(type_totals),
        "language_totals": dict(lang_totals),
        "issues": overall_issues,
        "warnings": overall_warnings,
        "page_results": page_results,
    }


# ═══════════════════════════════════════════════════════════════════════
# Output
# ═══════════════════════════════════════════════════════════════════════


def print_validation_report(result: dict[str, Any]) -> None:
    """Print a human-readable validation report."""
    print("=" * 70)
    print(f"  LAYOUT BLOCK VALIDATION REPORT")
    print(f"  Severity: {result['overall_severity']}")
    print("=" * 70)
    print()
    print(f"Pages:        {result['total_pages']:5d}")
    print(f"Blocks:       {result['total_blocks']:5d}")
    print(f"Empty:        {result['total_empty']:5d}")
    print(f"Unknown:      {result['total_unknown']:5d}")
    print(f"Needs review: {result['total_needs_review']:5d}")
    print(f"Node path ∅:  {result['total_node_path_missing']:5d}")
    print(f"citable ∅:    {result['total_citable_missing']:5d}")
    print(f"Composites:   {result['total_non_citable_composites']:5d}")
    print()
    print(f"PASS:  {result['pass_pages']:3d}")
    print(f"WARN:  {result['warn_pages']:3d}")
    print(f"FAIL:  {result['fail_pages']:3d}")
    print(f"Crit:  {result['critical_fails']:3d}")
    print()

    if result["issues"]:
        print("─ Issues ─")
        for issue in result["issues"]:
            print(f"  ❌ {issue}")
        print()

    if result["warnings"]:
        print("─ Warnings ─")
        for w in result["warnings"]:
            print(f"  ⚠ {w}")
        print()

    print("─ Block types ─")
    for bt, cnt in sorted(result["block_type_totals"].items()):
        print(f"  {bt:30s}: {cnt:5d}")
    print()

    print("─ Languages ─")
    for lang, cnt in sorted(result["language_totals"].items()):
        print(f"  {lang:10s}: {cnt:5d}")
    print()

    if result["page_results"]:
        print("─ Per-page detail ─")
        print(f"{'Pg':>4s} | {'Printed':>8s} | {'Blk':>4s} | {'Severity':>8s} | Issues")
        print("-" * 65)
        for r in result["page_results"]:
            pp = r.get("printed_page_label") or "?"
            issue_str = "; ".join(r["issues"][:3])
            print(f"{r['page_number']:4d} | {str(pp):>8s} | {r['total_blocks']:4d} | {r['severity']:>8s} | {issue_str}")
        print()


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate Likutey Halajot layout blocks",
    )
    parser.add_argument("--input-dir", default="/tmp/layout_blocks",
                        help="Directory with page_NNNN_blocks.json files")
    parser.add_argument("--json", action="store_true",
                        help="Output full JSON report")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}")
        sys.exit(1)

    # Load all block JSON files
    parsed: dict[int, list[dict]] = {}
    for fpath in sorted(input_dir.glob("page_*_blocks.json")):
        with open(fpath) as f:
            data = json.load(f)
        pg = data["page_number"]
        parsed[pg] = data["blocks"]

    if not parsed:
        print("No block files found.")
        sys.exit(1)

    # Load page mapping if available
    mapping_dir = Path("/tmp/likutey_layout_probe")
    page_mapping: dict[int, int] | None = None
    mapping_file = input_dir / "page_mapping.json"
    if mapping_file.exists():
        with open(mapping_file) as f:
            page_mapping = {int(k): int(v) for k, v in json.load(f).items()}
    elif mapping_dir.joinpath("page_mapping.json").exists():
        with open(mapping_dir.joinpath("page_mapping.json")) as f:
            page_mapping = {int(k): int(v) for k, v in json.load(f).items()}

    result = validate_all(parsed, page_mapping)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_validation_report(result)


if __name__ == "__main__":
    main()
