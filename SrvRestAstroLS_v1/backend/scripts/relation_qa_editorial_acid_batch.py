#!/usr/bin/env python3
"""
Relation QA Editorial Acid Batch — 10 preguntas investigativas para Breslov.

Evalúa la calidad editorial, auditabilidad y utilidad investigativa de las
respuestas generadas por POST /library/relation-qa.

Uso:
    uv run python -m scripts.relation_qa_editorial_acid_batch \\
        --questions data/reports/breslov/2026-07-09-relation-qa-editorial-acid-batch/batch_questions.json \\
        --output data/reports/breslov/2026-07-09-relation-qa-editorial-acid-batch \\
        --email admin@tebaai.ai --password <pass>

    # Sin IA (solo fuentes)
    uv run python -m scripts.relation_qa_editorial_acid_batch ... --no-ai

    # Solo una pregunta
    uv run python -m scripts.relation_qa_editorial_acid_batch ... --id 1

    # Solo preflight
    uv run python -m scripts.relation_qa_editorial_acid_batch ... --preflight-only

Requiere:
    - Backend TebaAI corriendo en TEBAAI_BACKEND_HOST:TEBAAI_BACKEND_PORT
    - Credenciales de admin para autenticación
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

SCOPE_CODE = "breslov_primary"
BACKEND_HOST = os.environ.get("TEBAAI_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.environ.get("TEBAAI_BACKEND_PORT", "7008")
BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"


# ── Preflight ─────────────────────────────────────────────────────────────────


async def preflight(client: httpx.AsyncClient, token: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    # Backend reachable
    try:
        r = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "probe@tebaai.ai", "password": "probe"},
            timeout=5,
        )
        checks["backend_reachable"] = "OK" if r.status_code in (401, 201) else f"WARN ({r.status_code})"
    except Exception as exc:
        checks["backend_reachable"] = f"FAIL ({exc})"
        return {"status": "BLOCKED", "checks": checks}

    # Auth works
    if token:
        try:
            r = await client.post(
                f"{BASE_URL}/library/relation-qa",
                headers={"Authorization": f"Bearer {token}"},
                json={"question": "probe"},
                timeout=10,
            )
            checks["auth_works"] = "OK" if r.status_code in (200, 422) else f"WARN ({r.status_code})"
        except Exception as exc:
            checks["auth_works"] = f"FAIL ({exc})"
    else:
        checks["auth_works"] = "SKIP (no token)"

    checks["no_writes_planned"] = "yes"
    return {"status": "PASS" if all(str(v).startswith("OK") or v == "SKIP (no token)" for v in checks.values()) else "WARN", "checks": checks}


def print_preflight_table(checks: dict[str, Any]) -> None:
    print(f"\n{'='*60}")
    print("  PRECHECK — Relation QA Editorial Acid Batch")
    print(f"{'='*60}")
    for check, val in sorted(checks.items()):
        icon = "OK" if str(val).startswith("OK") else "  "
        print(f"  {icon} {check:<35} {str(val):<30}")
    print(f"{'='*60}\n")


# ── Auth ──────────────────────────────────────────────────────────────────────


async def authenticate(email: str, password: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if r.status_code != 201:
            raise RuntimeError(f"Auth failed ({r.status_code}): {r.text}")
        body = r.json()
        return body["access_token"]


# ── Batch execution ───────────────────────────────────────────────────────────


async def run_single(
    client: httpx.AsyncClient,
    token: str,
    question: dict[str, Any],
    use_ai: bool,
    top_k: int,
) -> dict[str, Any]:
    payload = {
        "question": question["question"],
        "language": "es",
        "top_k": top_k,
        "use_ai": use_ai,
        "knowledge_scope_code": SCOPE_CODE,
        "evidence_depth": "standard",
        "return_markdown": True,
        "debug": False,
    }
    start = time.time()
    r = await client.post(
        f"{BASE_URL}/library/relation-qa",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=120,
    )
    elapsed = round(time.time() - start, 2)

    if r.status_code != 200:
        return {
            "id": question["id"],
            "slug": question["slug"],
            "question": question["question"],
            "error": True,
            "status_code": r.status_code,
            "detail": r.text[:500],
            "elapsed": elapsed,
        }

    body = r.json()
    return {
        "id": question["id"],
        "slug": question["slug"],
        "question": question["question"],
        "error": False,
        "status_code": r.status_code,
        "elapsed": elapsed,
        "response": body,
    }


# ── Markdown renderer ─────────────────────────────────────────────────────────


def render_markdown(result: dict[str, Any]) -> str:
    qid = result["id"]
    slug = result["slug"]
    question = result["question"]

    if result.get("error"):
        return (
            f"# {qid}. {question}\n\n"
            f"## ERROR\n\n"
            f"HTTP {result['status_code']}: {result['detail']}\n\n"
        )

    r = result["response"]
    answer = r.get("answer", {})
    concepts = r.get("concepts", {})
    evidence_summary = r.get("evidence_summary", {})
    sources = r.get("sources", []) or r.get("source_map", [])
    warnings_list = r.get("warnings", [])
    method = r.get("method", {})

    lines = [
        f"# {qid}. {question}",
        "",
        "## Conclusión corta",
        answer.get("short_conclusion", "No informado por el endpoint."),
        "",
        "## Respuesta editorial",
    ]

    editorial = answer.get("editorial_answer_markdown", "")
    if editorial:
        lines.append(editorial)
    else:
        lines.append("No informado por el endpoint.")
    lines.append("")

    # Concepts
    lines.append("## Conceptos detectados")
    for side in ("concept_a", "concept_b"):
        c = concepts.get(side, {})
        label = c.get("label", "?")
        variants = c.get("variants", [])
        lines.append(f"- **{side}**: {label}")
        if variants:
            lines.append(f"  - Variantes: {', '.join(variants[:10])}")
    lines.append("")

    # Evidence summary
    lines.append("## Resumen de evidencia")
    if evidence_summary:
        for etype, count in sorted(evidence_summary.items()):
            if count > 0:
                lines.append(f"- {etype}: {count}")
    else:
        lines.append("No informado por el endpoint.")
    lines.append("")

    # Sources
    lines.append("## Fuentes")
    if sources:
        for idx, src in enumerate(sources, 1):
            title = src.get("document_title", "?")
            page = src.get("page_number")
            chunk_id = src.get("chunk_id", "?")
            evidence_type = src.get("evidence_type", "?")
            evidence_types = src.get("evidence_types", [])
            score = src.get("score")
            retrieval_method = src.get("retrieval_method", "?")
            snippet = src.get("snippet", "")

            lines.append(f"### {idx}. {title}")
            if page is not None:
                lines.append(f"- Página: {page}")
            if chunk_id:
                lines.append(f"- Chunk: {chunk_id}")
            lines.append(f"- Tipo de evidencia: {evidence_type}")
            if evidence_types:
                lines.append(f"- Tipos completos: {', '.join(evidence_types[:5])}")
            if score is not None:
                lines.append(f"- Score: {score}")
            lines.append(f"- Método: {retrieval_method}")
            if snippet:
                lines.append(f"- Snippet:\n  > {snippet[:500]}")
            lines.append("")
    else:
        lines.append("No se encontraron fuentes.")
        lines.append("")

    # Warnings
    lines.append("## Advertencias")
    if warnings_list:
        for w in warnings_list:
            lines.append(f"- {w}")
    else:
        lines.append("No informado por el endpoint.")
    lines.append("")

    # Method
    lines.append("## Método")
    lines.append(f"- retrieval: {method.get('retrieval', [])}")
    lines.append(f"- llm_model: {method.get('llm_model', 'No informado')}")
    lines.append(f"- embedding_model: {method.get('embedding_model', 'No informado')}")
    lines.append(f"- used_pg_as_canonical: {method.get('used_pg_as_canonical', 'No informado')}")
    lines.append(f"- used_milvus: {method.get('used_milvus', 'No informado')}")
    lines.append(f"- used_ai: {method.get('used_ai', 'No informado')}")
    lines.append("")

    # Link to raw
    lines.append(f"## JSON source")
    lines.append(f"raw/{qid:02d}-{slug}.json")
    lines.append("")

    return "\n".join(lines)


# ── Editorial scores template ─────────────────────────────────────────────────


def editorial_scores_header() -> str:
    header = [
        "# Editorial Scores — Relation QA Editorial Acid Batch",
        "",
        "Evaluación por pregunta con puntaje 0–3 en cada criterio.",
        "Máximo por pregunta: 24.",
        "",
        "| ID | Pregunta | Conclusión | Fuentes | Evidencia | Warnings | Conceptos | Cobertura | UI/render | Método | Total | Estado | Observaciones |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    return "\n".join(header)


def editorial_scores_row(question: dict[str, Any], result: dict[str, Any]) -> str:
    qid = question["id"]
    slug = question["slug"]
    question_text = question["question"][:50]
    if result.get("error"):
        return f"| {qid} | {question_text}... | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | 0 | FAIL | HTTP {result['status_code']} |"
    return f"| {qid} | {question_text}... |  |  |  |  |  |  |  |  |  |  |  |"


# ── Main ──────────────────────────────────────────────────────────────────────


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Relation QA Editorial Acid Batch — 10 preguntas investigativas para Breslov"
    )
    parser.add_argument("--questions", required=True, help="Path to batch_questions.json")
    parser.add_argument("--output", required=True, help="Output directory for report")
    parser.add_argument("--email", default=os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", ""), help="Admin email for auth")
    parser.add_argument("--password", default=os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD", ""), help="Admin password for auth")
    parser.add_argument("--id", type=int, help="Run single question by ID")
    parser.add_argument("--preflight-only", action="store_true", help="Run preflight only")
    parser.add_argument("--no-ai", action="store_false", dest="use_ai", default=True, help="Disable AI synthesis")
    parser.add_argument("--top-k", type=int, default=20, help="Results per query (default: 20)")
    parser.add_argument("--skip-render", action="store_true", help="Skip markdown rendering and scores")
    args = parser.parse_args()

    output_dir = Path(args.output)
    raw_dir = output_dir / "raw"
    rendered_dir = output_dir / "rendered"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rendered_dir.mkdir(parents=True, exist_ok=True)

    # Load questions
    with open(args.questions) as f:
        all_questions = json.load(f)

    if args.id:
        questions = [q for q in all_questions if q["id"] == args.id]
        if not questions:
            print(f"ERROR: question id {args.id} not found")
            return 1
    else:
        questions = all_questions

    mode_label = "USE-AI" if args.use_ai else "NO-AI"

    print(f"\n{'='*70}")
    print(f"  RELATION QA EDITORIAL ACID BATCH — {mode_label}")
    print(f"  Questions: {len(questions)}")
    print(f"  Output: {output_dir}")
    print(f"{'='*70}")

    # Authenticate
    if not args.email or not args.password:
        print("ERROR: --email and --password required (or TEBAAI_E2E_ADMIN_EMAIL/PASSWORD env)")
        return 1

    print(f"\n  Authenticating as {args.email}...")
    token = await authenticate(args.email, args.password)
    print(f"  Token obtained: {token[:20]}...")

    # Preflight
    async with httpx.AsyncClient() as client:
        pf = await preflight(client, token)
        print_preflight_table(pf["checks"])

        if args.preflight_only:
            print("  Preflight only. No questions executed.")
            return 0

        # Run batch
        results = []
        for q in questions:
            qid = q["id"]
            slug = q["slug"]
            print(f"\n  [{qid:02d}/{len(questions)}] {q['question'][:80]}...")
            print(f"  {'─'*60}")

            result = await run_single(client, token, q, args.use_ai, args.top_k)
            results.append(result)

            elapsed = result.get("elapsed", 0)
            if result.get("error"):
                print(f"  ERROR ({result['status_code']}) in {elapsed}s")
            else:
                resp = result["response"]
                answer = resp.get("answer", {})
                sources = resp.get("sources", []) or resp.get("source_map", [])
                evidence = resp.get("evidence_summary", {})
                print(f"  OK in {elapsed}s")
                print(f"  Conclusion: {answer.get('short_conclusion', '?')[:100]}")
                print(f"  Sources: {len(sources)} | Evidence types: {len(evidence)}")
                if answer.get("literal_relation_found"):
                    print(f"  LITERAL relation found")
                if answer.get("ai_inference_used"):
                    print(f"  AI inference used (certainty: {answer.get('editorial_certainty', '?')})")

            # Save raw JSON
            raw_path = raw_dir / f"{qid:02d}-{slug}.json"
            with open(raw_path, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"  → raw/{qid:02d}-{slug}.json")

            # Render markdown
            if not args.skip_render:
                md = render_markdown(result)
                md_path = rendered_dir / f"{qid:02d}-{slug}.md"
                with open(md_path, "w") as f:
                    f.write(md)
                print(f"  → rendered/{qid:02d}-{slug}.md")

        # Generate editorial scores
        if not args.skip_render:
            scores_lines = [editorial_scores_header()]
            for q in questions:
                matching = [r for r in results if r["id"] == q["id"]]
                if matching:
                    scores_lines.append(editorial_scores_row(q, matching[0]))
                else:
                    scores_lines.append(f"| {q['id']} | {q['question'][:50]}... | SKIP | SKIP | SKIP | SKIP | SKIP | SKIP | SKIP | SKIP | 0 | SKIP | No ejecutada |")
            scores_lines.append("")
            scores_lines.append("## Resumen")
            passed = sum(1 for r in results if not r.get("error"))
            failed = sum(1 for r in results if r.get("error"))
            scores_lines.append(f"- Ejecutadas: {len(results)}")
            scores_lines.append(f"- Exitosas: {passed}")
            scores_lines.append(f"- Fallidas: {failed}")

            scores_path = output_dir / "editorial_scores.md"
            with open(scores_path, "w") as f:
                f.write("\n".join(scores_lines) + "\n")
            print(f"\n  → editorial_scores.md")

    # Summary
    print(f"\n{'='*70}")
    print(f"  RELATION QA EDITORIAL ACID BATCH — COMPLETE")
    print(f"  Mode: {mode_label}")
    print(f"  Output: {output_dir}")
    print(f"{'='*70}")
    print(f"\n  {'ID':<5} {'Slug':<25} {'Status':<10} {'Time':<8}")
    print(f"  {'─'*5} {'─'*25} {'─'*10} {'─'*8}")
    for r in results:
        status = "OK" if not r.get("error") else f"ERR({r.get('status_code','?')})"
        print(f"  {r['id']:<5} {r['slug']:<25} {status:<10} {r.get('elapsed',0):<8.1f}s")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
