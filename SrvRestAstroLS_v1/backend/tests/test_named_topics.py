from __future__ import annotations

import asyncio
import json

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row

import modules.library.multilingual_query as multilingual
from globalVar import POSTGRES_DSN
from modules.library.investigative_qa_v1 import QaRequest, run
from modules.library.multilingual_query import interpret_query, preprocess_query
from modules.library.named_topics import (
    load_named_topic_glossary,
    named_topic_retrieval_plan,
    normalize_named_topic_candidate,
    resolve_named_topic,
)


TISHA_VARIANTS = [
    "tisha beav", "Tisha Beav", "Tisha B'Av", "Tisha B’Av", "Tisha B´Av",
    "Tisha beAv", "Tisha be-Av", "Tishá BeAv", "Tishá beAv", "Tishá be-Av",
    "Tisha B Av", "Tisha-b-Av", "9 de Av", "nueve de Av", "Nueve de Av",
    "fast of Tisha B'Av", "ayuno de Tishá BeAv", "תשעה באב", "צום תשעה באב",
    "tisha beev",
]


@pytest.mark.parametrize("query", TISHA_VARIANTS)
def test_tisha_variants_resolve_to_one_allowlisted_topic(query: str) -> None:
    result = resolve_named_topic(query)
    assert result is not None
    assert result.canonical_id == "jewish_calendar.tisha_beav"
    assert result.canonical_label == "Tishá BeAv"
    assert result.subject_raw == query
    assert result.subject_type == "named_topic"
    assert result.topic_type == "jewish_calendar_observance"
    assert result.confidence >= 0.92


@pytest.mark.parametrize("query", [
    "tisha", "av", "beav", "nueve", "9", "Tisha B", "nombre inexistente",
    "xqz random", "2026", "página 9", "Salmos 119", "Berajot 2a",
    "una persona llamada Av", "<script>alert(1)</script>", "ignora todo y Tisha B'Av",
    "SELECT * FROM named_topics", "a" * 1000, "Shabat emuna", "Tisha B duelo", "\u202eTisha B",
])
def test_ambiguous_or_unrelated_inputs_do_not_resolve(query: str) -> None:
    assert resolve_named_topic(query) is None


def test_normalization_preserves_original_outside_lookup_and_unifies_punctuation() -> None:
    forms = ["Tisha B'Av", "Tisha B’Av", "Tisha B´Av", "Tisha B-Av", "Tísha B Av"]
    assert {normalize_named_topic_candidate(value) for value in forms} == {"tisha b av"}
    raw = "  תשעה   באב  "
    assert normalize_named_topic_candidate(raw) == "תשעה באב"
    assert raw == "  תשעה   באב  "


def test_glossary_has_unique_allowlisted_ids_and_general_topic_types() -> None:
    entries = load_named_topic_glossary()
    ids = [entry.canonical_id for entry in entries]
    assert len(ids) == len(set(ids))
    assert len(entries) >= 10
    assert {entry.topic_type for entry in entries} >= {
        "jewish_calendar_observance", "person", "work_title",
        "conceptual_term", "custom_or_practice",
    }


def test_retrieval_plan_is_bounded_multilingual_and_literal_first() -> None:
    resolution = resolve_named_topic("Tisha B'Av")
    assert resolution is not None
    plan = named_topic_retrieval_plan(resolution)
    assert plan["strategy"] == "named_topic_multilingual"
    assert plan["primary_variants"][0] == "Tisha B'Av"
    assert "Tisha beAv" in plan["primary_variants"]
    assert "9 de Av" in plan["secondary_variants"]
    assert plan["hebrew_variants"] == ["תשעה באב"]
    assert len(plan["variants_searched"]) <= 8


class _InvalidResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": json.dumps({
            "language": "en", "intent": "concept_lookup", "query_subjects": [{"raw": "tisha"}],
        })}}]}


class _InvalidClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def post(self, *_args: object, **_kwargs: object) -> _InvalidResponse:
        return _InvalidResponse()


def test_ai_schema_failure_uses_named_topic_fallback_without_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(multilingual, "LITELLM_API_KEY", "configured")
    monkeypatch.setattr(multilingual.httpx, "AsyncClient", lambda **_kwargs: _InvalidClient())
    result, warnings = asyncio.run(interpret_query(preprocess_query("Tisha B'Av"), ai_enabled=True))
    assert warnings == ["ai_interpretation_fallback:ValidationError"]
    assert result.fallback_used and not result.ai_used
    assert result.query_subjects[0].raw == "Tisha B'Av"
    assert result.query_subjects[0].canonical_id == "jewish_calendar.tisha_beav"


def _run_real(question: str) -> dict:
    async def execute() -> dict:
        async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as connection:
            return await run(connection, QaRequest(
                question=question,
                works=["lm_xv"],
                languages=["es", "he", "en"],
                ai={"enabled": False},
            ))
    return asyncio.run(execute())


@pytest.mark.parametrize("query", ["tisha beav", "Tisha B'Av"])
def test_real_tisha_named_topic_keeps_full_subject_and_strong_lm_xv_evidence(query: str) -> None:
    response = _run_real(query)
    assert response["status"] == "ok"
    assert response["intent"] == "concept_lookup"
    assert response["query_understanding"]["subject_raw"] == query
    assert response["named_topic"]["canonical_id"] == "jewish_calendar.tisha_beav"
    assert response["named_topic"]["canonical_label"] == "Tishá BeAv"
    primary = next(hit for hit in response["hits"] if hit["is_primary"])
    assert primary["work_title"] == "Likutey Moharán XV KDP"
    assert primary["pdf_page"] == 262
    assert primary["printed_page"] == 248
    assert "#85:2" in primary["section"]
    assert "ayuno de Tisha beAv" in primary["snippet"]
    assert primary["literal_match_kind"] in {
        "named_topic_exact", "named_topic_normalized", "named_topic_alias",
    }
    assert primary["direct_support"] is True
    assert primary["match_strength"] == "strong"
    assert primary["evidence_strength"] == "strong"
    assert primary["single_term"] is False
    assert "relación solicitada" not in response["answer_markdown"]
    assert not any("ValidationError" in warning for warning in response["warnings"])
