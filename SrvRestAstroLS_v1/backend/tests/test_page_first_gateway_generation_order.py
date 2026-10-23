"""Direct, offline FK ordering contract for the production gateway."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4
import hashlib

import pytest

from modules.library import page_first_gateway as gateway


def synthetic_request(tmp_path):
    path = tmp_path / "synthetic.txt"
    path.write_text("synthetic only; no PDF extraction")
    return SimpleNamespace(
        tenant=SimpleNamespace(knowledge_scope_id=uuid4(), organization_id=uuid4(),
                               workspace_id=uuid4(), project_id=uuid4()),
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        pipeline_version="synthetic_v1", attempt_key="synthetic:1", attempt_number=1,
        job_id=uuid4(), upload_id=uuid4(), knowledge_scope_code="synthetic",
        source_path=path, title="synthetic", work_family=None, actor_user_id=uuid4(),
    )


def empty_extracted():
    # Legal empty page set exercises registration without regional/extraction changes.
    return SimpleNamespace(pages=(), language="es", content_sha256=hashlib.sha256(b"").hexdigest(),
                           content_markdown="")


@pytest.mark.asyncio
async def test_generation_requires_resolved_logical_link_and_run(monkeypatch, tmp_path):
    events = []
    logical_id = uuid4()

    class Cursor:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, sql, params=None):
            statement = " ".join(sql.split())
            if statement.startswith("INSERT INTO library_documents("):
                events.append("document")
            elif statement.startswith("SELECT id FROM library_logical_documents"):
                events.append("logical_resolved")
            elif statement.startswith("UPDATE library_documents SET logical_document_id"):
                events.append("document_logical_link")
            elif statement.startswith("INSERT INTO library_ingestion_runs_v2"):
                assert "document" in events
                events.append("run")
            elif statement.startswith("INSERT INTO library_document_generations"):
                missing = {"document", "logical_resolved", "document_logical_link", "run"} - set(events)
                assert not missing, f"generation before required parents: {sorted(missing)}; events={events}"
                assert "'BUILDING'" in sql
                events.append("generation")
            assert "INSERT INTO library_logical_document_active_generations" not in sql
            assert "SET CONSTRAINTS" not in sql

        async def fetchone(self):
            return {"id": logical_id}

    class Connection:
        def cursor(self, **kwargs):
            return Cursor()

    @asynccontextmanager
    async def tx(pool):
        yield Connection()

    monkeypatch.setattr(gateway, "transaction", tx)
    await gateway.PostgresMilvusPageFirstGateway(None).persist_document_and_pages(
        synthetic_request(tmp_path), empty_extracted())
    assert events.count("generation") == 1
    for parent in ("document", "logical_resolved", "document_logical_link", "run"):
        assert events.index(parent) < events.index("generation")
