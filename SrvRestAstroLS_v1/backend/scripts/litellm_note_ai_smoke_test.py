"""Live contract smoke tests for LM II note adjudication via LiteLLM."""
from __future__ import annotations

import asyncio
import json

import httpx
from modules.library.ai_note_continuity_analyzer import analyze
from scripts.adjudicate_lmii_unknown_satellites import fetch_candidates
import psycopg
from psycopg.rows import dict_row
from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL, LITELLM_TIMEOUT_SECONDS, POSTGRES_DSN, RESEARCH_CONVERSATION_MODEL


async def check(name: str, payload: dict, expected: set[str], minimum: float | None = None) -> dict:
    result = await analyze(payload)
    ok = result.parse_status == "parsed" and result.decision in expected
    if minimum is not None:
        ok = ok and result.confidence >= minimum
    return {"name": name, "pass": ok, "decision": result.decision, "confidence": result.confidence,
            "parse_status": result.parse_status, "model": result.model_name, "fallback_reason": result.fallback_reason}


async def main() -> int:
    results = []
    async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{LITELLM_BASE_URL}/v1/chat/completions", headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"}, json={"model": RESEARCH_CONVERSATION_MODEL, "messages": [{"role": "user", "content": "Respondé sólo JSON: {\\\"ok\\\": true}"}], "temperature": 0, "max_tokens": 30, "response_format": {"type": "json_object"}})
    try:
        minimal_content = response.json()["choices"][0]["message"]["content"]
        minimal_ok = response.status_code == 200 and json.loads(minimal_content) == {"ok": True}
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        minimal_ok = False
    results.append({"name": "A_minimal_json", "pass": minimal_ok, "status_code": response.status_code, "model": RESEARCH_CONVERSATION_MODEL})
    results.append(await check("B_synthetic_continuation", {
        "candidate_block_text": "la emuná cada día mediante la plegaria.»", "candidate_geometry": {"lower_page": True},
        "previous_numbered_note_text": "1. «La plegaria fortalece", "previous_note_number": "1",
        "previous_note_page": 12, "candidate_physical_page": 13, "layout_classification": "lower_unmarked_block",
        "deterministic_candidate_reasons": ["la nota previa termina a mitad de una cita y el candidato completa exactamente su oración"],
        "next_numbered_note_text": "2. Comentario independiente sobre otra fuente."},
        {"continuation_of_previous_note"}, .85))
    results.append(await check("C_synthetic_negative", {
        "candidate_block_text": "Referencia bibliográfica: Jerusalén, 1988.",
        "previous_numbered_note_text": "1. La emuná se expresa en la plegaria y", "previous_note_number": "1",
        "previous_note_page": 12, "candidate_physical_page": 13, "layout_classification": "lower_unmarked_block"},
        {"citable_unlinked_satellite", "new_unmarked_note", "source_reference"}))
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        candidates = await fetch_candidates(conn, 1, include_processed=True)
    if candidates:
        result = await analyze(candidates[0]["payload"])
        results.append({"name": "D_real_case", "pass": result.parse_status == "parsed", "decision": result.decision,
                        "confidence": result.confidence, "parse_status": result.parse_status,
                        "model": result.model_name, "fallback_reason": result.fallback_reason})
    else:
        results.append({"name": "D_real_case", "pass": False, "reason": "no_fallback_candidate_available"})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(item["pass"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
