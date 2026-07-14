"""Audited LiteLLM adjudication for ambiguous editorial satellite blocks.

This module deliberately follows the proven Relation QA LiteLLM contract:
``RESEARCH_CONVERSATION_MODEL`` + ``/v1/chat/completions`` + JSON object.
It never falls back to another provider or model.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from globalVar import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LITELLM_TIMEOUT_SECONDS,
    RESEARCH_CONVERSATION_MODEL,
)

PROMPT_VERSION = "lmii_note_continuity_v2"
ALLOWED = {
    "continuation_of_previous_note",
    "new_unmarked_note",
    "marginal_commentary",
    "source_reference",
    "editorial_note",
    "citable_unlinked_satellite",
    "unknown_non_citable",
}


@dataclass(frozen=True)
class NoteDecision:
    decision: str
    confidence: float
    rationale: str
    requires_human_review: bool
    raw: dict[str, Any]
    model_name: str
    raw_request: dict[str, Any]
    raw_response: str
    parse_status: str
    fallback_reason: str | None = None


def fallback(reason: str, *, raw_request: dict[str, Any] | None = None, raw_response: str = "") -> NoteDecision:
    return NoteDecision(
        "citable_unlinked_satellite", 0.0, reason, True,
        {"fallback": reason}, RESEARCH_CONVERSATION_MODEL,
        raw_request or {}, raw_response, "fallback", reason,
    )


def prompt_text(payload: dict[str, Any], *, retry: bool = False) -> str:
    retry_clause = " La respuesta anterior no fue JSON válido: devolvé exclusivamente un objeto JSON válido." if retry else ""
    return """Evaluá un bloque editorial inferior de Likutey Moharán II como editor bibliográfico conservador.
No hagas interpretación doctrinal ni inventes relaciones. La página física siempre conserva la cita,
pero una relación fuerte sólo existe si la continuidad textual es clara. No conviertas la mera
coincidencia de página en relación fuerte y no confundas texto primario con nota.

Evaluá continuidad gramatical y temática, una nota previa abierta, conectores/minúsculas/cierres de
cita/referencias editoriales, y cambios abruptos de tema. Si no hay certeza, elegí
``citable_unlinked_satellite``. ``unknown_non_citable`` sólo aplica a texto roto o inutilizable.
Usá confidence >= 0.85 únicamente cuando el candidato completa de forma literal una oración o cita
truncada de la nota previa; si sólo hay afinidad temática, mantené confidence < 0.85.

Devolvé sólo JSON con exactamente estos campos:
decision (continuation_of_previous_note|new_unmarked_note|marginal_commentary|source_reference|
editorial_note|citable_unlinked_satellite|unknown_non_citable), target_note_number (string|null),
target_page (integer|null), target_content_node_hint (string|null), relation_type (string|null),
confidence (number 0..1), rationale (justificación breve), textual_continuity_signals (array de
strings), rejection_reasons (array de strings), requires_human_review (boolean).
""" + retry_clause + "\n\nCASO:\n" + json.dumps(payload, ensure_ascii=False)


def _extract_json(content: str) -> dict[str, Any]:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1]) if len(lines) >= 3 else value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, re.DOTALL)
        if not match:
            raise ValueError("response_not_json")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("response_not_object")
    return parsed


def _normalize(raw: dict[str, Any], request: dict[str, Any], response: str) -> NoteDecision:
    decision = raw.get("decision")
    rationale = str(raw.get("rationale", "")).strip()
    try:
        confidence = float(raw.get("confidence"))
    except (TypeError, ValueError):
        confidence = -1
    if decision not in ALLOWED or not rationale or not 0 <= confidence <= 1:
        return fallback("invalid_ai_json", raw_request=request, raw_response=response)
    normalized = {
        "decision": decision,
        "target_note_number": raw.get("target_note_number"),
        "target_page": raw.get("target_page"),
        "target_content_node_hint": raw.get("target_content_node_hint"),
        "relation_type": raw.get("relation_type"),
        "confidence": confidence,
        "rationale": rationale,
        "textual_continuity_signals": raw.get("textual_continuity_signals", []),
        "rejection_reasons": raw.get("rejection_reasons", []),
        "requires_human_review": bool(raw.get("requires_human_review", True)),
    }
    return NoteDecision(decision, confidence, rationale, normalized["requires_human_review"], normalized,
                        RESEARCH_CONVERSATION_MODEL, request, response, "parsed")


async def analyze(payload: dict[str, Any]) -> NoteDecision:
    """Ask LiteLLM once, retrying exactly once only for malformed JSON."""
    if not LITELLM_API_KEY:
        return fallback("litellm_key_missing")
    last_request: dict[str, Any] = {}
    last_response = ""
    for retry in (False, True):
        request = {
            "model": RESEARCH_CONVERSATION_MODEL,
            "messages": [
                {"role": "system", "content": "You are a conservative scholarly editor."},
                {"role": "user", "content": prompt_text(payload, retry=retry)},
            ],
            "temperature": 0,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
        }
        last_request = request
        try:
            async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{LITELLM_BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
                    json=request,
                )
            last_response = response.text
            if response.status_code != 200:
                return fallback(f"litellm_http_status:{response.status_code}", raw_request=request, raw_response=last_response)
            content = response.json()["choices"][0]["message"]["content"]
            try:
                return _normalize(_extract_json(content), request, last_response)
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                if retry:
                    return fallback("invalid_ai_json_after_retry", raw_request=request, raw_response=last_response)
        except httpx.HTTPError as exc:
            return fallback(f"litellm_failure:{type(exc).__name__}", raw_request=request, raw_response=last_response)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return fallback(f"litellm_response_error:{type(exc).__name__}", raw_request=request, raw_response=last_response)
    return fallback("invalid_ai_json_after_retry", raw_request=last_request, raw_response=last_response)
