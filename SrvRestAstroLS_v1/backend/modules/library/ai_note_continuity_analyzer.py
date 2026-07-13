"""Audited LiteLLM adjudication for ambiguous editorial satellite blocks."""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
import httpx
from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL, LITELLM_DEFAULT_MODEL_ALIAS

PROMPT_VERSION = "lmii_note_continuity_v1"
ALLOWED = {"continuation_of_previous_note","new_unmarked_note","marginal_commentary","source_reference","editorial_note","citable_unlinked_satellite","unknown_non_citable"}

@dataclass(frozen=True)
class NoteDecision:
    decision: str; confidence: float; rationale: str; requires_human_review: bool; raw: dict[str, Any]; model_name: str

def fallback(reason: str) -> NoteDecision:
    return NoteDecision("citable_unlinked_satellite", 0.0, reason, True, {"fallback": reason}, "unavailable")

async def analyze(payload: dict[str, Any]) -> NoteDecision:
    prompt = "Return JSON only. Classify an editorial lower-page block. Never infer a continuation unless textual continuity is explicit. " + json.dumps(payload, ensure_ascii=False)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{LITELLM_BASE_URL}/v1/chat/completions", headers={"Authorization": f"Bearer {LITELLM_API_KEY}"}, json={"model": LITELLM_DEFAULT_MODEL_ALIAS, "messages":[{"role":"system","content":"You are a conservative scholarly editor."},{"role":"user","content":prompt}], "response_format":{"type":"json_object"}, "temperature":0})
            response.raise_for_status(); raw=json.loads(response.json()["choices"][0]["message"]["content"])
        decision=raw.get("decision"); confidence=float(raw.get("confidence",0)); rationale=str(raw.get("rationale","")).strip()
        if decision not in ALLOWED or not rationale or not 0 <= confidence <= 1: return fallback("invalid_ai_json")
        return NoteDecision(decision,confidence,rationale,bool(raw.get("requires_human_review",True)),raw,LITELLM_DEFAULT_MODEL_ALIAS)
    except Exception as exc:
        return fallback(f"litellm_failure:{type(exc).__name__}")
