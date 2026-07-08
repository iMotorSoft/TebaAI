"""LiteLLM adapter for a bounded editorial answer over canonical evidence."""

from __future__ import annotations

import json
import re
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from globalVar import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LITELLM_TIMEOUT_SECONDS,
    RESEARCH_CONVERSATION_MODEL,
)
from modules.library.relation_qa_schemas import RelationQASource


class EditorialAIResult(BaseModel):
    short_conclusion: str = Field(..., min_length=1, max_length=1200)
    editorial_answer_markdown: str = Field(..., min_length=1, max_length=12000)
    editorial_certainty: Literal["low", "medium", "high"] = "low"
    ai_inference_used: bool = False
    source_ids: list[str] = Field(default_factory=list)


class RelationQAAIError(RuntimeError):
    """The editorial model transport or structured response was unusable."""


def validate_editorial_ai_result(
    result: EditorialAIResult,
    sources: list[RelationQASource],
    *,
    literal_relation_found: bool,
) -> EditorialAIResult:
    """Validate source IDs and enforce deterministic literalness boundaries."""
    allowed_ids = {
        source.source_id for source in sources if source.is_final_citation
    }
    used_ids = set(result.source_ids)
    bracket_ids = set(
        re.findall(r"\[(src_[A-Za-z0-9_-]+)\]", result.editorial_answer_markdown)
    )
    if not used_ids or not used_ids.issubset(allowed_ids):
        raise RelationQAAIError("AI response referenced unknown or empty source IDs")
    if not bracket_ids or not bracket_ids.issubset(allowed_ids):
        raise RelationQAAIError("AI markdown lacks valid source_id citations")
    if not literal_relation_found:
        combined = f"{result.short_conclusion}\n{result.editorial_answer_markdown}"
        false_literal_claim = re.search(
            r"\b(se encontr[oó]|existe|hay)\b.{0,40}"
            r"\b(conexi[oó]n|relaci[oó]n)\b.{0,25}\bliteral\b|"
            r"\bliteral\b.{0,25}\b(se encontr[oó]|existe|hay)\b",
            combined,
            re.IGNORECASE | re.DOTALL,
        )
        if false_literal_claim:
            raise RelationQAAIError("AI response promoted inference to literal evidence")
        result.ai_inference_used = True
        result.editorial_certainty = "low"
        if "no se encontró una relación literal" not in result.short_conclusion.casefold():
            result.short_conclusion = (
                "No se encontró una relación literal directa en el corpus recuperado. "
                + result.short_conclusion
            )
        result.editorial_answer_markdown = (
            "> **Sin relación literal:** la síntesis siguiente es editorial y puede "
            "incluir inferencia marcada.\n\n"
            + result.editorial_answer_markdown
        )
    return result


def _parse_json(content: str) -> dict:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1])
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, re.DOTALL)
        if not match:
            raise RelationQAAIError("AI response was not valid JSON")
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RelationQAAIError("AI response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RelationQAAIError("AI response JSON must be an object")
    return parsed


async def build_editorial_answer_with_ai(
    *,
    question: str,
    concept_a: str,
    concept_b: str,
    sources: list[RelationQASource],
    literal_relation_found: bool,
) -> EditorialAIResult:
    """Request strict JSON from GPT through LiteLLM and validate citations."""
    if not LITELLM_API_KEY:
        raise RelationQAAIError("LiteLLM API key is not configured")
    source_payload = [
        {
            "source_id": source.source_id,
            "document_title": source.document_title,
            "document_status": source.document_status,
            "page_number": source.page_number,
            "block_type": source.block_type,
            "editorial_role": source.editorial_role,
            "evidence_types": [value.value for value in source.evidence_types],
            "is_final_citation": source.is_final_citation,
            "snippet": source.snippet,
        }
        for source in sources[:20]
    ]
    system_prompt = """Respondé como editor/investigador bibliográfico de Breslov.
Usá solamente la evidencia recuperada. No inventes fuentes ni completes con conocimiento externo.
No presentes inferencia como literal. No mezcles texto principal, nota, fuente marginal y explicación editorial.
Si no hay evidencia literal, decilo. Si hay solo coocurrencia, decilo.
Si hay derash o remez, marcalo. Toda interpretación debe marcarse INFERIDA_POR_IA.
Toda afirmación debe citar uno o más source_id entre corchetes. Tono sobrio, no devocional.
Devolvé solo JSON con: short_conclusion, editorial_answer_markdown,
editorial_certainty (low|medium|high), ai_inference_used (boolean), source_ids (array)."""
    payload = {
        "model": RESEARCH_CONVERSATION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "concept_a": concept_a,
                        "concept_b": concept_b,
                        "literal_relation_found": literal_relation_found,
                        "sources": source_payload,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{LITELLM_BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {LITELLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise RelationQAAIError("LiteLLM editorial request failed") from exc
    if response.status_code != 200:
        raise RelationQAAIError(
            f"LiteLLM editorial request returned status {response.status_code}"
        )
    try:
        content = response.json()["choices"][0]["message"]["content"]
        result = EditorialAIResult.model_validate(_parse_json(content))
    except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
        raise RelationQAAIError("AI response failed structured validation") from exc

    return validate_editorial_ai_result(
        result,
        sources,
        literal_relation_found=literal_relation_found,
    )
