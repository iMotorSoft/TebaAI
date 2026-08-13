"""Document-centric administrative views — summary and library listing.

Tests exercise the read-model helpers without a live database. Pure helpers
(`_operational_state`, `_e2e_clause`) are tested exhaustively; the SQL
builders are tested by capturing the SQL and returning query-specific canned
result sets from a fake async connection.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from modules.library.content_manager import (
    _e2e_clause,
    _operational_state,
    get_content_summary,
    list_content_documents,
)
from modules.library.content_manager_schemas import ContentSummary


ORG = "11111111-1111-1111-1111-111111111111"
WS = "22222222-2222-2222-2222-222222222222"
PROJECT = "33333333-3333-3333-3333-333333333333"


# ── Pure helpers ──────────────────────────────────────────────────────────


def test_operational_state_mapping() -> None:
    assert _operational_state(document_status="ready", job_status=None, is_processing=False) == "idle"
    assert _operational_state(document_status="test_candidate", job_status=None, is_processing=False) == "needs_review"
    assert _operational_state(document_status=None, job_status=None, is_processing=True) == "processing"
    assert _operational_state(document_status=None, job_status="queued", is_processing=False) == "processing"
    assert _operational_state(document_status="ingestion_failed", job_status=None, is_processing=False) == "failed"
    assert _operational_state(document_status=None, job_status="failed", is_processing=False) == "failed"
    assert _operational_state(document_status="ready", job_status="completed_with_warnings", is_processing=False) == "needs_review"


def test_e2e_clause_excluded_by_default() -> None:
    assert "breslov_e2e" in _e2e_clause("ks", include_test_data=False)
    assert _e2e_clause("ks", include_test_data=True) == ""


def test_summary_shape_matches_contract() -> None:
    summary = ContentSummary(
        total_documents=0, ready=0, test_candidate=0, processing=0,
        with_warnings=0, failed=0, languages={},
    )
    assert summary.model_dump() == {
        "total_documents": 0, "ready": 0, "test_candidate": 0,
        "processing": 0, "with_warnings": 0, "failed": 0, "languages": {},
    }


# ── SQL builders with a fake connection ───────────────────────────────────


class FakeCursor:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.result_sets = result_sets
        self.last_sql = ""
        self.last_params: dict[str, Any] = {}

    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> "FakeCursor":
        self.last_sql = sql
        self.last_params = params or {}
        return self

    async def fetchall(self) -> list[dict[str, Any]]:
        return list(self.result_sets.pop(0)) if self.result_sets else []

    async def fetchone(self) -> dict[str, Any] | None:
        rows = await self.fetchall()
        return rows[0] if rows else None


class FakeConn:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.cursor = FakeCursor(result_sets)
        self.executed: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> FakeCursor:
        await self.cursor.execute(sql, params)
        self.executed.append((sql, params or {}))
        return self.cursor


def test_summary_aggregates_document_statuses() -> None:
    doc_statuses = [{
        "total_documents": 12, "ready": 8, "test_candidate": 3,
        "ingestion_failed": 1, "draft": 0,
    }]
    processing = [{"processing": 1}]
    latest = [{"with_warnings": 2, "job_failed": 0}]
    languages = [{"lang": "es", "cnt": 8}, {"lang": "he", "cnt": 4}]
    conn = FakeConn([doc_statuses, processing, latest, languages])

    result = asyncio.run(
        get_content_summary(
            conn, organization_id=ORG, workspace_id=WS, project_id=PROJECT,
        )
    )

    assert result.total_documents == 12
    assert result.ready == 8
    assert result.test_candidate == 3
    assert result.processing == 1
    assert result.with_warnings == 2
    assert result.failed == 1
    assert result.languages == {"es": 8, "he": 4}
    # Default excludes E2E in document and job queries.
    assert any("breslov_e2e" in sql for sql, _ in conn.executed)


def test_summary_include_test_data_drops_e2e_clause() -> None:
    doc_statuses = [{
        "total_documents": 15, "ready": 8, "test_candidate": 4,
        "ingestion_failed": 2, "draft": 1,
    }]
    processing = [{"processing": 2}]
    latest = [{"with_warnings": 3, "job_failed": 1}]
    languages = [{"lang": "es", "cnt": 15}]
    conn = FakeConn([doc_statuses, processing, latest, languages])

    result = asyncio.run(
        get_content_summary(
            conn, organization_id=ORG, workspace_id=WS, project_id=PROJECT,
            include_test_data=True,
        )
    )

    assert result.total_documents == 15
    assert result.failed == 3  # ingestion_failed + job_failed
    assert not any("breslov_e2e" in sql for sql, _ in conn.executed)


def test_list_documents_maps_documents_and_states() -> None:
    doc_rows = [
        {
            "document_id": uuid4(), "title": "Likutey Halajot — Interior Final",
            "language": "es", "document_status": "test_candidate",
            "source_filename": "lh.pdf", "edition": "Interior Final",
            "created_at": None, "updated_at": None,
            "work_family": "Likutey Halajot",
            "canonical_work": "Likutey Halajot",
            "page_count": 284,
            "latest_job_id": None, "latest_job_status": None,
            "latest_job_stage": None, "job_filename": None,
            "is_processing": False, "knowledge_scope_code": "breslov_primary",
        },
        {
            "document_id": uuid4(), "title": "KITZUR",
            "language": "es", "document_status": "ready",
            "source_filename": "kitzur.pdf", "edition": None,
            "created_at": None, "updated_at": None,
            "work_family": "Kitzur", "canonical_work": None,
            "page_count": 0,
            "latest_job_id": None, "latest_job_status": None,
            "latest_job_stage": None, "job_filename": None,
            "is_processing": False, "knowledge_scope_code": "breslov_primary",
        },
    ]
    # Summary: 4 queries follow the list query.
    doc_statuses = [{
        "total_documents": 2, "ready": 1, "test_candidate": 1,
        "ingestion_failed": 0, "draft": 0,
    }]
    processing = [{"processing": 0}]
    latest = [{"with_warnings": 0, "job_failed": 0}]
    languages = [{"lang": "es", "cnt": 2}]
    conn = FakeConn([doc_rows, doc_statuses, processing, latest, languages])

    result = asyncio.run(
        list_content_documents(
            conn, organization_id=ORG, workspace_id=WS, project_id=PROJECT,
        )
    )

    assert len(result.documents) == 2
    states = {doc.title: doc.operational_state for doc in result.documents}
    assert states["Likutey Halajot — Interior Final"] == "needs_review"
    assert states["KITZUR"] == "idle"
    # Document list query excludes E2E by default.
    assert "breslov_e2e" in conn.executed[0][0]


def test_list_documents_marks_e2e_when_included() -> None:
    doc_rows = [
        {
            "document_id": uuid4(), "title": "E2E fixture",
            "language": "es", "document_status": "test_candidate",
            "source_filename": "e2e.pdf", "edition": None,
            "created_at": None, "updated_at": None,
            "work_family": None, "canonical_work": None,
            "page_count": 3,
            "latest_job_id": None, "latest_job_status": "completed_with_warnings",
            "latest_job_stage": "completed_with_warnings", "job_filename": "e2e.pdf",
            "is_processing": False, "knowledge_scope_code": "breslov_e2e",
        },
    ]
    doc_statuses = [{
        "total_documents": 1, "ready": 0, "test_candidate": 1,
        "ingestion_failed": 0, "draft": 0,
    }]
    processing = [{"processing": 0}]
    latest = [{"with_warnings": 1, "job_failed": 0}]
    languages = [{"lang": "es", "cnt": 1}]
    conn = FakeConn([doc_rows, doc_statuses, processing, latest, languages])

    result = asyncio.run(
        list_content_documents(
            conn, organization_id=ORG, workspace_id=WS, project_id=PROJECT,
            include_test_data=True,
        )
    )

    assert len(result.documents) == 1
    assert result.documents[0].is_test_data is True
    assert result.documents[0].has_warnings is True
    assert "breslov_e2e" not in conn.executed[0][0]
