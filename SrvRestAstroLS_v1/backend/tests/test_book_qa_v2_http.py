"""HTTP tests for POST /library/book-qa endpoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from modules.library.book_qa_schemas import BookQAResponse
from modules.library.routes import book_qa

RUN_ID = "492acd8d-06bd-42ac-a511-f3ec52f97bb3"


def _mock_response(answer_type: str = "no_evidence") -> BookQAResponse:
    return BookQAResponse(
        question="test",
        run_id=RUN_ID,
        answer_type=answer_type,
    )


@asynccontextmanager
async def fake_transaction(_pool):
    yield AsyncMock()


@pytest.mark.parametrize("question,expected_type", [
    ("¿Dónde aparece la alegría?", "concept_lookup"),
    ("¿Dónde habla de hitbodedut?", "concept_lookup"),
    ("¿Qué relación hay entre sangre y habla?", "relation_lookup"),
    ("¿Cómo se relacionan alegría y plegaria?", "relation_lookup"),
])
def test_book_qa_classification(question: str, expected_type: str) -> None:
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch(
            "modules.library.routes.get_current_user_payload",
            new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"}),
        ),
        patch("modules.library.routes.transaction", new=fake_transaction),
            patch("modules.library.routes.run_book_qa", new=AsyncMock(return_value=_mock_response(expected_type))),
        TestClient(Litestar(route_handlers=[book_qa])) as client,
    ):
        response = client.post(
            "/library/book-qa",
            headers={"Authorization": "Bearer test-token"},
            json={
                "question": question,
                "run_id": RUN_ID,
                "top_k": 5,
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer_type"] == expected_type, f"{question}: expected {expected_type}, got {body['answer_type']}"


def test_book_qa_requires_auth() -> None:
    with TestClient(Litestar(route_handlers=[book_qa])) as client:
        response = client.post(
            "/library/book-qa",
            json={"question": "test", "run_id": RUN_ID},
        )
    assert response.status_code == 401
