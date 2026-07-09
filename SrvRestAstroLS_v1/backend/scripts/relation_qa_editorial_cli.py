#!/usr/bin/env python3
"""
Relation QA Editorial CLI — consulta interactiva desde terminal.

Obtiene respuestas de POST /library/relation-qa y las muestra en formato
legible para copiar y evaluar editorialmente.

Uso:
    uv run python scripts/relation_qa_editorial_cli.py "¿Dónde habla Rabí Najmán sobre la tristeza?"
    uv run python scripts/relation_qa_editorial_cli.py --save "¿Dónde aparece hitbodedut?"
    uv run python scripts/relation_qa_editorial_cli.py  # modo interactivo

En modo interactivo:
    Pregunta> ¿Dónde habla Rabí Najmán sobre la tristeza?
    :quit  o  :exit  o  :q  para salir
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BACKEND_HOST = os.environ.get("TEBAAI_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.environ.get("TEBAAI_BACKEND_PORT", "7008")
BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

SCOPE_CODE = "breslov_primary"


def e(label: str, value: Any) -> str:
    if value is None or value is False:
        return f"{label}: {value}"
    if value == "" or value == []:
        return f"{label}: —"
    return f"{label}: {value}"


def format_response(result: dict[str, Any], top_sources: int = 5) -> str:
    if result.get("error"):
        return f"## ERROR\n\nHTTP {result['status_code']}: {result.get('detail', '?')}"

    r = result["response"]
    ans = r.get("answer", {})
    method = r.get("method", {})
    concepts = r.get("concepts", {})
    evidence = r.get("evidence_summary", {})
    sources = (r.get("sources", []) or r.get("source_map", []))[:top_sources]
    warnings = r.get("warnings", [])

    lines = [
        "## Pregunta",
        r.get("question", "?"),
        "",
        "## Modo de síntesis",
        e("synthesis_mode", method.get("synthesis_mode")),
        e("ai_synthesis_status", method.get("ai_synthesis_status")),
        e("ai_synthesis_attempts", method.get("ai_synthesis_attempts")),
        e("fallback_used", method.get("fallback_used")),
        e("fallback_reason", method.get("fallback_reason")),
        "",
        "## Conclusión corta",
        ans.get("short_conclusion", "—"),
        "",
    ]

    editorial = ans.get("editorial_answer_markdown", "")
    if editorial:
        lines += ["## Respuesta editorial", editorial, ""]

    ca = concepts.get("concept_a", {})
    cb = concepts.get("concept_b", {})
    lines += [
        "## Conceptos detectados",
        f"Concepto A:",
        f"  label: {ca.get('label', '?')}",
        f"  variants: {', '.join(ca.get('variants', []))}",
        f"Concepto B:",
        f"  label: {cb.get('label', '?')}",
        f"  variants: {', '.join(cb.get('variants', []))}",
        "",
        "## Resumen de evidencia",
    ]
    for etype, count in sorted(evidence.items()):
        if count > 0:
            lines.append(f"- {etype}: {count}")
    lines.append("")

    if sources:
        lines.append(f"## Fuentes principales (primeras {len(sources)})")
        for idx, src in enumerate(sources, 1):
            snippet = (src.get("snippet") or "")[:300].replace("\n", " ")
            lines += [
                f"{idx}. {src.get('document_title', '?')}",
                f"   Página: {src.get('page_number') or '—'}",
                f"   Chunk: {src.get('chunk_id', '?')}",
                f"   Tipo de evidencia: {src.get('evidence_type', '?')}",
                f"   Score: {src.get('score') or '—'}",
                f"   Método: {src.get('retrieval_method', '?')}",
                f"   Snippet: {snippet}",
                "",
            ]
    else:
        lines += ["## Fuentes principales", "—", ""]

    if warnings:
        lines += ["## Advertencias"]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines += [
        "## Método",
        e("retrieval", method.get("retrieval")),
        e("llm_model", method.get("llm_model") or "—"),
        e("embedding_model", method.get("embedding_model")),
        e("used_pg_as_canonical", method.get("used_pg_as_canonical")),
        e("used_milvus", method.get("used_milvus")),
        e("used_ai", method.get("used_ai")),
        "",
        "## Evaluación editorial pendiente",
        "Veredicto: pendiente",
        "Duda editorial:",
    ]

    return "\n".join(lines).strip()


async def query(
    token: str, question: str, use_ai: bool = True, top_k: int = 20
) -> dict[str, Any]:
    payload = {
        "question": question,
        "language": "auto",
        "top_k": top_k,
        "use_ai": use_ai,
        "knowledge_scope_code": SCOPE_CODE,
        "evidence_depth": "standard",
        "return_markdown": True,
        "debug": False,
    }
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
            return {
                "error": True,
                "status_code": r.status_code,
                "detail": r.text[:500],
                "elapsed": elapsed,
            }
        return {
            "error": False,
            "status_code": r.status_code,
            "elapsed": elapsed,
            "response": r.json(),
        }


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


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Relation QA Editorial CLI — consulta interactiva desde terminal"
    )
    parser.add_argument("question", nargs="*", help="Pregunta directa (opcional, si se omite entra en modo interactivo)")
    parser.add_argument("--no-ai", action="store_false", dest="use_ai", default=True, help="Deshabilitar IA")
    parser.add_argument("--top-k", type=int, default=20, help="Resultados por consulta")
    parser.add_argument("--top-sources", type=int, default=5, help="Fuentes a mostrar")
    parser.add_argument("--save", metavar="DIR", nargs="?", const=".", default=None, help="Guardar JSON crudo en directorio")
    parser.add_argument(
        "--email",
        default=os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", ""),
        help="Email admin (default: TEBAAI_E2E_ADMIN_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD", ""),
        help="Password admin (default: TEBAAI_E2E_ADMIN_PASSWORD)",
    )
    args = parser.parse_args()

    if not args.email or not args.password:
        print("ERROR: Se necesita --email y --password o TEBAAI_E2E_ADMIN_EMAIL/PASSWORD")
        return 1

    print(f"Autenticando como {args.email}...", file=sys.stderr)
    token = await authenticate(args.email, args.password)
    print("OK\n", file=sys.stderr)

    if args.question:
        questions = [" ".join(args.question)]
    else:
        questions = []
        print("Modo interactivo. Escribí ':quit' para salir.\n")
        while True:
            try:
                q = input("Pregunta> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if q in (":quit", ":exit", ":q"):
                break
            if q:
                questions.append(q)

    for i, q in enumerate(questions):
        if len(questions) > 1:
            sep = f"\n{'='*70}\n--- Pregunta {i+1}/{len(questions)} ---\n{'='*70}\n"
            print(sep)

        print(f"Consultando: {q[:120]}...", file=sys.stderr)
        result = await query(token, q, args.use_ai, args.top_k)

        elapsed = result.get("elapsed", 0)
        if result.get("error"):
            print(f"ERROR ({result['status_code']}) in {elapsed}s")
            continue

        print(f"({elapsed}s)\n", file=sys.stderr)

        output = format_response(result, args.top_sources)
        print(output)
        print()

        if args.save is not None:
            save_dir = Path(args.save) if args.save != "." else Path.cwd()
            save_dir.mkdir(parents=True, exist_ok=True)
            slug = q.lower().strip()[:40]
            slug = "".join(c if c.isalnum() or c in " -" else "" for c in slug).strip().replace(" ", "-")
            fpath = save_dir / f"{i+1:02d}-{slug}.json"
            with open(fpath, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"  (JSON guardado: {fpath})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
