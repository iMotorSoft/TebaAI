#!/usr/bin/env python3
"""
Breslov Research Conversation — Golden Questions Validation.

Validates 15 research questions against the Breslov research service.
Evaluates intent classification, retrieval, evidence, and source map correctness.

Usage:
  uv run python -m scripts.breslov_research_conversation_golden --dry-run
  uv run python -m scripts.breslov_research_conversation_golden --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Any

GOLDEN_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": 1,
        "query": "¿Qué es un Tzadik según Breslov?",
        "expected_intent": "find_sources",
        "expected_language": "es",
    },
    {
        "id": 2,
        "query": "¿Cómo vencer la tristeza?",
        "expected_intent": "find_sources",
        "expected_language": "es",
    },
    {
        "id": 3,
        "query": "¿Qué significa no tener miedo?",
        "expected_intent": "explain_concept",
        "expected_language": "es",
    },
    {
        "id": 4,
        "query": "¿En qué libros se toca el miedo?",
        "expected_intent": "list_books",
        "expected_language": "es",
    },
    {
        "id": 5,
        "query": "¿En qué libros se toca la tristeza?",
        "expected_intent": "list_books",
        "expected_language": "es",
    },
    {
        "id": 6,
        "query": "¿Qué relación hay entre miedo, fe y alegría?",
        "expected_intent": "compare_sources",
        "expected_language": "es",
    },
    {
        "id": 7,
        "query": "¿Dónde aparece hitbodedut / plegaria personal?",
        "expected_intent": "find_sources",
        "expected_language": "es",
    },
    {
        "id": 8,
        "query": "¿Qué dice La Potencia de la Plegaria sobre rezar?",
        "expected_intent": "find_sources",
        "expected_language": "es",
    },
    {
        "id": 9,
        "query": "¿Qué aparece en KITZUR sobre alegría?",
        "expected_intent": "find_sources",
        "expected_language": "es",
    },
    {
        "id": 10,
        "query": "¿Dónde aparece el puente angosto?",
        "expected_intent": "locate_literal",
        "expected_language": "es",
    },
    {
        "id": 11,
        "query": "¿Está citado literalmente o es una explicación?",
        "expected_intent": "evidence_check",
        "expected_language": "es",
    },
    {
        "id": 12,
        "query": "¿Esto aparece en otros libros o solo en Cruzando?",
        "expected_intent": "list_books",
        "expected_language": "es",
    },
    {
        "id": 13,
        "query": "Dame fuentes sobre desesperación.",
        "expected_intent": "find_sources",
        "expected_language": "es",
    },
    {
        "id": 14,
        "query": "Dame fuentes sobre alegría y servicio a Dios.",
        "expected_intent": "find_sources",
        "expected_language": "es",
    },
    {
        "id": 15,
        "query": "¿Qué no se puede afirmar todavía desde el corpus?",
        "expected_intent": "out_of_scope",
        "expected_language": "es",
    },
]


def classify_intent(query: str) -> str:
    """Simple deterministic intent classification for validation baseline."""
    q = query.lower()
    if any(w in q for w in ["dónde aparece", "dónde dice", "dame fuentes"]):
        return "find_sources"
    if "qué es" in q or "qué significa" in q or "cómo vencer" in q or "qué aparece" in q:
        return "find_sources"
    if any(w in q for w in ["relación", "diferencia", "compara"]):
        return "compare_sources"
    if "literalmente" in q or "literal" in q:
        return "locate_literal"
    if "en qué libros" in q or "qué libros" in q or "en otros libros" in q:
        return "list_books"
    if "cita" in q or "interpretación" in q or "citado" in q:
        return "evidence_check"
    if "no se puede afirmar" in q:
        return "out_of_scope"
    return "find_sources"


async def run_golden_questions(
    dry_run: bool = True,
    json_output: bool = False,
    use_conversation_analyzer: bool = True,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for q_def in GOLDEN_QUESTIONS:
        query = q_def["query"]
        print(f"\n{'─'*60}")
        print(f"  [{q_def['id']:02d}/15] {query}")
        print(f"{'─'*60}")

        result: dict[str, Any] = {
            "id": q_def["id"],
            "query": query,
            "expected_intent": q_def["expected_intent"],
            "expected_language": q_def["expected_language"],
        }

        if use_conversation_analyzer and not dry_run:
            from modules.library.conversation_analyzer import (
                ResearchConversationAnalyzer,
            )
            ca = ResearchConversationAnalyzer()
            analysis = ca.analyze(query)
            result["detected_intent"] = analysis.intent.value
            result["detected_language"] = analysis.language
            result["analysis_model"] = analysis.model_used
            result["analysis_fallback"] = analysis.analysis_fallback
            result["topic_terms"] = analysis.topic_terms
            result["expanded_terms"] = analysis.expanded_terms
            result["research_mode"] = analysis.research_mode.value
            print(f"  Intención detectada: {analysis.intent.value}")
            print(f"  Idioma: {analysis.language}")
            print(f"  Modo: {analysis.research_mode.value}")
            if analysis.topic_terms:
                print(f"  Términos: {', '.join(analysis.topic_terms[:5])}")
        else:
            intent = classify_intent(query)
            result["detected_intent"] = intent
            result["analysis_model"] = "deterministic_baseline"
            result["analysis_fallback"] = True
            print(f"  Intención detectada (baseline): {intent}")

        intent_ok = result["detected_intent"] == q_def["expected_intent"]
        result["intent_pass"] = intent_ok
        result["evaluation"] = "PASS" if intent_ok else "WARN"

        if intent_ok:
            print(f"  ✅ Intención correcta: {q_def['expected_intent']}")
        else:
            print(f"  ⚠️  Intención: esperada={q_def['expected_intent']}, detectada={result['detected_intent']}")

        if not dry_run:
            from modules.library.research_service import BreslovResearchService
            service = BreslovResearchService()
            answer = await service.research(query=query, top_k=10)
            result["answer_summary"] = answer.answer_summary
            result["evidence_counts"] = answer.evidence_counts
            result["documents_found"] = answer.documents_found
            result["chunks_found"] = answer.chunks_found
            result["source_count"] = len(answer.source_map)
            result["limitations"] = answer.limitations
            result["has_pg_text"] = all(
                bool(s.canonical_excerpt) for s in answer.source_map
            ) if answer.source_map else True

            has_literal = any(
                e.evidence_type.value in ("literal", "direct_quote")
                for e in (s.evidence for s in answer.source_map)
            )
            has_inference = any(
                e.evidence_type.value == "remez_derash_inference"
                for e in (s.evidence for s in answer.source_map)
            )
            no_pg = sum(
                1 for s in answer.source_map if not s.canonical_excerpt
            )
            result["has_literal_evidence"] = has_literal
            result["has_inference_evidence"] = has_inference
            result["no_pg_count"] = no_pg

            print(f"  Documentos: {answer.documents_found}, Fuentes: {len(answer.source_map)}")
            print(f"  Evidencia: {answer.evidence_counts}")
            if no_pg > 0:
                print(f"  ⚠️  {no_pg} fuentes sin texto PG")
                result["evaluation"] = "FAIL"
            if has_inference and not has_literal:
                print(f"  ⚠️  Solo evidencia inferencial")
                if result["evaluation"] == "PASS":
                    result["evaluation"] = "WARN"
        else:
            result["answer_summary"] = ""
            result["evidence_counts"] = {}
            result["documents_found"] = 0
            result["chunks_found"] = 0
            result["source_count"] = 0
            result["limitations"] = []
            result["has_literal_evidence"] = False
            result["has_inference_evidence"] = False
            result["no_pg_count"] = 0

        results.append(result)

    return results


def print_report(results: list[dict[str, Any]]) -> None:
    print(f"\n\n{'='*70}")
    print(f"  GOLDEN QUESTIONS REPORT")
    print(f"  {datetime.utcnow().isoformat()}")
    print(f"{'='*70}")

    pass_count = sum(1 for r in results if r.get("evaluation") == "PASS")
    warn_count = sum(1 for r in results if r.get("evaluation") == "WARN")
    fail_count = sum(1 for r in results if r.get("evaluation") == "FAIL")

    print(f"\n  PASS: {pass_count}/{len(results)}")
    print(f"  WARN: {warn_count}/{len(results)}")
    print(f"  FAIL: {fail_count}/{len(results)}")
    print(f"{'─'*70}")

    print(f"\n{'Query':<3} {'Evaluación':<10} {'Intención esperada':<20} {'Intención detectada':<20} {'Fuentes':<8}")
    print(f"{'─'*70}")
    for r in results:
        eval_str = r.get("evaluation", "?")
        print(f"{r['id']:<3} {eval_str:<10} {r['expected_intent']:<20} {r['detected_intent']:<20} {r.get('source_count', 0):<8}")

    print(f"\n{'─'*70}")
    print("  Detalle:")
    for r in results:
        print(f"\n  [{r['id']:02d}] {r['query'][:60]}")
        print(f"       Evaluación: {r.get('evaluation', '?')}")
        print(f"       Intención: esperada={r['expected_intent']}, detectada={r['detected_intent']}")
        if r.get("source_count", 0) > 0:
            print(f"       Fuentes: {r['source_count']}, Docs: {r['documents_found']}")
            print(f"       Evidencia: {r.get('evidence_counts', {})}")
        if r.get("no_pg_count", 0) > 0:
            print(f"       ⚠️  Sin PG: {r['no_pg_count']}")

    print(f"\n{'='*70}")
    print(f"  FIN DEL REPORTE")
    print(f"{'='*70}")


async def main():
    parser = argparse.ArgumentParser(
        description="Breslov Research Conversation — Golden Questions Validation"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo validar intención (sin retrieval ni PG)")
    parser.add_argument("--json", action="store_true",
                        help="Output en JSON")
    parser.add_argument("--no-analyzer", action="store_true",
                        help="Usar baseline determinístico (no conversation analyzer)")
    args = parser.parse_args()

    print(f"BRESLOV RESEARCH CONVERSATION — GOLDEN QUESTIONS")
    print(f"Dry run: {args.dry_run}")
    print(f"Conversation analyzer: {'no' if args.no_analyzer else 'yes'}")

    results = await run_golden_questions(
        dry_run=args.dry_run,
        json_output=args.json,
        use_conversation_analyzer=not args.no_analyzer,
    )

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    else:
        print_report(results)

    fail_count = sum(1 for r in results if r.get("evaluation") == "FAIL")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
