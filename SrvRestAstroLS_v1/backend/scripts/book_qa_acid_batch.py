#!/usr/bin/env python3
"""
Book QA Acid Batch — El Jardín de las Almas.

Test de precisión textual, localización por libro/página y fidelidad
al fragmento para preguntas con respuesta conocida.

Uso:
    uv run python -m scripts.book_qa_acid_batch
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BACKEND_HOST = os.environ.get("TEBAAI_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.environ.get("TEBAAI_BACKEND_PORT", "7008")
BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
SCOPE_CODE = "breslov_primary"

REPORT_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data/reports/breslov/2026-07-09-jardin-almas-book-qa-acid-test"


def e(label: str, value: Any) -> str:
    if value is None or value is False:
        return f"{label}: {value}"
    if value in ("", [], {}):
        return f"{label}: —"
    return f"{label}: {value}"


async def authenticate(email: str, password: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if r.status_code != 201:
            raise RuntimeError(f"Auth failed ({r.status_code}): {r.text}")
        return r.json()["access_token"]


async def query_relation_qa(
    token: str,
    question: str,
    concept_a: str | None = None,
    concept_b: str | None = None,
    use_ai: bool = True,
    top_k: int = 30,
) -> dict[str, Any]:
    payload = {
        "question": question,
        "language": "es",
        "top_k": top_k,
        "use_ai": use_ai,
        "knowledge_scope_code": SCOPE_CODE,
        "evidence_depth": "standard",
        "return_markdown": True,
        "debug": False,
    }
    if concept_a:
        payload["concept_a"] = concept_a
    if concept_b:
        payload["concept_b"] = concept_b

    async with httpx.AsyncClient() as client:
        start = time.time()
        r = await client.post(
            f"{BASE_URL}/library/relation-qa",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=120,
        )
        elapsed = round(time.time() - start, 2)
        if r.status_code != 200:
            return {"error": True, "status_code": r.status_code, "detail": r.text[:500], "elapsed": elapsed}
        return {"error": False, "status_code": 200, "elapsed": elapsed, "response": r.json()}


def check_source_match(result: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    """Check if the response found the right book, page, and fragment."""
    if result.get("error"):
        return {"book_ok": False, "page_ok": False, "fragment_ok": False, "details": "HTTP error"}

    r = result["response"]
    sources = r.get("sources", []) or r.get("source_map", [])
    answer_text = (
        r.get("answer", {}).get("editorial_answer_markdown", "")
        + "\n"
        + r.get("answer", {}).get("short_conclusion", "")
    ).lower()

    expected_book = question["book"].lower()
    expected_page = str(question["expected_page"])
    must_find = [m.lower() for m in question["must_find"]]

    # Check book
    book_ok = any(expected_book in (s.get("document_title") or "").lower() for s in sources)

    # Check page (exact or range)
    page_ok = False
    for s in sources:
        sp = s.get("page_number")
        if sp is not None:
            sp_str = str(sp)
            if "," in expected_page:
                pages = [p.strip() for p in expected_page.split(",")]
                if any(p == sp_str for p in pages):
                    page_ok = True
                    break
            elif "-" in expected_page:
                parts = expected_page.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    if int(parts[0]) <= sp <= int(parts[1]):
                        page_ok = True
                        break
            elif sp_str == expected_page:
                page_ok = True
                break

    # Check must_find terms appear in sources or answer
    fragment_ok = True
    missing_terms = []
    for term in must_find:
        found = False
        for s in sources:
            snippet = (s.get("snippet") or "").lower()
            if term in snippet:
                found = True
                break
        if not found and term in answer_text:
            found = True
        if not found:
            fragment_ok = False
            missing_terms.append(term)

    return {
        "book_ok": book_ok,
        "page_ok": page_ok,
        "fragment_ok": fragment_ok,
        "missing_terms": missing_terms,
        "source_count": len(sources),
        "used_milvus": r.get("method", {}).get("used_milvus", False),
        "synthesis_mode": r.get("method", {}).get("synthesis_mode", "?"),
        "ai_synthesis_status": r.get("method", {}).get("ai_synthesis_status", "?"),
        "warnings": r.get("warnings", []),
    }


def compute_score(check: dict[str, Any]) -> tuple[int, str]:
    book_ok = check.get("book_ok", False)
    page_ok = check.get("page_ok", False)
    fragment_ok = check.get("fragment_ok", False)
    missing = check.get("missing_terms", [])
    warnings = check.get("warnings", [])

    score = 0
    if book_ok:
        score += 3
    if page_ok:
        score += 4
    if fragment_ok:
        score += 5
    else:
        # Partial: each missing term reduces
        found_ratio = max(0, 1 - len(missing) / 7)
        score += round(5 * found_ratio)

    # Respuesta fiel: synthesis_mode=ai gives +3, fallback gives +1
    mode = check.get("synthesis_mode", "")
    if mode == "ai":
        score += 4
    elif mode == "deterministic_fallback":
        score += 2
    else:
        score += 1

    # No inventa
    has_ai_warning = any("ai_inference" in w or "inferida" in w.lower() for w in warnings)
    if not has_ai_warning:
        score += 2
    else:
        score += 1

    # Warnings adecuados
    has_no_literal = any("no_literal" in w for w in warnings)
    if has_no_literal or has_ai_warning:
        score += 2
    else:
        score += 1

    score = min(score, 20)

    if score >= 18:
        state = "PASS fuerte"
    elif score >= 15:
        state = "PASS usable"
    elif score >= 11:
        state = "WARN"
    else:
        state = "FAIL"

    return score, state


def format_rendered(q: dict[str, Any], result: dict[str, Any], check: dict[str, Any], score: int, state: str) -> str:
    lines = [
        f"# Q{q['id']:02d} — {q['question']}",
        "",
        f"## Nivel",
        f"{q['level']} — {q['level_name']}",
        "",
        f"## Libro esperado",
        q["book"],
        "",
        f"## Página esperada",
        str(q["expected_page"]),
        "",
        f"## Respuesta esperada",
        q["expected_answer_excerpt"],
        "",
        "## Respuesta obtenida",
    ]

    if result.get("error"):
        lines.append(f"ERROR HTTP {result['status_code']}: {result.get('detail', '?')}")
    else:
        r = result["response"]
        ans = r.get("answer", {})
        editorial = ans.get("editorial_answer_markdown", "")
        conclusion = ans.get("short_conclusion", "")
        lines.append(conclusion)
        if editorial:
            lines.append("")
            lines.append(editorial)

    lines += ["", "## Fuentes obtenidas"]
    if not result.get("error"):
        sources = (result["response"].get("sources", []) or result["response"].get("source_map", []))[:10]
        for idx, s in enumerate(sources, 1):
            snippet = (s.get("snippet") or "")[:250].replace("\n", " ")
            lines += [
                f"{idx}. {s.get('document_title', '?')}",
                f"   Página: {s.get('page_number') or '—'}",
                f"   Chunk: {s.get('chunk_id', '?')}",
                f"   Evidence type: {s.get('evidence_type', '?')}",
                f"   Score: {s.get('score') or '—'}",
                f"   Retrieval: {s.get('retrieval_method', '?')}",
                f"   Snippet: {snippet}",
                "",
            ]
    else:
        lines.append("No se obtuvieron fuentes.")

    lines += [
        "## Comparación editorial",
        f"- ¿Encontró el libro correcto?: {'sí' if check.get('book_ok') else 'no'}",
        f"- ¿Encontró la página correcta?: {'sí' if check.get('page_ok') else 'no'}",
        f"- ¿Encontró el fragmento esperado?: {'sí' if check.get('fragment_ok') else 'no (faltan: ' + ', '.join(check.get('missing_terms', [])) + ')'}",
        f"- Síntesis: {check.get('synthesis_mode', '?')} ({check.get('ai_synthesis_status', '?')})",
        f"- Milvus usado: {check.get('used_milvus', '?')}",
        f"- Warnings: {'; '.join(check.get('warnings', [])) or 'ninguno'}",
        "",
        f"## Score",
        f"{score}/20 — {state}",
    ]

    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Book QA Acid Batch — El Jardín de las Almas")
    parser.add_argument("--id", type=int, help="Run single question by ID")
    parser.add_argument("--no-ai", action="store_false", dest="use_ai", default=True)
    parser.add_argument(
        "--email",
        default=os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", ""),
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD", ""),
    )
    args = parser.parse_args()

    if not args.email or not args.password:
        print("ERROR: --email y --password requeridos")
        return 1

    # Load questions
    qpath = REPORT_BASE / "questions.json"
    with open(qpath) as f:
        all_questions = json.load(f)

    if args.id:
        questions = [q for q in all_questions if q["id"] == args.id]
    else:
        questions = all_questions

    # Authenticate
    print(f"Autenticando como {args.email}...", file=sys.stderr)
    token = await authenticate(args.email, args.password)
    print("OK\n", file=sys.stderr)

    results = []
    for q in questions:
        qid = q["id"]
        lvl = q["level"]
        question_text = q["question"]

        print(f"[Q{qid:02d}] (nivel {lvl}) {question_text[:80]}...", file=sys.stderr)

        result = await query_relation_qa(token, question_text, use_ai=args.use_ai, top_k=30)

        if not result.get("error"):
            print(f"  → {result['elapsed']}s | synthesis={result['response']['method']['synthesis_mode']} | milvus={result['response']['method']['used_milvus']}", file=sys.stderr)

        # Save raw
        raw_dir = REPORT_BASE / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"Q{qid:02d}.json"
        with open(raw_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        # Check
        check = check_source_match(result, q)
        score, state = compute_score(check)

        # Rendered
        rendered_dir = REPORT_BASE / "rendered"
        rendered_dir.mkdir(parents=True, exist_ok=True)
        md = format_rendered(q, result, check, score, state)
        md_path = rendered_dir / f"Q{qid:02d}.md"
        with open(md_path, "w") as f:
            f.write(md)

        print(f"  → score={score}/20 ({state}) | book={check['book_ok']} page={check['page_ok']} fragment={check['fragment_ok']}", file=sys.stderr)

        results.append({"id": qid, "level": lvl, "question": question_text[:60], "result": result, "check": check, "score": score, "state": state})

    # Summary
    print(f"\n{'='*70}")
    print(f"  BOOK QA ACID BATCH — El Jardín de las Almas — COMPLETE")
    print(f"{'='*70}")
    print(f"\n| ID | Nivel | Pregunta | Libro OK | Página OK | Fragmento OK | Score | Estado | Hallazgo |")
    print(f"|---:|---:|---|---|---|---:|---|---|")
    for r in results:
        c = r["check"]
        hallazgo = ""
        if not c["book_ok"]:
            hallazgo = "Libro incorrecto"
        elif not c["page_ok"]:
            hallazgo = "Página incorrecta"
        elif not c["fragment_ok"]:
            hallazgo = f"Faltan: {', '.join(c['missing_terms'][:3])}"
        elif c.get("synthesis_mode") == "deterministic_fallback":
            hallazgo = "Fallback determinístico"
        else:
            hallazgo = "OK"
        print(f"| {r['id']:02d} | {r['level']} | {r['question'][:45]} | {'sí' if c['book_ok'] else 'no'} | {'sí' if c['page_ok'] else 'no'} | {'sí' if c['fragment_ok'] else 'no'} | {r['score']} | {r['state']:<13} | {hallazgo} |")

    # Averages
    by_level = {}
    for r in results:
        by_level.setdefault(r["level"], []).append(r["score"])
    print(f"\n### Promedio por nivel")
    for lvl in sorted(by_level):
        scores = by_level[lvl]
        avg = sum(scores) / len(scores)
        levels = {1: "trivial", 2: "comprensión", 3: "síntesis", 4: "compleja"}
        print(f"  Nivel {lvl} ({levels.get(lvl, '?')}): {avg:.1f}/20")

    total_avg = sum(r["score"] for r in results) / len(results)
    print(f"\n  **Promedio global: {total_avg:.1f}/20**")

    # Write scores.md
    scores_path = REPORT_BASE / "scores.md"
    with open(scores_path, "w") as f:
        f.write("# Scores — El Jardín de las Almas - Book QA Acid Test\n\n")
        f.write(f"| ID | Nivel | Pregunta | Libro OK | Página OK | Fragmento OK | Score | Estado | Hallazgo |\n")
        f.write(f"|---:|---:|---|---|---|---:|---|---|\n")
        for r in results:
            c = r["check"]
            hallazgo = ""
            if not c["book_ok"]:
                hallazgo = "Libro incorrecto"
            elif not c["page_ok"]:
                hallazgo = "Página incorrecta"
            elif not c["fragment_ok"]:
                hallazgo = f"Faltan: {', '.join(c['missing_terms'][:3])}"
            elif c.get("synthesis_mode") == "deterministic_fallback":
                hallazgo = "Fallback determinístico"
            else:
                hallazgo = "OK"
            f.write(f"| {r['id']:02d} | {r['level']} | {r['question'][:45]} | {'sí' if c['book_ok'] else 'no'} | {'sí' if c['page_ok'] else 'no'} | {'sí' if c['fragment_ok'] else 'no'} | {r['score']} | {r['state']:<13} | {hallazgo} |\n")
        f.write(f"\n### Promedio por nivel\n")
        for lvl in sorted(by_level):
            scores = by_level[lvl]
            avg = sum(scores) / len(scores)
            levels = {1: "trivial", 2: "comprensión", 3: "síntesis", 4: "compleja"}
            f.write(f"- Nivel {lvl} ({levels.get(lvl, '?')}): {avg:.1f}/20\n")
        f.write(f"\n**Promedio global: {total_avg:.1f}/20**\n")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
