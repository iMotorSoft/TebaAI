#! /usr/bin/env python3
"""
CLI: Evaluate bibliographic search quality against validation cases.

Usage:
    uv run python -m scripts.evaluate_bibliographic_search \\
        --cases tests/fixtures/breslov_validation_cases.json \\
        --collection breslov \\
        --top-k 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Any


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate bibliographic search quality.")
    parser.add_argument("--cases", required=True, help="Path to validation cases JSON")
    parser.add_argument("--collection", default="breslov", help="Collection code")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K results to evaluate")
    parser.add_argument("--mode", default="auto", choices=["auto", "fts", "phrase", "trigram"])
    parser.add_argument("--language", default="es", choices=["es", "en", "he"])
    parser.add_argument("--output-json", help="Path to write JSON report")
    parser.add_argument("--output-md", help="Path to write Markdown report")
    parser.add_argument("--fail-under", type=float, help="Exit non-zero if pass_rate below this")
    parser.add_argument("--only-level", type=int, choices=[1, 2, 3, 4], help="Only test this level")
    parser.add_argument("--only-category", choices=["literal", "comprehension", "synthesis", "complex", "intertextual"])
    parser.add_argument("--only-book", help="Only test this book")
    parser.add_argument("--verbose", action="store_true", help="Show per-case details")
    return parser.parse_args(argv)


def load_cases(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Cases file must contain a JSON array")
    return data


def filter_cases(cases: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    result = cases
    if args.only_level:
        result = [c for c in result if c.get("level") == args.only_level]
    if args.only_category:
        result = [c for c in result if c.get("category") == args.only_category]
    if args.only_book:
        result = [c for c in result if c.get("book") == args.only_book]
    return result


def evaluate_case(case: dict[str, Any], results: list[dict[str, Any]], top_k: int, mode: str) -> dict[str, Any]:
    """Evaluate a single case against search results."""
    expected_title = case.get("expected_document_title", "")
    expected_terms = case.get("expected_terms", [])
    terms_lower = [t.lower() for t in expected_terms]

    found_position: int | None = None
    found_title: str | None = None
    found_type: str | None = None
    found_score: float | None = None
    found_excerpt: str | None = None
    found_highlighted: str | None = None
    best_reason: str | None = None
    status = "FAIL"

    for pos, r in enumerate(results):
        pos_1based = pos + 1
        doc_title: str = r.get("document_title", "") or ""
        excerpt: str = r.get("highlighted_excerpt", "") or r.get("plain_excerpt", "") or ""
        excerpt_lower = excerpt.lower()

        # Check document match
        title_match = expected_title and (
            doc_title.lower() == expected_title.lower()
            or expected_title.lower() in doc_title.lower()
            or doc_title.lower() in expected_title.lower()
        )

        # Check terms in excerpt
        term_match = any(t in excerpt_lower for t in terms_lower)

        if title_match and term_match:
            # PASS fuerte
            status = "PASS"
            found_position = pos_1based
            found_title = doc_title
            found_type = r.get("match_type", mode)
            found_score = r.get("rank")
            found_excerpt = r.get("plain_excerpt")
            found_highlighted = r.get("highlighted_excerpt")
            best_reason = f"document match + terms in excerpt"
            break
        elif title_match and not term_match:
            # PARTIAL: correct book but missing terms
            if status == "FAIL":
                status = "PARTIAL"
                found_position = pos_1based
                found_title = doc_title
                found_type = r.get("match_type", mode)
                found_score = r.get("rank")
                found_excerpt = r.get("plain_excerpt")
                found_highlighted = r.get("highlighted_excerpt")
                best_reason = f"correct document but no expected terms in excerpt"
        elif term_match and not title_match:
            # PARTIAL: terms found but wrong doc
            if status == "FAIL":
                status = "PARTIAL"
                found_position = pos_1based
                found_title = doc_title
                found_type = r.get("match_type", mode)
                found_score = r.get("rank")
                found_excerpt = r.get("plain_excerpt")
                found_highlighted = r.get("highlighted_excerpt")
                best_reason = f"terms found but in different document: {doc_title}"

    if found_position is None:
        status = "FAIL"
        best_reason = "no matching document or terms in top-k results"

    return {
        "case_id": case["id"],
        "book": case.get("book", ""),
        "level": case.get("level", 0),
        "category": case.get("category", ""),
        "question": case.get("question", "")[:120],
        "query_terms": case.get("query_terms", []),
        "expected_document_title": expected_title,
        "expected_terms": expected_terms,
        "status": status,
        "reason": best_reason or "",
        "found_top_document": found_title or "",
        "found_rank_position": found_position,
        "found_match_type": found_type or "",
        "found_score": found_score,
        "found_excerpt": (found_excerpt or "")[:200] if found_excerpt else None,
        "found_highlighted": (found_highlighted or "")[:200] if found_highlighted else None,
    }


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from modules.library.text_search import search_chunks_text
    from psycopg.rows import dict_row

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
        return 1

    # Load cases
    cases = load_cases(args.cases)
    cases = filter_cases(cases, args)
    print(f"Loaded {len(cases)} validation case(s)")

    pool = create_pool_from_settings()
    await open_pool(pool)

    report_cases: list[dict[str, Any]] = []

    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            cur = conn.cursor()
            await cur.execute("SELECT current_database()")
            db = (await cur.fetchone())["current_database"]
            if db != "tebaai":
                print(f"ERROR: Expected 'tebaai', got '{db}'", file=sys.stderr)
                return 1

            for case in cases:
                query_terms = case.get("query_terms", [])
                if not query_terms:
                    query_terms = [case.get("question", "")]

                best: dict[str, Any] | None = None

                for q in query_terms:
                    try:
                        search_results = await search_chunks_text(
                            conn,
                            collection_code=args.collection,
                            query=q,
                            top_k=args.top_k,
                            mode=args.mode,
                            language=args.language,
                        )
                    except Exception:
                        search_results = []

                    if not search_results:
                        continue

                    eval_result = evaluate_case(case, search_results, args.top_k, args.mode)
                    if best is None or _status_rank(eval_result["status"]) > _status_rank(best["status"]):
                        best = eval_result
                        best["query_used"] = q

                if best is None:
                    best = {
                        "case_id": case["id"],
                        "book": case.get("book", ""),
                        "level": case.get("level", 0),
                        "category": case.get("category", ""),
                        "question": case.get("question", "")[:120],
                        "query_terms": case.get("query_terms", []),
                        "expected_document_title": case.get("expected_document_title", ""),
                        "expected_terms": case.get("expected_terms", []),
                        "status": "FAIL",
                        "reason": "no search results for any query term",
                        "found_top_document": "",
                        "found_rank_position": None,
                        "found_match_type": "",
                        "found_score": None,
                        "found_excerpt": None,
                        "found_highlighted": None,
                        "query_used": query_terms[0] if query_terms else "",
                    }

                report_cases.append(best)

    finally:
        await close_pool(pool)

    # Build report
    summary = build_summary(report_cases)

    # Display
    print(f"\n{'='*60}")
    print(f"Bibliographic Search Evaluation")
    print(f"Collection: {args.collection}")
    print(f"Top-K: {args.top_k}  Mode: {args.mode}")
    print(f"Total cases: {summary['total_cases']}")
    print(f"{'='*60}")

    if args.verbose:
        for c in report_cases:
            icon = {"PASS": "✓", "PARTIAL": "~", "FAIL": "✗"}.get(c["status"], "?")
            level_icon = {1: "N1", 2: "N2", 3: "N3", 4: "N4"}.get(c["level"], "?")
            book_short = c.get("book", "")[:30]
            print(f"  {icon} [{level_icon}] {c['case_id']:35s} {c['status']:8s} | {book_short}")
            if args.verbose and c["status"] != "PASS":
                print(f"      Reason: {c['reason']}")

    print(f"\n{'─'*60}")
    print(f"  Overall:     {summary['pass_count']}/{summary['total_cases']} PASS, "
          f"{summary['partial_count']} PARTIAL, {summary['fail_count']} FAIL")
    print(f"  Pass rate:   {summary['pass_rate']:.1f}%")
    print(f"  Top-1 hit:   {summary['top1_hit_rate']:.1f}%")
    print(f"  Top-3 hit:   {summary['top3_hit_rate']:.1f}%")
    print(f"  Top-10 hit:  {summary['top10_hit_rate']:.1f}%")
    print(f"{'─'*60}")

    # By level
    print(f"\n  By level:")
    for level_data in summary["by_level"]:
        print(f"    {level_data['label']:25s} {level_data['pass_count']:3d}/{level_data['total']:3d} PASS  "
              f"({level_data['pass_rate']:.0f}%)")

    # By category
    print(f"\n  By category:")
    for cat_data in summary["by_category"]:
        print(f"    {cat_data['label']:20s} {cat_data['pass_count']:3d}/{cat_data['total']:3d} PASS  "
              f"({cat_data['pass_rate']:.0f}%)")

    # By book
    print(f"\n  By book:")
    for book_data in summary["by_book"]:
        print(f"    {book_data['label']:30s} {book_data['pass_count']:3d}/{book_data['total']:3d} PASS  "
              f"({book_data['pass_rate']:.0f}%)")
    print()

    # Output files
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "cases": report_cases}, f, indent=2, ensure_ascii=False)
        print(f"JSON report: {args.output_json}")

    if args.output_md:
        md = build_markdown(summary, report_cases, args)
        with open(args.output_md, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"MD report:   {args.output_md}")

    # Fail-under check
    if args.fail_under is not None and summary["pass_rate"] < args.fail_under:
        print(f"FAIL: pass rate {summary['pass_rate']:.1f}% < {args.fail_under}%")
        return 1

    return 0


def _status_rank(s: str) -> int:
    return {"PASS": 3, "PARTIAL": 2, "FAIL": 1}.get(s, 0)


def build_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    pass_count = sum(1 for c in cases if c["status"] == "PASS")
    partial_count = sum(1 for c in cases if c["status"] == "PARTIAL")
    fail_count = sum(1 for c in cases if c["status"] == "FAIL")
    pass_rate = (pass_count / total * 100) if total else 0

    top1 = sum(1 for c in cases if c.get("found_rank_position") == 1)
    top3 = sum(1 for c in cases if c.get("found_rank_position") is not None and c["found_rank_position"] <= 3)
    top10 = sum(1 for c in cases if c.get("found_rank_position") is not None)

    # By level
    levels = {1: "N1 trivial", 2: "N2 fácil", 3: "N3 media", 4: "N4 difícil"}
    by_level = []
    for lv, lbl in levels.items():
        subset = [c for c in cases if c.get("level") == lv]
        if subset:
            sp = sum(1 for c in subset if c["status"] == "PASS")
            by_level.append({
                "label": lbl, "total": len(subset), "pass_count": sp,
                "partial_count": sum(1 for c in subset if c["status"] == "PARTIAL"),
                "fail_count": sum(1 for c in subset if c["status"] == "FAIL"),
                "pass_rate": sp / len(subset) * 100,
            })

    # By category
    cats = ["literal", "comprehension", "synthesis", "complex", "intertextual"]
    by_category = []
    for cat in cats:
        subset = [c for c in cases if c.get("category") == cat]
        if subset:
            sp = sum(1 for c in subset if c["status"] == "PASS")
            by_category.append({
                "label": cat, "total": len(subset), "pass_count": sp,
                "partial_count": sum(1 for c in subset if c["status"] == "PARTIAL"),
                "fail_count": sum(1 for c in subset if c["status"] == "FAIL"),
                "pass_rate": sp / len(subset) * 100,
            })

    # By book
    books = sorted(set(c.get("book", "") for c in cases if c.get("book")))
    by_book = []
    for bk in books:
        subset = [c for c in cases if c.get("book") == bk]
        if subset:
            sp = sum(1 for c in subset if c["status"] == "PASS")
            by_book.append({
                "label": bk, "total": len(subset), "pass_count": sp,
                "partial_count": sum(1 for c in subset if c["status"] == "PARTIAL"),
                "fail_count": sum(1 for c in subset if c["status"] == "FAIL"),
                "pass_rate": sp / len(subset) * 100,
            })

    return {
        "total_cases": total,
        "pass_count": pass_count,
        "partial_count": partial_count,
        "fail_count": fail_count,
        "pass_rate": round(pass_rate, 1),
        "top1_hit_rate": round(top1 / total * 100, 1) if total else 0,
        "top3_hit_rate": round(top3 / total * 100, 1) if total else 0,
        "top10_hit_rate": round(top10 / total * 100, 1) if total else 0,
        "by_level": by_level,
        "by_category": by_category,
        "by_book": by_book,
    }


def build_markdown(summary: dict[str, Any], cases: list[dict[str, Any]], args: argparse.Namespace) -> str:
    lines = [
        "# Bibliographic Search Evaluation Report",
        "",
        f"**Date:** {datetime.utcnow().isoformat()}",
        f"**Collection:** {args.collection}",
        f"**Top-K:** {args.top_k}  **Mode:** {args.mode}",
        f"**Language:** {args.language}",
        f"**Cases file:** {args.cases}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Total cases | {summary['total_cases']} |",
        f"| PASS | {summary['pass_count']} |",
        f"| PARTIAL | {summary['partial_count']} |",
        f"| FAIL | {summary['fail_count']} |",
        f"| Pass rate | {summary['pass_rate']}% |",
        f"| Top-1 hit rate | {summary['top1_hit_rate']}% |",
        f"| Top-3 hit rate | {summary['top3_hit_rate']}% |",
        f"| Top-10 hit rate | {summary['top10_hit_rate']}% |",
        "",
        "### By Level",
        "",
        "| Level | PASS | PARTIAL | FAIL | Total | Rate |",
        "|-------|-----:|--------:|-----:|------:|-----:|",
    ]
    for ld in summary["by_level"]:
        lines.append(f"| {ld['label']} | {ld['pass_count']} | {ld['partial_count']} | {ld['fail_count']} | {ld['total']} | {ld['pass_rate']:.0f}% |")

    lines.extend(["", "### By Category", "", "| Category | PASS | PARTIAL | FAIL | Total | Rate |", "|----------|-----:|--------:|-----:|------:|-----:|"])
    for cd in summary["by_category"]:
        lines.append(f"| {cd['label']} | {cd['pass_count']} | {cd['partial_count']} | {cd['fail_count']} | {cd['total']} | {cd['pass_rate']:.0f}% |")

    lines.extend(["", "### By Book", "", "| Book | PASS | PARTIAL | FAIL | Total | Rate |", "|------|-----:|--------:|-----:|------:|-----:|"])
    for bd in summary["by_book"]:
        lines.append(f"| {bd['label']} | {bd['pass_count']} | {bd['partial_count']} | {bd['fail_count']} | {bd['total']} | {bd['pass_rate']:.0f}% |")

    lines.extend(["", "---", "", "## Per-case results", "", "| ID | Book | N | Category | Status | Reason |", "|----|------|---|----------|--------|--------|"])
    for c in cases:
        book_short = c.get("book", "")[:25]
        lines.append(f"| {c['case_id']} | {book_short} | {c['level']} | {c['category']} | {c['status']} | {c.get('reason','')[:80]} |")

    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
