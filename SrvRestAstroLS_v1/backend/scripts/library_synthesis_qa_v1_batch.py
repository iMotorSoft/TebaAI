#!/usr/bin/env python3
"""Read-only Synthesis QA V1 batch for a single explicit Ingesta V2 run.

It is intentionally a script prototype: no corpus writes, no index changes, and
no implicit scope resolution.  PostgreSQL page text remains the final authority.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import psycopg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL, LITELLM_TIMEOUT_SECONDS, RESEARCH_CONVERSATION_MODEL
from modules.library.book_qa_service import run_book_qa
from modules.library.vector_backends import get_vector_backend
from scripts.book_qa_v2_hybrid_probe import probe as probe_hybrid_pages

PG = {"user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"], "host": os.environ.get("DB_PG_IP", "localhost"), "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai"}

QUESTIONS = [
    ("q1_teshuva", "Teshuvá", "Describe el proceso completo del arrepentimiento, teshuvá, según el Kitzur Likutey Moharán.", [20,21,29,30,31,32,33,65,66,204,205], [("humildad y silencio", ["avergüenzan", "insultos"]), ("confesión verbal", ["confesión verbal", "confesarse"]), ("juicio y temores", ["juzga a sí misma", "temores caídos"]), ("vergüenza y perdón", ["vergüenza", "perdonado"]), ("arrepentimiento continuo", ["arrepentirse de su arrepentimiento", "previas concepciones"]), ("correr y retornar", ["retornar", "experta en la ley"]), ("Keter / EHIéH", ["Keter", "EHIéH"])]),
    ("q2_pureza", "Pureza sexual", "Explica cómo alcanzar pureza sexual y sus beneficios espirituales.", [17,36,81,82,136,137,140,145], [("Lenguaje Sagrado", ["Lenguaje Sagrado", "habla sagrada"]), ("tzitzit", ["tzitzit", "ojos"]), ("pensamientos", ["pensamientos lujuriosos", "alejar la mente"]), ("plegaria y voz", ["digno de orar", "refine su voz"]), ("profecía y sustento", ["espíritu sagrado de profecía", "sustento sin esfuerzo"])]),
    ("q3_plegaria", "Plegaria perfecta", "Describe el proceso para alcanzar una plegaria perfecta.", [17,18,25,41,60,61,292,293,331,332], [("verdad", ["con honestidad", "verdad"]), ("Tzadikim", ["verdaderos Tzadikim", "unir sus plegarias"]), ("alegría", ["gran alegría", "alegría"]), ("obstáculos", ["pensamientos ajenos", "orgullo"]), ("paz", ["paz general", "paz en todos los mundos"])]),
    ("q4_hitbodedut", "Hitbodedut", "Explica hitbodedut, plegaria personal en reclusión, y sus beneficios.", [65,66,166,167,202,203,237,466], [("conversación y juicio", ["conversación con el Creador", "juzga a sí misma"]), ("temores y luz", ["temores caídos", "luz oculta"]), ("noche y lugar", ["durante la noche", "fuera de las zonas habitadas"]), ("unión a la fuente", ["unirse a Dios", "incluida en su fuente"]), ("idioma cotidiano", ["idioma que les sea más familiar", "Hitbodedut es una práctica"])]),
    ("q5_shabat", "Shabat", "Cómo se relaciona la santidad del Shabat con rectificación espiritual y alegría.", [159,160,328,341,343,344,404,461,462], [("fe y bendiciones", ["encarnación de la fe", "fuente de todas las bendiciones"]), ("daat y compasión", ["conocimiento sagrado", "compasión"]), ("comida y alma", ["comer en Shabat", "alma adicional"]), ("alegría y libertad", ["alegría del Shabat", "alcanza la libertad"])]),
    ("q6_punto_bueno", "Punto bueno / nekudá tová", "Explica el punto bueno, nekudá tová, y su importancia en el servicio a Dios.", [407,408,409,410,411], [("buscar el bien", ["punto bueno", "más puntos buenos"]), ("impureza y retorno", ["mezclado con mucha impureza", "retornar a Dios"]), ("vida, alegría y plegaria", ["vida y alegría", "orar como debe"]), ("líder de plegaria", ["recolectar todos los puntos buenos", "líder de la plegaria"]), ("juicio favorable", ["lado del mérito", "juzgar favorablemente"])]),
    ("q7_temor_angeles", "Temor perfecto y ángeles", "Describe el temor perfecto a Dios y el dominio sobre los ángeles.", [419,420,421,422,423,424], [("tres deseos", ["deseos de dinero", "placer sexual", "comida"]), ("Tres Festividades", ["Pesaj", "Shavuot", "Sukot"]), ("temor y plegaria", ["temor perfecto", "plegaria perfecta"]), ("ángeles", ["ángeles superiores se subordinan", "dominio sobre los ángeles"]), ("líderes y almas", ["verdaderos líderes", "almas de Israel"])]),
]

def quote(text: str, terms: list[str]) -> str:
    lower = text.lower()
    for term in terms:
        pos = lower.find(term.lower())
        if pos >= 0:
            return re.sub(r"\s+", " ", text[max(0, pos - 110):pos + 420]).strip()
    return ""

async def page_evidence(conn: psycopg.AsyncConnection, run_id: str, pages: list[int], claim: str, terms: list[str]) -> list[dict[str, Any]]:
    found = []
    async with conn.cursor() as cur:
        for page in pages:
            await cur.execute("SELECT text FROM library_pages_v2 WHERE run_id=%s AND page_number=%s", (run_id, page))
            row = await cur.fetchone()
            text = row[0] if row else ""
            snippet = quote(text, terms)
            if snippet:
                found.append({"source_id": f"{claim[:3]}_p{page}", "page": page, "language": "es", "method": "page_direct", "evidence_type": "literal", "quote": snippet, "score": 1.0})
    return found

def deterministic(question: str, claims: list[dict[str, Any]]) -> str:
    lines = [f"Según las fuentes verificadas para: {question}"]
    for item in claims:
        if item["accepted"]:
            ev = item["accepted"][0]
            lines.append(f"- {item['claim']}: {ev['quote'][:240]} [p. {ev['page']}]")
        else:
            lines.append(f"- {item['claim']}: NO_CONFIRMADO en las páginas verificadas.")
    return "\n".join(lines)

async def ai_synthesis(question: str, claims: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    if not LITELLM_API_KEY:
        return None, "litellm_key_missing"
    sources = [{"id": e["source_id"], "page": e["page"], "quote": e["quote"]} for c in claims for e in c["accepted"][:1]]
    if not sources:
        return None, "no_verified_evidence"
    prompt = {"question": question, "sources": sources, "rules": "Usá solo estas fuentes. Cada oración factual debe citar [id]. Si falta evidencia, escribí NO_CONFIRMADO. No inventes páginas."}
    payload = {"model": RESEARCH_CONVERSATION_MODEL, "messages": [{"role": "system", "content": "Sos un editor bibliográfico. Devolvé una síntesis breve en español con citas [id]."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}], "temperature": 0.1, "max_tokens": 1200}
    try:
        async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{LITELLM_BASE_URL}/v1/chat/completions", headers={"Authorization": f"Bearer {LITELLM_API_KEY}"}, json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        allowed = {s["id"] for s in sources}
        cited = set(re.findall(r"\[([A-Za-z0-9_]+)\]", content))
        if not content or not cited or not cited.issubset(allowed):
            return None, "ai_response_missing_or_unknown_citations"
        return content, None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        return None, f"ai_error:{type(exc).__name__}"

async def run(args: argparse.Namespace) -> int:
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "raw_requests").mkdir(exist_ok=True); (args.output / "raw_responses").mkdir(exist_ok=True)
    conn = await psycopg.AsyncConnection.connect(**PG)
    results = []; matrix = []; vector_backend = get_vector_backend(args.vector_backend)
    try:
        for qid, title, question, pages, claim_defs in QUESTIONS:
            hybrid_error = None
            try:
                hybrid = await probe_hybrid_pages(
                    question, args.run_id, args.milvus_collection,
                    top_k=args.top_k, sql_top_k=args.top_k, milvus_top_k=args.top_k,
                ) if not args.skip_hybrid else {"sources": [], "evidence_summary": {}}
            except Exception as exc:  # external derived index must never block canonical PG evidence
                hybrid = {"sources": [], "evidence_summary": {}}
                hybrid_error = f"semantic_retrieval_unavailable:{type(exc).__name__}"
            claims = []
            for claim, terms in claim_defs:
                direct = await page_evidence(conn, args.run_id, pages, claim, terms)
                book = await run_book_qa(conn, f"¿Dónde aparece {claim}?", run_id=args.run_id, scope_code=args.scope_code, top_k=args.top_k)
                try:
                    vector_hits = await vector_backend.search(
                        claim, args.scope_code, top_k=args.top_k,
                        filters={"run_id": args.run_id, "language": "es"},
                    )
                    vector_evidence = [
                        {
                            "source_id": f"vec_{qid}_{len(claims)+1}_{index + 1}",
                            "source_method": "vector", "vector_backend_used": hit.backend,
                            "chunk_id": hit.chunk_id, "document_id": hit.document_id,
                            "page": hit.page, "language": hit.language,
                            "distance": hit.distance, "score": hit.score,
                            "quote": hit.evidence_text, "evidence_type": "thematic",
                        }
                        for index, hit in enumerate(vector_hits)
                    ]
                except Exception as exc:
                    vector_evidence = []
                    vector_error = f"{type(exc).__name__}: {exc}"
                else:
                    vector_error = getattr(vector_backend, "last_error", None)
                accepted = direct[:1]
                claims.append({"claim_id": f"{qid}_{len(claims)+1}", "claim": claim, "page_direct": direct, "book_qa_hits": len(book.sources), "vector_evidence": vector_evidence, "vector_error": vector_error, "accepted": accepted, "status": "PASS" if accepted else "FAIL"})
            ai, ai_error = await ai_synthesis(question, claims) if args.use_ai else (None, "ai_disabled")
            fallback = deterministic(question, claims)
            hybrid_sources = hybrid.get("sources", [])
            result = {"question_id": qid, "question": question, "scope": args.scope_code, "run_id": args.run_id, "document_filter": "resolved by run", "claims": claims, "diagnostics": {"sql_hits": sum(len(c["page_direct"]) for c in claims), "fts_hits": 0, "milvus_hits": sum(1 for s in hybrid_sources if s.get("milvus_score", 0) > 0), "hybrid_hits": len(hybrid_sources), "vector_hits": sum(len(c["vector_evidence"]) for c in claims), "vector_backend_requested": args.vector_backend, "vector_backend_used": getattr(vector_backend, "backend_used", getattr(vector_backend, "name", "none")), "relation_qa_hits": 0, "book_qa_hits": sum(c["book_qa_hits"] for c in claims), "page_direct_hits": sum(len(c["page_direct"]) for c in claims), "methods_unavailable": ["FTS and Relation QA do not accept an Ingesta V2 run_id in current contracts"], "semantic_error": hybrid_error, "backend_runtime_model": RESEARCH_CONVERSATION_MODEL, "embedding_model": "openai_text_embedding_3_small", "ai_synthesis_used": ai is not None, "fallback_used": ai is None, "ai_error": ai_error, "hybrid_collection": args.milvus_collection}, "answer": ai or fallback, "final_status": "PASS" if all(c["status"] == "PASS" for c in claims) else "PARTIAL"}
            results.append(result); matrix.extend({"question_id": qid, **c} for c in claims)
            (args.output / "raw_requests" / f"{qid}.json").write_text(json.dumps({"question": question, "scope": args.scope_code, "run_id": args.run_id}, ensure_ascii=False, indent=2))
            (args.output / "raw_responses" / f"{qid}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await conn.close()
    (args.output / "results.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results))
    (args.output / "evidence_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2))
    if args.results_json:
        args.results_json.parent.mkdir(parents=True, exist_ok=True)
        args.results_json.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps({"questions": len(results), "pass": sum(r["final_status"] == "PASS" for r in results), "ai_used": sum(r["diagnostics"]["ai_synthesis_used"] for r in results)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True); parser.add_argument("--scope-code", required=True)
    parser.add_argument("--top-k", type=int, default=8); parser.add_argument("--use-ai", action="store_true")
    parser.add_argument("--milvus-collection", default="tebaai_breslov_bookqa_v2_kitzur_test_pages_v1")
    parser.add_argument("--vector-backend", choices=("milvus", "pgvector", "auto", "disabled"), default="auto")
    parser.add_argument("--skip-hybrid", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--results-json", type=Path)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
