#!/usr/bin/env python3
"""Book QA V2 SQL Acid Batch — 10 preguntas sobre KITZUR V2."""

from __future__ import annotations

import argparse, asyncio, json, re, sys
from pathlib import Path
from typing import Any

from scripts.book_qa_v2_sql_probe import probe, classify

QUESTIONS = [
    {"id": 1, "question": "¿Dónde aparece la alegría?", "expected_route": "concept_lookup"},
    {"id": 2, "question": "¿Dónde aparece la plegaria?", "expected_route": "concept_lookup"},
    {"id": 3, "question": "¿Dónde aparece hitbodedut?", "expected_route": "concept_lookup"},
    {"id": 4, "question": "¿Dónde aparece emuná?", "expected_route": "concept_lookup"},
    {"id": 5, "question": "¿Dónde aparece sangre?", "expected_route": "concept_lookup"},
    {"id": 6, "question": "¿Dónde aparece habla?", "expected_route": "concept_lookup"},
    {"id": 7, "question": "¿Qué relación hay entre alegría y plegaria?", "expected_route": "relation_lookup"},
    {"id": 8, "question": "¿Qué relación hay entre sangre y habla?", "expected_route": "relation_lookup"},
    {"id": 9, "question": "¿Qué relación hay entre hitbodedut y plegaria?", "expected_route": "relation_lookup"},
    {"id": 10, "question": 'Buscá la frase "Rebe Najmán"', "expected_route": "phrase_lookup"},
]


def score_question(q: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    score = 0
    details = []

    # 1. Classification correct (2 pts)
    route = result.get("route", "?")
    expected = q["expected_route"]
    if route == expected:
        score += 2
        details.append("clasificación: correcta")
    else:
        details.append(f"clasificación: esperaba {expected}, obtuvo {route}")

    # 2. Evidence found when exists (2 pts)
    sources = result.get("sources", [])
    if sources:
        score += 2
        details.append(f"evidencia: {len(sources)} fuentes")
    else:
        details.append("evidencia: no encontrada")

    # 3. Page/snippet useful (2 pts)
    if sources:
        has_page = any(s.get("page_number") for s in sources)
        has_snippet = any(s.get("snippet", "").strip() for s in sources)
        if has_page and has_snippet:
            score += 2
            details.append("página+snippet: útil")
        elif has_page:
            score += 1
            details.append("página: sí, snippet: no")
        else:
            details.append("página: no")
    else:
        details.append("página: sin fuentes")

    # 4. Evidence type correct (2 pts)
    if sources:
        ev_types = set(s.get("evidence_type", "") for s in sources)
        expected_types = {"concept_lookup": {"concept"}, "relation_lookup": {"relation_candidate", "cooccurrence_same_page"}, "phrase_lookup": {"literal", "token_match"}}
        expected_set = expected_types.get(expected, set())
        if ev_types & expected_set:
            score += 2
            details.append(f"tipo evidencia: {ev_types}")
        else:
            score += 1
            details.append(f"tipo evidencia: parcial ({ev_types})")
    else:
        score += 0

    # 5. Warnings honest (1 pt)
    warnings = result.get("warnings", [])
    if warnings:
        score += 1
        details.append(f"warnings: {len(warnings)}")
    else:
        score += 0
        details.append("warnings: ninguno")

    # 6. Method explicit (1 pt)
    method = result.get("method", {})
    if method.get("retrieval") == "postgres_v2_sql_only":
        score += 1
        details.append("método: SQL-only")

    return {"score": score, "max": 10, "details": "; ".join(details), "status": "PASS" if score >= 7 else "WARN" if score >= 4 else "FAIL"}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Book QA V2 SQL Acid Batch")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for q in QUESTIONS:
        print(f"Q{q['id']:02d}: {q['question'][:60]}...", file=sys.stderr)
        result = await probe(q["question"], args.run_id, args.top_k)
        scoring = score_question(q, result)
        all_results.append({"question": q, "result": result, "scoring": scoring})
        status = scoring["status"]
        print(f"  → {scoring['score']}/10 {status}", file=sys.stderr)

        # Save raw
        slug = re.sub(r"[^a-z0-9]+", "-", q["question"].lower())[:40].strip("-")
        (report_dir / f"raw_Q{q['id']:02d}_{slug}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    # Summary
    total_score = sum(a["scoring"]["score"] for a in all_results)
    max_score = len(QUESTIONS) * 10
    pct = round(total_score / max_score * 100)

    if pct >= 90:
        global_status = "PASS fuerte"
    elif pct >= 75:
        global_status = "PASS usable"
    elif pct >= 50:
        global_status = "WARN"
    else:
        global_status = "FAIL"

    print(f"\nTotal: {total_score}/{max_score} ({pct}%) — {global_status}", file=sys.stderr)
    print(f"\n| ID | Pregunta | Route | Evidencia | Score | Status |", file=sys.stderr)
    print(f"|---:|---|---|---:|---|", file=sys.stderr)
    for a in all_results:
        q = a["question"]
        r = a["result"]
        s = a["scoring"]
        ev_count = len(r.get("sources", []))
        print(f"| {q['id']:02d} | {q['question'][:40]} | {r.get('route','?')} | {ev_count} src | {s['score']}/10 | {s['status']} |", file=sys.stderr)

    # Save report
    report = {
        "total_score": total_score, "max_score": max_score, "percentage": pct,
        "global_status": global_status, "results": all_results,
    }
    (report_dir / "acid_batch_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    # Scoring markdown
    md_lines = [
        "# Book QA V2 SQL Acid Batch — Scoring",
        "",
        f"**Total: {total_score}/{max_score} ({pct}%) — {global_status}**",
        "",
        "| ID | Pregunta | Route | Fuentes | Score | Status | Detalle |",
        "|---:|---|---|---:|---|---|",
    ]
    for a in all_results:
        q = a["question"]
        r = a["result"]
        s = a["scoring"]
        md_lines.append(
            f"| {q['id']:02d} | {q['question'][:50]} | {r.get('route','?')} | {len(r.get('sources',[]))} | {s['score']}/10 | {s['status']} | {s['details'][:50]} |"
        )
    md_lines += ["", "### Leyenda", "10-7: PASS | 6-4: WARN | 3-0: FAIL"]
    (report_dir / "scoring.md").write_text("\n".join(md_lines) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
