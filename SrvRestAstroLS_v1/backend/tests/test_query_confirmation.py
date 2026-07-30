from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from litestar import Litestar
from litestar.testing import TestClient

import modules.library.investigative_qa_v1 as qa
from modules.library.investigative_qa_v1 import (
    PreparedQuery,
    QaRequest,
    display_interpretation,
    interpret_only,
)
from modules.library.multilingual_query import deterministic_interpret, preprocess_query
from modules.library.named_topics import resolve_named_topic
from modules.library.query_confirmation import (
    INTERPRETATION_STORE,
    InterpretationStateError,
    InterpretationStore,
)
from modules.library.routes import investigative_qa_v1


def _prepared(question: str) -> PreparedQuery:
    return PreparedQuery(
        structured=deterministic_interpret(preprocess_query(question)),
        named_topic=resolve_named_topic(question),
        warnings=(),
        preprocessing=preprocess_query(question).model_dump(),
        glossary_duration_ms=0,
    )


@pytest.mark.asyncio
async def test_interpret_phase_never_calls_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("retrieval must not run during interpretation")

    monkeypatch.setattr(qa, "_fetch", forbidden)
    monkeypatch.setattr(qa, "_phrase_fetch", forbidden)
    prepared, response = await interpret_only(
        QaRequest(question="tisha beav", phase="interpret", ai={"enabled": False})
    )

    assert prepared.named_topic is not None
    assert response["status"] == "awaiting_confirmation"
    assert "Tishá BeAv" in response["display_interpretation"]
    assert response["actions"] == ["analyze", "modify"]
    assert response["execution"]["retrieval_executed"] is False
    assert "hits" not in response
    assert "claims" not in response


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("tisha beav", "Interpreté que desea investigar referencias sobre Tishá BeAv."),
        (
            "donde aparece Oraj Jaim 1",
            "Interpreté que desea localizar la referencia estructural «Oraj Jaim 1».",
        ),
        (
            "Moshé, tú lo has dicho bien",
            "Interpreté que desea localizar la frase «Moshé, tú lo has dicho bien».",
        ),
        (
            "con qué conceptos aparece escorpión",
            "Interpreté que desea saber con qué conceptos aparece relacionado «escorpión».",
        ),
        (
            "azamra la relaciones que tiene",
            "Interpreté que desea saber con qué conceptos aparece relacionado «Azamra».",
        ),
        (
            "relación entre Tishá BeAv y los veintiún días",
            "Interpreté que desea investigar la relación entre «Tishá BeAv» y «los veintiún días».",
        ),
    ],
)
def test_controlled_display_templates(question: str, expected: str) -> None:
    assert display_interpretation(QaRequest(question=question), _prepared(question)) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "tisha beav",
        "Tisha B'Av",
        "תשעה באב",
        "donde aparece Oraj Jaim 1",
        "where is Orach Chaim 1 mentioned",
        "Moshé, tú lo has dicho bien",
        "servir a HaShem por la noche",
        "איפה מופיע תהלתי אחטם לך",
        "con qué conceptos aparece escorpión",
        "where does scorpion appear",
        "איפה נמצא המושג עקרב",
        "relación entre sangre y el habla",
        "relación entre Tishá BeAv y los veintiún días",
        "relation between prayer and joy",
        "comparar sangre y habla",
        "versículos de Salmos 119",
        "referencias a Génesis 2:7",
        "source for the main claim",
        "muéstrame la fuente principal",
        "¿en qué obras aparece?",
        "¿qué se dice sobre la tristeza?",
        "qué significa hitbodedut",
        "where is prayer mentioned",
        "tish beav",
        "orach jaim uno",
        "consulta breve",
        "investigar alegría",
        "דם ודיבור",
        "מה הקשר בין דם לדיבור",
        "texto ambiguo para investigar",
    ],
)
async def test_interpretation_batch_never_returns_retrieval_artifacts(question: str) -> None:
    _, response = await interpret_only(
        QaRequest(question=question, phase="interpret", ai={"enabled": False})
    )
    assert response["original_query"] == question
    assert response["actions"] == ["analyze", "modify"]
    assert response["display_interpretation"].startswith(("Interpreté que desea", "Interpreté que busca"))
    assert response["execution"]["retrieval_executed"] is False
    assert "hits" not in response
    assert "claims" not in response
    assert "primary_evidence_ids" not in response


@pytest.mark.asyncio
async def test_colloquial_relational_interpretation_is_structured_without_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("retrieval must remain deferred")

    monkeypatch.setattr(qa, "_fetch", forbidden)
    monkeypatch.setattr(qa, "_phrase_fetch", forbidden)
    _, response = await interpret_only(QaRequest(
        question="azamra la relaciones que tiene",
        phase="interpret",
        ai={"enabled": False},
    ))

    understanding = response["query_understanding"]
    assert response["status"] == "awaiting_confirmation"
    assert response["display_interpretation"] == (
        "Interpreté que desea saber con qué conceptos aparece relacionado «Azamra»."
    )
    assert response["actions"] == ["analyze", "modify"]
    assert understanding["intent"] == "discover_relations"
    assert understanding["operation"] == "find_related_concepts"
    assert understanding["instruction_span"] == "la relaciones que tiene"
    assert understanding["subject"] == {
        "raw": "azamra",
        "canonical": "Azamra",
        "normalized": "azamra",
            "subject_type": "named_topic",
    }
    assert understanding["typo_resolution"] == {
        "applied": True,
        "original_fragment": "la relaciones",
        "interpreted_as": "las relaciones",
        "reason": "article_number_agreement",
        "confidence": "high",
    }
    assert response["execution"]["retrieval_executed"] is False
    assert not {"hits", "claims", "evidence_matrix"} & response.keys()


def test_http_interpret_analyze_is_idempotent_and_server_authoritative() -> None:
    INTERPRETATION_STORE.clear()
    user_id = "8f060f49-6238-45c1-a958-e63ffdef9c15"

    @asynccontextmanager
    async def fake_transaction(_pool):
        yield AsyncMock()

    async def fake_interpret(data: QaRequest):
        prepared = _prepared(data.question)
        return prepared, {
            "phase": "interpretation",
            "status": "awaiting_confirmation",
            "original_query": data.question,
            "display_interpretation": display_interpretation(data, prepared),
            "query_understanding": {
                "intent": prepared.structured.intent,
                "operation": "find_named_topic",
                "subject": {"raw": data.question, "canonical": "Tishá BeAv", "subject_type": "named_topic"},
            },
            "actions": ["analyze", "modify"],
            "warnings": [],
            "execution": {"retrieval_executed": False},
        }

    result = {
        "status": "ok",
        "answer_text": "resultado",
        "answer_markdown": "resultado",
        "summary": "resultado",
        "conversation": {"conversation_id": "conversation-1", "turn_id": None},
        "works_consulted": [],
        "hits": [],
        "claims": [],
        "primary_evidence_ids": [],
        "evidence_counts": {"primary": 0, "contextual": 0, "additional_literal": 0},
        "evidence_matrix": [],
        "cross_corpus_matrix": [],
        "warnings": [],
        "not_found": [],
        "execution": {},
    }

    with (
        patch(
            "modules.library.routes.get_current_user_payload",
            new=AsyncMock(return_value={"sub": user_id, "role": "admin"}),
        ),
        patch("modules.library.routes.interpret_only", new=AsyncMock(side_effect=fake_interpret)),
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch("modules.library.routes.transaction", new=fake_transaction),
        patch(
            "modules.library.routes.run_simple_rag",
            new=AsyncMock(return_value=result),
        ) as run,
        patch(
            "modules.library.routes.run_investigative_qa_v1",
            new=AsyncMock(),
        ) as advanced,
        TestClient(Litestar(route_handlers=[investigative_qa_v1])) as client,
    ):
        interpreted = client.post(
            "/library/investigative-qa/v1",
            headers={"Authorization": "Bearer test"},
            json={
                "phase": "interpret",
                "question": "tisha beav",
                "conversation": {"conversation_id": "conversation-1"},
            },
        )
        assert interpreted.status_code == 200
        body = interpreted.json()
        assert body["actions"] == ["analyze", "modify"]
        assert "hits" not in body

        payload = {
            "phase": "analyze",
            "question": "payload manipulado",
            "interpretation_id": body["interpretation_id"],
            "conversation": {"conversation_id": "conversation-1"},
            "idempotency_key": "stable-analysis-key",
        }
        first = client.post(
            "/library/investigative-qa/v1",
            headers={"Authorization": "Bearer test"},
            json=payload,
        )
        second = client.post(
            "/library/investigative-qa/v1",
            headers={"Authorization": "Bearer test"},
            json=payload,
        )

    assert first.status_code == second.status_code == 200
    assert run.await_count == 1
    assert run.await_args.args[1].question == "tisha beav"
    advanced.assert_not_awaited()
    assert first.json() == second.json()


def test_interpretation_id_cannot_cross_users() -> None:
    INTERPRETATION_STORE.clear()
    payload = {"sub": "user-one", "role": "admin"}

    with (
        patch(
            "modules.library.routes.get_current_user_payload",
            new=AsyncMock(side_effect=lambda _request: payload.copy()),
        ),
        patch(
            "modules.library.routes.interpret_only",
            new=AsyncMock(
                return_value=(
                    _prepared("tisha beav"),
                    {
                        "display_interpretation": "Interpreté que desea investigar referencias sobre Tishá BeAv.",
                        "query_understanding": {},
                        "actions": ["analyze", "modify"],
                        "warnings": [],
                        "execution": {"retrieval_executed": False},
                        "phase": "interpretation",
                        "status": "awaiting_confirmation",
                        "original_query": "tisha beav",
                    },
                )
            ),
        ),
        TestClient(Litestar(route_handlers=[investigative_qa_v1])) as client,
    ):
        response = client.post(
            "/library/investigative-qa/v1",
            headers={"Authorization": "Bearer test"},
            json={"phase": "interpret", "question": "tisha beav"},
        )
        payload["sub"] = "user-two"
        denied = client.post(
            "/library/investigative-qa/v1",
            headers={"Authorization": "Bearer test"},
            json={
                "phase": "analyze",
                "question": "tisha beav",
                "interpretation_id": response.json()["interpretation_id"],
            },
        )

    assert denied.status_code == 409


@pytest.mark.asyncio
async def test_modified_interpretation_supersedes_old_without_retrieval() -> None:
    store = InterpretationStore()
    old = await store.create(
        user_id="user",
        conversation_id="conversation",
        original_query="Tisha B'Av",
        structured=_prepared("Tisha B'Av").structured.model_dump(),
        named_topic=None,
        interpretation_warnings=[],
        display_interpretation="old",
        query_understanding={},
    )
    await store.supersede(
        old.interpretation_id,
        user_id="user",
        conversation_id="conversation",
    )
    with pytest.raises(InterpretationStateError, match="interpretation_superseded"):
        await store.begin_analysis(
            old.interpretation_id,
            user_id="user",
            conversation_id="conversation",
        )


@pytest.mark.asyncio
async def test_expired_and_conversation_mismatched_interpretations_are_rejected() -> None:
    store = InterpretationStore(ttl_seconds=0)
    expired = await store.create(
        user_id="user",
        conversation_id="conversation",
        original_query="tisha beav",
        structured=_prepared("tisha beav").structured.model_dump(),
        named_topic=None,
        interpretation_warnings=[],
        display_interpretation="expired",
        query_understanding={},
    )
    with pytest.raises(InterpretationStateError, match="interpretation_expired"):
        await store.begin_analysis(
            expired.interpretation_id,
            user_id="user",
            conversation_id="conversation",
        )

    active_store = InterpretationStore()
    active = await active_store.create(
        user_id="user",
        conversation_id="conversation",
        original_query="tisha beav",
        structured=_prepared("tisha beav").structured.model_dump(),
        named_topic=None,
        interpretation_warnings=[],
        display_interpretation="active",
        query_understanding={},
    )
    with pytest.raises(InterpretationStateError, match="conversation_mismatch"):
        await active_store.begin_analysis(
            active.interpretation_id,
            user_id="user",
            conversation_id="other-conversation",
        )
