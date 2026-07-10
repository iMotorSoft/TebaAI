#!/usr/bin/env python3
"""KITZUR Level 2 Book QA Acid Batch — preguntas de comprensión."""

from __future__ import annotations

import argparse, asyncio, json, os, re, sys, unicodedata
from pathlib import Path
from typing import Any

import httpx

BASE = "http://127.0.0.1:7008"
RUN_ID = "492acd8d-06bd-42ac-a511-f3ec52f97bb3"


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = t.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip()


def score_question(q: dict, result: dict) -> dict[str, Any]:
    score = 0
    details: list[str] = []
    sources = result.get("sources", [])
    conc = result.get("short_conclusion", "")
    answer_type = result.get("answer_type", "?")
    expected_type = q.get("expected_answer_type", "")

    # 1. HTTP 200 (2 pts)
    if not result.get("error"):
        score += 2
    else:
        return {"score": 0, "max": 25, "details": "HTTP error", "status": "FAIL"}

    # 2. answer_type (3 pts)
    if answer_type == expected_type:
        score += 3; details.append("answer_type: correcto")
    else:
        details.append(f"answer_type: esperaba {expected_type}, obtuvo {answer_type}")

    # 3. Pages (6 pts)
    expected_pages = q.get("expected_pages", [])
    found_pages = [s.get("page_number") for s in sources if s.get("page_number")]
    found_ep = [p for p in expected_pages if p in found_pages]
    nearby = [p for p in expected_pages for fp in found_pages if p not in found_ep and abs(p - fp) <= 2]
    if found_ep:
        score += 6; details.append(f"páginas: {found_ep}")
    elif nearby:
        score += 3; details.append(f"páginas: cercanas ({nearby})")
    else:
        details.append(f"páginas: {expected_pages} no encontradas, found: {found_pages[:3]}")

    # 4. Fragments (6 pts)
    expected_frags = q.get("expected_text_fragments", [])
    all_text = " ".join(s.get("snippet", "") for s in sources) + " " + conc
    all_norm = _norm(all_text)
    found_frags = []
    partial_frags = []
    for f in expected_frags:
        fn = _norm(f)
        if fn in all_norm:
            found_frags.append(f)
        elif any(word in all_norm for word in fn.split() if len(word) > 4):
            partial_frags.append(f)
    frag_score = min(6, len(found_frags) * 2 + len(partial_frags))
    score += frag_score
    details.append(f"fragmentos: {len(found_frags)} exactos, {len(partial_frags)} parciales ({frag_score}/6)")

    # 5. Multi-source coverage (3 pts)
    if len(expected_pages) > 1:
        found_unique = set(found_ep) | set(nearby)
        if len(found_unique) >= len(expected_pages):
            score += 3; details.append("multi-source: todas las fuentes")
        elif len(found_unique) >= 1:
            score += 1; details.append("multi-source: parcial")
        else:
            details.append("multi-source: ninguna")
    else:
        score += 3; details.append("multi-source: no aplica (página única)")

    # 6. Snippet permite inferir respuesta (3 pts)
    if found_frags or partial_frags:
        score += 3; details.append("snippet: inferible")
    else:
        details.append("snippet: no permite inferencia")

    # 7. Método (1 pt)
    method = result.get("method", {})
    if method.get("retrieval") == "postgres_v2_sql_only":
        score += 1; details.append("método: SQL-only")

    # 8. Warnings (1 pt)
    warnings = result.get("warnings", [])
    if any("not_found" in w or "no_evidence" in w for w in warnings):
        score -= 1
    else:
        score += 1

    score = max(0, min(score, 25))
    status = "PASS fuerte" if score >= 22 else "PASS usable" if score >= 18 else "WARN" if score >= 12 else "FAIL"
    return {"score": score, "max": 25, "details": "; ".join(details), "status": status,
            "found_frags": len(found_frags), "partial_frags": len(partial_frags),
            "total_frags": len(expected_frags)}


def render_markdown(q: dict, result: dict, scoring: dict) -> str:
    lines = [
        f"# {q['id']}", "",
        f"## Pregunta", q["question"], "",
        f"## Esperado", f"Respuesta: {q.get('expected_answer','')}", f"Páginas esperadas: {q.get('expected_pages',[])}", "",
        f"## Resultado",
        f"HTTP: {'200' if not result.get('error') else result.get('status_code','?')}",
        f"answer_type: {result.get('answer_type','?')}",
        f"score: {scoring['score']}/{scoring['max']}", f"status: {scoring['status']}", "",
        f"## Conclusión corta", result.get("short_conclusion", ""), "",
        "## Fuentes recuperadas",
    ]
    for s in result.get("sources", [])[:8]:
        snip = (s.get("snippet") or "")[:400].replace("\n", " ").strip()
        lines += [f"### Página {s.get('page_number','?')} — {s.get('evidence_type','?')}", f"{snip}", ""]

    all_text = " ".join(s.get("snippet", "") for s in result.get("sources", [])) + " " + result.get("short_conclusion", "")
    all_norm = _norm(all_text)
    lines += ["## Fragmentos esperados detectados"]
    for f in q.get("expected_text_fragments", []):
        fn = _norm(f)
        if fn in all_norm:
            lines.append(f"- ✅ {f}")
        elif any(word in all_norm for word in fn.split() if len(word) > 4):
            lines.append(f"- ⚠️ {f} (parcial)")
        else:
            lines.append(f"- ❌ {f}")

    lines += ["", "## Advertencias"]
    for w in result.get("warnings", []):
        lines.append(f"- {w}")
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="KITZUR Level 2 Book QA Acid Batch")
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--scope-code", default="breslov_test")
    parser.add_argument("--resolve-latest", action="store_true")
    parser.add_argument("--questions-file", type=Path)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--top-k", type=int, default=12)
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
            ep = q.get("expected_pages", [])
            fp = [str(s.get("page_number")) for s in result.get("sources", []) if s.get("page_number")]
            print(f"  → {scoring['score']}/{scoring['max']} {scoring['status']} pages={ep}→{fp[:4]}", file=sys.stderr)

            (report_dir / "raw" / f"{qid}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
            md = render_markdown(q, result, scoring)
            (report_dir / "rendered" / f"{qid}.md").write_text(md)

    total = sum(r["scoring"]["score"] for r in results)
    max_s = len(questions) * 25
    pct = round(total / max_s * 100)
    gs = "PASS fuerte" if pct >= 88 else "PASS usable" if pct >= 72 else "WARN" if pct >= 48 else "FAIL"

    print(f"\nTotal: {total}/{max_s} ({pct}%) — {gs}", file=sys.stderr)
    print(f"\n| ID | Pregunta | Págs esperadas | Págs encontradas | Fragmentos | Score | Estado |", file=sys.stderr)
    print(f"|---:|---|---|---|---:|---|", file=sys.stderr)
    for r in results:
        q = r["question"]
        s = r["scoring"]
        ep = q.get("expected_pages", [])
        fp = [str(s2.get("page_number")) for s2 in r["result"].get("sources", []) if s2.get("page_number")]
        frags = f"{s.get('found_frags',0)}+{s.get('partial_frags',0)}/{s.get('total_frags',0)}"
        print(f"| {q['id']} | {q['question'][:45]} | {ep} | {fp[:4]} | {frags} | {s['score']}/{s['max']} | {s['status']} |", file=sys.stderr)

    summary = {"total_score": total, "max_score": max_s, "percentage": pct, "global_status": gs, "run_id": rid}
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nReport: {report_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
