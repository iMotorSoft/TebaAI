"""HTTP tests for Book QA V2 comprehension questions."""

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


def _mock_resp(answer_type: str = "comprehension_lookup", pages: list[int] | None = None) -> BookQAResponse:
    from modules.library.book_qa_schemas import BookQAEvidenceSummary, BookQAMethod, BookQASource
    pgs = pages or [13]
    return BookQAResponse(
        question="test", run_id=RUN_ID, answer_type=answer_type,
        sources=[BookQASource(page_number=p, evidence_type="comprehension_match", score=0.8, snippet="test") for p in pgs],
        evidence_summary=BookQAEvidenceSummary(pages=pgs),
    )


@asynccontextmanager
async def fake_transaction(_pool):
    yield AsyncMock()


AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("question,expected_type,expected_page", [
    ("¿Cómo se relaciona el estudio de la Torá con la anulación de la mala inclinación?", "comprehension_lookup", 13),
    ("¿Qué papel juega la caridad en relación con la pureza sexual?", "comprehension_lookup", 82),
    ("¿Qué conexión establece el texto entre el mes de Tishrei y la rectificación espiritual?", "comprehension_lookup", 117),
    ("¿Cuál es el propósito del suspiro sagrado y cómo beneficia a la persona?", "comprehension_lookup", 337),
    ("¿Cómo se relaciona la paz con el conocimiento (daat) según el texto?", "comprehension_lookup", 257),
])
def test_comprehension_route(question: str, expected_type: str, expected_page: int) -> None:
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch("modules.library.routes.get_current_user_payload",
              new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"})),
        patch("modules.library.routes.transaction", new=fake_transaction),
        patch("modules.library.routes.run_book_qa",
              new=AsyncMock(return_value=_mock_resp(expected_type, [expected_page]))),
        TestClient(Litestar(route_handlers=[book_qa])) as client,
    ):
        r = client.post("/library/book-qa", headers=AUTH_HEADERS, json={
            "question": question, "run_id": RUN_ID, "top_k": 8,
        })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer_type"] == expected_type, f"{question[:40]}: expected {expected_type}, got {body['answer_type']}"
    pages = [s["page_number"] for s in body.get("sources", [])]
    assert expected_page in pages, f"{question[:40]}: expected page {expected_page} not in {pages}"
    method = body.get("method", {})
    assert method.get("used_milvus") is False
    assert method.get("used_ai") is False


def test_comprehension_requires_auth() -> None:
    with TestClient(Litestar(route_handlers=[book_qa])) as client:
        r = client.post("/library/book-qa", json={"question": "test", "run_id": RUN_ID})
    assert r.status_code == 401
