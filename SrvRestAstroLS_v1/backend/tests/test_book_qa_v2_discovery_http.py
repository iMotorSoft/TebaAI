"""HTTP tests for Book QA V2 discovery endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from modules.library.book_qa_schemas import BookQAResponse
from modules.library.routes import book_qa, book_qa_runs, book_qa_runs_latest

RUN_ID = "492acd8d-06bd-42ac-a511-f3ec52f97bb3"


def _mock_response() -> BookQAResponse:
    return BookQAResponse(question="test", run_id=RUN_ID)


@asynccontextmanager
async def fake_transaction(_pool):
    yield AsyncMock()


AUTH_HEADERS = {"Authorization": "Bearer test-token"}


# ── Discovery runs ─────────────────────────────────────────────────────────


def test_runs_requires_auth() -> None:
    with TestClient(Litestar(route_handlers=[book_qa_runs])) as client:
        r = client.get("/library/book-qa/runs")
    assert r.status_code == 401


def test_runs_with_auth() -> None:
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch("modules.library.routes.get_current_user_payload",
              new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"})),
        patch("modules.library.routes.transaction", new=fake_transaction),
        patch("modules.library.routes.list_book_qa_runs", new=AsyncMock(return_value=[])),
        TestClient(Litestar(route_handlers=[book_qa_runs])) as client,
    ):
        r = client.get("/library/book-qa/runs", headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "runs" in body
    assert "count" in body


# ── Discovery latest ───────────────────────────────────────────────────────


def test_latest_requires_auth() -> None:
    with TestClient(Litestar(route_handlers=[book_qa_runs_latest])) as client:
        r = client.get("/library/book-qa/runs/latest")
    assert r.status_code == 401


def test_latest_with_auth() -> None:
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch("modules.library.routes.get_current_user_payload",
              new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"})),
        patch("modules.library.routes.transaction", new=fake_transaction),
        patch("modules.library.routes.get_latest_book_qa_run", new=AsyncMock(return_value=None)),
        TestClient(Litestar(route_handlers=[book_qa_runs_latest])) as client,
    ):
        r = client.get("/library/book-qa/runs/latest", headers=AUTH_HEADERS, params={"scope_code": "breslov_test"})
    assert r.status_code == 200
    body = r.json()
    assert "run" in body
    assert "warnings" in body


# ── POST hardening ─────────────────────────────────────────────────────────


def test_post_missing_run_id_and_document_id() -> None:
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch("modules.library.routes.get_current_user_payload",
              new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"})),
        patch("modules.library.routes.transaction", new=fake_transaction),
        TestClient(Litestar(route_handlers=[book_qa])) as client,
    ):
        r = client.post("/library/book-qa", headers=AUTH_HEADERS, json={
            "question": "test", "top_k": 5,
        })
    assert r.status_code == 200
    body = r.json()
    assert "missing_run_id_or_document_id" in body.get("warnings", [])


def test_post_allow_milvus_warns() -> None:
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch("modules.library.routes.get_current_user_payload",
              new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"})),
        patch("modules.library.routes.transaction", new=fake_transaction),
            patch("modules.library.routes.run_book_qa",
                  new=AsyncMock(return_value=BookQAResponse(
                      question="test", run_id=RUN_ID,
                      warnings=["milvus_disabled_in_sql_only_endpoint"],
                  ))),
            TestClient(Litestar(route_handlers=[book_qa])) as client,
        ):
            r = client.post("/library/book-qa", headers=AUTH_HEADERS, json={
                "question": "test", "run_id": RUN_ID, "options": {"allow_milvus": True},
            })
    assert r.status_code == 200
    body = r.json()
    assert "milvus_disabled_in_sql_only_endpoint" in body.get("warnings", [])


def test_post_allow_ai_warns() -> None:
    with (
        patch("modules.library.routes.get_pg_pool", new=AsyncMock(return_value=object())),
        patch("modules.library.routes.get_current_user_payload",
              new=AsyncMock(return_value={"sub": str(uuid4()), "role": "editor"})),
        patch("modules.library.routes.transaction", new=fake_transaction),
            patch("modules.library.routes.run_book_qa",
                  new=AsyncMock(return_value=BookQAResponse(
                      question="test", run_id=RUN_ID,
                      warnings=["ai_synthesis_disabled_in_sql_only_endpoint"],
                  ))),
            TestClient(Litestar(route_handlers=[book_qa])) as client,
        ):
            r = client.post("/library/book-qa", headers=AUTH_HEADERS, json={
                "question": "test", "run_id": RUN_ID, "options": {"allow_ai_synthesis": True},
            })
    assert r.status_code == 200
    body = r.json()
    assert "ai_synthesis_disabled_in_sql_only_endpoint" in body.get("warnings", [])
