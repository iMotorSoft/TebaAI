#!/usr/bin/env python3
"""KITZUR Level 1 Book QA Acid Batch — preguntas triviales de respuesta directa."""

from __future__ import annotations

import argparse, asyncio, json, os, re, sys, unicodedata
from pathlib import Path
from typing import Any

import httpx

BASE = "http://127.0.0.1:7008"
RUN_ID = "492acd8d-06bd-42ac-a511-f3ec52f97bb3"
REPORT_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data/reports/breslov/2026-07-09-book-qa-v2-kitzur-level1"


def _norm(t: str) -> str:
    """Normalize: lowercase, strip accents, collapse spaces."""
    t = unicodedata.normalize("NFKD", t.lower())
    t = t.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip()


def score_question(q: dict, result: dict) -> dict[str, Any]:
    score = 0
    details = []
    sources = result.get("sources", [])
    conc = result.get("short_conclusion", "")
    answer_type = result.get("answer_type", "?")

    # 1. HTTP 200 (2 pts)
    if not result.get("error"):
        score += 2
    else:
        return {"score": 0, "max": 20, "details": "HTTP error", "status": "FAIL"}

    # 2. answer_type correcto o razonable (2 pts)
    expected_type = q.get("expected_answer_type", "")
    if answer_type == expected_type:
        score += 2; details.append("answer_type: correcto")
    elif answer_type == "concept_lookup" and expected_type == "phrase_lookup":
        score += 1; details.append("answer_type: phrase esperado, concept obtenido")
    else:
        details.append(f"answer_type: esperaba {expected_type}, obtuvo {answer_type}")

    # 3. Página esperada encontrada (5 pts)
    expected_pages = q.get("expected_pages", [])
    found_pages = [s.get("page_number") for s in sources if s.get("page_number")]
    found_ep = [p for p in expected_pages if p in found_pages]
    if found_ep:
        score += 5; details.append(f"página: {found_ep}")
    else:
        # Check nearby pages
        nearby = [p for p in expected_pages for fp in found_pages if abs(p - fp) <= 2]
        if nearby:
            score += 3; details.append(f"página: cercana ({nearby})")
        else:
            details.append(f"página: no encontrada ({expected_pages}, found: {found_pages[:3]})")

    # 4. Fragmentos esperados en snippets (5 pts)
    expected_frags = q.get("expected_text_fragments", [])
    all_text = " ".join(s.get("snippet", "") for s in sources) + " " + conc
    all_norm = _norm(all_text)
    found_frags = []
    for f in expected_frags:
        if _norm(f) in all_norm:
            found_frags.append(f)
    ratio = len(found_frags) / max(len(expected_frags), 1)
    if ratio >= 0.8:
        score += 5; details.append(f"fragmentos: {len(found_frags)}/{len(expected_frags)}")
    elif ratio >= 0.5:
        score += 3; details.append(f"fragmentos: parcial {len(found_frags)}/{len(expected_frags)}")
    else:
        score += 1; details.append(f"fragmentos: bajo {len(found_frags)}/{len(expected_frags)}")

    # 5. Respuesta esperada inferible (3 pts)
    expected = _norm(q.get("expected_answer", ""))
    if expected and expected in all_norm:
        score += 3; details.append("respuesta: presente en fuentes")
    else:
        # Check any fragment match
        if found_frags:
            score += 2; details.append("respuesta: parcial (fragmentos encontrados)")
        else:
            details.append("respuesta: no encontrada")

    # 6. Método correcto (2 pts)
    method = result.get("method", {})
    if method.get("retrieval") == "postgres_v2_sql_only" and not method.get("used_milvus") and not method.get("used_ai"):
        score += 2; details.append("método: SQL-only, sin Milvus/IA")
    else:
        score += 1

    # 7. Warnings honestos (1 pt)
    warnings = result.get("warnings", [])
    no_evidence = any("not_found" in w or "no_evidence" in w for w in warnings)
    if no_evidence:
        score -= 1; details.append("warnings: no_evidence")
    else:
        score += 1; details.append("warnings: OK")

    score = max(0, min(score, 20))
    status = "PASS fuerte" if score >= 18 else "PASS usable" if score >= 15 else "WARN" if score >= 10 else "FAIL"
    return {"score": score, "max": 20, "details": "; ".join(details), "status": status, "found_frags": len(found_frags), "total_frags": len(expected_frags)}


def render_markdown(q: dict, result: dict, scoring: dict) -> str:
    lines = [
        f"# {q['id']}", "",
        f"## Pregunta", q["question"], "",
        f"## Esperado", f"Respuesta: {q.get('expected_answer','')}", f"Páginas: {q.get('expected_pages',[])}", "",
        f"## Resultado", f"HTTP: {'200' if not result.get('error') else result.get('status_code','?')}",
        f"answer_type: {result.get('answer_type','?')}",
        f"score: {scoring['score']}/{scoring['max']}", f"status: {scoring['status']}", "",
        f"## Conclusión corta", result.get("short_conclusion", ""), "",
        "## Fuentes",
    ]
    for s in result.get("sources", [])[:5]:
        snip = (s.get("snippet") or "")[:300].replace("\n", " ").strip()
        lines += [f"### Página {s.get('page_number','?')} — {s.get('evidence_type','?')}", f"{snip}", ""]

    lines += ["## Fragmentos esperados detectados"]
    all_text = " ".join(s.get("snippet", "") for s in result.get("sources", [])) + " " + result.get("short_conclusion", "")
    all_norm = _norm(all_text)
    for f in q.get("expected_text_fragments", []):
        found = _norm(f) in all_norm
        lines.append(f"- {'✅' if found else '❌'} {f}")

    lines += ["", "## Warnings"]
    for w in result.get("warnings", []):
        lines.append(f"- {w}")

    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="KITZUR Level 1 Book QA Acid Batch")
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--scope-code", default="breslov_test")
    parser.add_argument("--resolve-latest", action="store_true")
    parser.add_argument("--questions-file", type=Path, default=REPORT_BASE / "questions.json")
    parser.add_argument("--report-dir", type=Path, default=REPORT_BASE)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "raw").mkdir(exist_ok=True)
    (report_dir / "rendered").mkdir(exist_ok=True)

    with open(args.questions_file) as f:
        questions = json.load(f)

    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", "")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD", "")
    if not email or not password:
        print("ERROR: TEBAAI_E2E_ADMIN_EMAIL/PASSWORD required"); return 1

    rid = args.run_id

    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=10)
        token = r.json()["access_token"]

        if args.resolve_latest:
            r = await c.get(f"{BASE}/library/book-qa/runs/latest", headers={"Authorization": f"Bearer {token}"},
                            params={"scope_code": args.scope_code})
            data = r.json()
            if data.get("run"):
                rid = data["run"]["run_id"]
                print(f"Resolved latest run: {rid[:12]}...")

        results = []
        for q in questions:
            qid = q["id"]
            print(f"{qid}: {q['question'][:60]}...", file=sys.stderr)

            r = await c.post(f"{BASE}/library/book-qa", headers={"Authorization": f"Bearer {token}"}, json={
                "question": q["question"], "run_id": rid, "scope_code": args.scope_code, "top_k": args.top_k,
            }, timeout=60)
            result = r.json()
            scoring = score_question(q, result)
            results.append({"question": q, "result": result, "scoring": scoring})
            print(f"  → {scoring['score']}/20 {scoring['status']}", file=sys.stderr)

            # Save raw
            (report_dir / "raw" / f"{qid}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
            # Render
            md = render_markdown(q, result, scoring)
            (report_dir / "rendered" / f"{qid}.md").write_text(md)

    # Summary
    total = sum(r["scoring"]["score"] for r in results)
    max_s = len(questions) * 20
    pct = round(total / max_s * 100)
    gs = "PASS fuerte" if pct >= 90 else "PASS usable" if pct >= 75 else "WARN" if pct >= 50 else "FAIL"

    print(f"\nTotal: {total}/{max_s} ({pct}%) — {gs}", file=sys.stderr)
    print(f"\n| ID | Pregunta | Págs esperadas | Págs encontradas | Score | Estado |", file=sys.stderr)
    print(f"|---:|---|---|---:|---|", file=sys.stderr)
    for r in results:
        q = r["question"]
        res = r["result"]
        s = r["scoring"]
        found_pages = [str(s.get("page_number")) for s in res.get("sources", []) if s.get("page_number")]
        ep = q.get("expected_pages", [])
        print(f"| {q['id']} | {q['question'][:45]} | {ep} | {found_pages[:5]} | {s['score']}/20 | {s['status']} |", file=sys.stderr)

    summary = {
        "total_score": total, "max_score": max_s, "percentage": pct,
        "global_status": gs, "run_id": rid, "scope_code": args.scope_code,
        "method": "postgres_v2_sql_only",
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nReport: {report_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
