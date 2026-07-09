#!/usr/bin/env python3
"""Book QA V2 HTTP Acid Batch — 10 preguntas contra endpoint real."""

from __future__ import annotations

import argparse, asyncio, json, os, re, sys
from pathlib import Path
from typing import Any

import httpx

BASE = "http://127.0.0.1:7008"
RUN_ID = "492acd8d-06bd-42ac-a511-f3ec52f97bb3"

QUESTIONS = [
    {"id": 1, "question": "¿Dónde aparece la alegría?", "expected_type": "concept_lookup"},
    {"id": 2, "question": "¿Dónde aparece la plegaria?", "expected_type": "concept_lookup"},
    {"id": 3, "question": "¿Dónde aparece hitbodedut?", "expected_type": "concept_lookup"},
    {"id": 4, "question": "¿Dónde aparece emuná?", "expected_type": "concept_lookup"},
    {"id": 5, "question": "¿Dónde aparece sangre?", "expected_type": "concept_lookup"},
    {"id": 6, "question": "¿Dónde aparece habla?", "expected_type": "concept_lookup"},
    {"id": 7, "question": "¿Qué relación hay entre alegría y plegaria?", "expected_type": "relation_lookup"},
    {"id": 8, "question": "¿Qué relación hay entre sangre y habla?", "expected_type": "relation_lookup"},
    {"id": 9, "question": "¿Qué relación hay entre hitbodedut y plegaria?", "expected_type": "relation_lookup"},
    {"id": 10, "question": 'Buscá la frase "Rebe Najmán"', "expected_type": "phrase_lookup"},
]


def score_question(q: dict, result: dict) -> dict:
    score = 0
    details = []
    route = result.get("answer_type", "?")
    expected = q["expected_type"]

    if route == expected:
        score += 2; details.append("clasificación: correcta")
    else:
        details.append(f"clasificación: esperaba {expected}, obtuvo {route}")

    sources = result.get("sources", [])
    if sources:
        score += 2; details.append(f"evidencia: {len(sources)} fuentes")
    else:
        details.append("evidencia: no encontrada")

    has_page = any(s.get("page_number") for s in sources)
    has_snippet = any(s.get("snippet", "").strip() for s in sources)
    if has_page and has_snippet:
        score += 2; details.append("página+snippet: útil")
    elif has_page:
        score += 1; details.append("página: sí, snippet: no")
    else:
        details.append("página: sin fuentes")

    if sources:
        ev_types = set(s.get("evidence_type", "") for s in sources)
        expected_set = {"concept_lookup": {"concept"}, "relation_lookup": {"cooccurrence_same_page"}, "phrase_lookup": {"literal", "partial_phrase"}}
        if ev_types & expected_set.get(expected, set()):
            score += 2; details.append(f"tipo evidencia: correcto")
        else:
            score += 1; details.append(f"tipo evidencia: parcial")
    else:
        score += 0

    warnings = result.get("warnings", [])
    if warnings:
        score += 1; details.append(f"warnings: {len(warnings)}")
    else:
        details.append("warnings: ninguno")

    method = result.get("method", {})
    if method.get("retrieval") == "postgres_v2_sql_only":
        score += 1; details.append("método: SQL-only")

    status = "PASS" if score >= 7 else "WARN" if score >= 4 else "FAIL"
    return {"score": score, "max": 10, "details": "; ".join(details), "status": status}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, default=Path("data/reports/breslov/2026-07-09-book-qa-v2-endpoint-sql"))
    args = parser.parse_args()
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", "")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD", "")
    if not email or not password:
        print("ERROR: TEBAAI_E2E_ADMIN_EMAIL/PASSWORD required"); return 1

    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=10)
        token = r.json()["access_token"]

        all_results = []
        for q in QUESTIONS:
            print(f"Q{q['id']:02d}: {q['question'][:60]}...", file=sys.stderr)
            r = await c.post(f"{BASE}/library/book-qa", headers={"Authorization": f"Bearer {token}"}, json={
                "question": q["question"], "run_id": RUN_ID, "top_k": 8,
            }, timeout=60)
            result = r.json()
            scoring = score_question(q, result)
            all_results.append({"question": q, "result": result, "scoring": scoring})
            print(f"  → {scoring['score']}/10 {scoring['status']}", file=sys.stderr)

            slug = re.sub(r"[^a-z0-9]+", "-", q["question"].lower())[:40].strip("-")
            (report_dir / f"raw_Q{q['id']:02d}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    total = sum(a["scoring"]["score"] for a in all_results)
    max_s = len(QUESTIONS) * 10
    pct = round(total / max_s * 100)
    gs = "PASS fuerte" if pct >= 90 else "PASS usable" if pct >= 75 else "WARN" if pct >= 50 else "FAIL"

    print(f"\nTotal: {total}/{max_s} ({pct}%) — {gs}", file=sys.stderr)
    summary = {"total_score": total, "max_score": max_s, "percentage": pct, "global_status": gs, "results": all_results}
    (report_dir / "http_acid_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print(f"Report: {report_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
