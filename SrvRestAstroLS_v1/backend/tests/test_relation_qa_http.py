from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from modules.library.domain import KnowledgeScope
from modules.library.relation_qa_schemas import (
    ConceptVariants,
    EvidenceSummary,
    RelationQAAnswer,
    RelationQAConcepts,
    RelationQAMethod,
    RelationQAResponse,
)
from modules.library.routes import relation_qa


CASES = [
    ("blood_speech", "¿Dónde está la conexión entre sangre y habla?", "sangre", "habla", False),
    ("azamra", "¿Dónde aparece la enseñanza de los puntos buenos?", "puntos buenos", "poco de bien", False),
    ("jatzot", "¿Dónde aparece dividiendo la noche o la idea de jatzot?", "noche", "jatzot", True),
    ("tzafon", "¿Dónde aparece desde el norte vendrá el mal?", "tzafón", "mal", True),
    ("dibur", "¿Dónde aparece la enseñanza sobre elevar el habla o dibur?", "habla", "dibur", True),
    ("bereshit_rabah", "¿Dónde aparece Bereshit Rabah y qué función cumple?", "Bereshit Rabah", "midrash", True),
]


def _response(question: str, concept_a: str, concept_b: str) -> RelationQAResponse:
    return RelationQAResponse(
        question=question,
        language="es",
        knowledge_scope_code="breslov_primary",
        concepts=RelationQAConcepts(
            concept_a=ConceptVariants(label=concept_a, variants=[concept_a]),
            concept_b=ConceptVariants(label=concept_b, variants=[concept_b]),
        ),
        answer=RelationQAAnswer(
            short_conclusion="No hay relación literal; lectura editorial.",
            editorial_answer_markdown="Fuente [src_1].",
            literal_relation_found=False,
            ai_inference_used=True,
            editorial_certainty="low",
        ),
        evidence_summary=EvidenceSummary(ai_inference=1),
        sources=[],
        source_map=[],
        warnings=["no_literal_relation: no citar como doctrina literal"],
        method=RelationQAMethod(
            retrieval=["postgresql_fts_websearch", "milvus_dense_cosine"],
            llm_model="openai_gpt-5.4-nano",
            embedding_model="openai_text_embedding_3_small",
            used_milvus=True,
            used_ai=True,
        ),
    )


@pytest.mark.parametrize("case_id,question,concept_a,concept_b,include_test", CASES)
def test_relation_qa_http_contract(
    case_id: str,
    question: str,
    concept_a: str,
    concept_b: str,
    include_test: bool,
) -> None:
    scope = KnowledgeScope(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        knowledge_scope_code="breslov_primary",
        name="Breslov",
        status="active",
    )

    @asynccontextmanager
    async def fake_transaction(_pool):
        yield AsyncMock()

    expected = _response(question, concept_a, concept_b)
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch(
            "modules.library.routes.get_current_user_payload",
            new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"}),
        ),
        patch("modules.library.routes.transaction", new=fake_transaction),
        patch(
            "modules.library.routes.get_authorized_scope_by_code",
            new=AsyncMock(return_value=scope),
        ),
        patch(
            "modules.library.routes.run_relation_qa",
            new=AsyncMock(return_value=expected),
        ) as run,
        TestClient(Litestar(route_handlers=[relation_qa])) as client,
    ):
        response = client.post(
            "/library/relation-qa",
            headers={"Authorization": "Bearer test-token"},
            json={
                "question": question,
                "concept_a": concept_a,
                "concept_b": concept_b,
                "language": "es",
                "top_k": 20,
                "use_ai": True,
                "include_test_candidates": include_test,
            },
        )

    assert response.status_code == 200, (case_id, response.text)
    body = response.json()
    assert body["knowledge_scope_code"] == "breslov_primary"
    assert body["answer"]["literal_relation_found"] is False
    assert body["answer"]["ai_inference_used"] is True
    assert body["method"]["used_pg_as_canonical"] is True
    assert "source_map" in body
    assert run.await_count == 1


def test_relation_qa_requires_auth() -> None:
    with TestClient(Litestar(route_handlers=[relation_qa])) as client:
        response = client.post(
            "/library/relation-qa",
            json={"question": "¿Dónde está esta relación?"},
        )
    assert response.status_code == 401
