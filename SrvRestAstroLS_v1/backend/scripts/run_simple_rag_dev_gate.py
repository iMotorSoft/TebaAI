"""Run the reproducible DEV A/B batch without mutating corpus or services."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from globalVar import POSTGRES_DSN
from modules.library.investigative_qa_v1 import QaRequest, run as run_advanced
from modules.library.simple_research_rag import run_simple_rag


QUESTIONS = [
    "Relación sangre y habla",
    "salmo 19",
    "el término escorpión con qué está relacionado",
    "azamra",
    "tristeza",
    "miedo",
    "hitbodedut",
    "emuná",
    "Rebe Najmán",
    "Likutey Moharán",
    "Rabí Natán",
    "Zohar",
    "Tzadik",
    "alegría",
    "verdad",
    "brit",
    "Mundo Venidero",
    "qué relación hay entre alegría y emuná",
    "What does Rebbe Nachman teach about fear?",
    "מהי התבודדות",
    "hitbodeduth",
    "¿Cómo explica Rebe Najmán que una persona puede transformar el miedo y la tristeza mediante la plegaria y la alegría?",
]


def _request(question: str) -> QaRequest:
    return QaRequest(
        question=question,
        phase="legacy",
        languages=["es", "en", "he"],
        include_thematic=True,
        max_hits_per_work=10,
        ai={"enabled": True, "model": "openai_gpt-5.4-nano"},
        conversation={},
    )


async def _run_one(question: str) -> dict[str, Any]:
    async with (
        await psycopg.AsyncConnection.connect(
            POSTGRES_DSN,
            row_factory=dict_row,
        ) as simple_conn,
        await psycopg.AsyncConnection.connect(
            POSTGRES_DSN,
            row_factory=dict_row,
        ) as advanced_conn,
    ):
        simple_result, advanced_result = await asyncio.gather(
            run_simple_rag(simple_conn, _request(question)),
            run_advanced(advanced_conn, _request(question)),
            return_exceptions=True,
        )
    if isinstance(simple_result, BaseException):
        simple: dict[str, Any] = {
            "status": "failed",
            "error": type(simple_result).__name__,
        }
    else:
        evidence = simple_result.get("evidence", [])
        simple = {
            "status": simple_result.get("research_status"),
            "compatibility_status": simple_result.get("status"),
            "original_query_preserved": simple_result.get("original_query") == question,
            "answer_present": bool(simple_result.get("answer_markdown")),
            "evidence_count": len(evidence),
            "primary_evidence_ids": simple_result.get("primary_evidence_ids", []),
            "first_selected_source": (
                {
                    "work": evidence[0].get("work"),
                    "pdf_page": evidence[0].get("pdf_page"),
                    "language": evidence[0].get("language"),
                    "evidence_id": evidence[0].get("evidence_id"),
                }
                if evidence else None
            ),
            "semantic_status": simple_result.get("retrieval", {}).get(
                "semantic_status"
            ),
            "literal_status": simple_result.get("retrieval", {}).get(
                "literal_status"
            ),
            "fallback": simple_result.get("processing", {}).get("fallback_used"),
            "duration_ms": simple_result.get("execution", {}).get("duration_ms"),
            "warnings": simple_result.get("warnings", []),
        }
    if isinstance(advanced_result, BaseException):
        advanced: dict[str, Any] = {
            "status": "failed",
            "error": type(advanced_result).__name__,
        }
    else:
        advanced = {
            "status": advanced_result.get("status"),
            "answer_present": bool(advanced_result.get("answer_markdown")),
            "evidence_count": len(advanced_result.get("hits", [])),
            "primary_evidence_ids": advanced_result.get(
                "primary_evidence_ids",
                [],
            ),
            "used_vector": advanced_result.get("execution", {}).get(
                "used_vector"
            ),
            "fallback": advanced_result.get("execution", {}).get(
                "used_deterministic_fallback"
            ),
            "duration_ms": advanced_result.get("execution", {}).get(
                "duration_ms"
            ),
            "warnings": advanced_result.get("warnings", []),
        }
    return {"question": question, "simple_rag": simple, "advanced": advanced}


async def main(output: Path) -> None:
    results = []
    for index, question in enumerate(QUESTIONS, 1):
        result = await _run_one(question)
        results.append(result)
        print(json.dumps({
            "progress": f"{index}/{len(QUESTIONS)}",
            "question": question,
            "simple_status": result["simple_rag"].get("status"),
            "advanced_status": result["advanced"].get("status"),
        }, ensure_ascii=False), flush=True)
    simple_durations = [
        float(item["simple_rag"]["duration_ms"])
        for item in results
        if item["simple_rag"].get("duration_ms") is not None
    ]
    advanced_durations = [
        float(item["advanced"]["duration_ms"])
        for item in results
        if item["advanced"].get("duration_ms") is not None
    ]
    payload = {
        "questions": len(results),
        "simple_valid": sum(
            item["simple_rag"].get("status")
            in {"complete", "partial", "degraded", "no_evidence"}
            and item["simple_rag"].get("original_query_preserved") is True
            and item["simple_rag"].get("answer_present") is True
            for item in results
        ),
        "simple_with_evidence": sum(
            int(item["simple_rag"].get("evidence_count") or 0) > 0
            for item in results
        ),
        "advanced_valid": sum(
            item["advanced"].get("status") in {"ok", "partial", "no_evidence"}
            and item["advanced"].get("answer_present") is True
            for item in results
        ),
        "advanced_with_primary_evidence": sum(
            bool(item["advanced"].get("primary_evidence_ids"))
            for item in results
        ),
        "latency_ms": {
            "simple_p50": (
                round(statistics.median(simple_durations), 2)
                if simple_durations else None
            ),
            "simple_max": round(max(simple_durations), 2) if simple_durations else None,
            "advanced_p50": (
                round(statistics.median(advanced_durations), 2)
                if advanced_durations else None
            ),
            "advanced_max": (
                round(max(advanced_durations), 2) if advanced_durations else None
            ),
        },
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in payload.items() if key != "results"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.output))
