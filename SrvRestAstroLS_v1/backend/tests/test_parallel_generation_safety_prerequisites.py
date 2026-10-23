"""Offline regressions: safety prerequisites, NOT a parallel-generation PASS.

All stores are fakes. No real PDF, C identity, model call or service connection.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.library import hybrid_search, page_first_gateway
from modules.library.content_manager_cleanup import ManifestCleanupService
from modules.library.page_first_gateway import E2EIsolationError
from globalVar import CONTENT_MANAGER_E2E_COLLECTION, CONTENT_MANAGER_E2E_SCOPE


def _active_documents(document_ids):
    """Offline stand-in for the active-generation resolution."""
    async def resolve(*args, **kwargs):
        return list(document_ids)
    return resolve


@pytest.mark.asyncio
@pytest.mark.parametrize("canonical", [None, {}, {"document_id": "different-document", "content": "OLD_ONLY_MARKER"}])
async def test_hybrid_never_emits_unauthorized_or_misattributed_vector(monkeypatch, canonical):
    async def no_fts(*args, **kwargs):
        return []

    async def hydrate(*args, **kwargs):
        return canonical

    monkeypatch.setattr(hybrid_search, "search_chunks_text", no_fts)
    monkeypatch.setattr(hybrid_search, "_enrich_chunk", hydrate)
    monkeypatch.setattr(
        hybrid_search, "resolve_active_document_ids",
        _active_documents(["active-document"]),
    )
    monkeypatch.setattr("infrastructure.milvus.client.create_connection", lambda: None)
    monkeypatch.setattr(hybrid_search, "embed_text", lambda query: [0.0])
    monkeypatch.setattr(hybrid_search, "ensure_collection", lambda *args, **kwargs: None)
    monkeypatch.setattr(hybrid_search, "search_vectors", lambda **kwargs: [{
        "chunk_id": "candidate-chunk", "document_id": "candidate-document",
        "title": "NEW_ONLY_MARKER", "content_preview": "NEW_ONLY_MARKER", "distance": 1.0,
    }])
    result = await hybrid_search.search_chunks_hybrid(object(), "synthetic_scope", "marker")
    assert result == [], "Unrehydrated/misattributed Milvus hit must fail closed"


@pytest.mark.asyncio
async def test_hybrid_uses_only_canonical_identity_and_chunk_index(monkeypatch):
    async def no_fts(*args, **kwargs):
        return []

    async def hydrate(*args, **kwargs):
        return {"document_id": "doc", "document_title": "canonical", "chunk_index": 0,
                "content": "OLD_ONLY_MARKER", "content_length": 15}

    monkeypatch.setattr(hybrid_search, "search_chunks_text", no_fts)
    monkeypatch.setattr(hybrid_search, "_enrich_chunk", hydrate)
    monkeypatch.setattr(
        hybrid_search, "resolve_active_document_ids",
        _active_documents(["active-document"]),
    )
    monkeypatch.setattr("infrastructure.milvus.client.create_connection", lambda: None)
    monkeypatch.setattr(hybrid_search, "embed_text", lambda query: [0.0])
    monkeypatch.setattr(hybrid_search, "ensure_collection", lambda *args, **kwargs: None)
    monkeypatch.setattr(hybrid_search, "search_vectors", lambda **kwargs: [{
        "chunk_id": "chunk", "document_id": "doc", "title": "not canonical",
        "chunk_index": 999, "distance": 1.0,
    }])
    result = await hybrid_search.search_chunks_hybrid(object(), "synthetic_scope", "marker")
    assert len(result) == 1
    assert result[0]["document_title"] == "canonical"
    assert result[0]["chunk_index"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["ready", "archived", None, "unrecognized"])
async def test_cleanup_rejects_protected_or_unknown_status_before_any_side_effect(status):
    calls = []

    class Service(ManifestCleanupService):
        async def _load(self, *args):
            return {"manifest_id": uuid4(), "document_id": uuid4(), "document_status": status,
                    "scope_code": CONTENT_MANAGER_E2E_SCOPE,
                    "collection_code": CONTENT_MANAGER_E2E_COLLECTION}

        async def _set_status(self, *args):
            calls.append("status_write")

    def forbidden_index(*args):
        calls.append("index_created")
        raise AssertionError("Must refuse before index construction")

    service = Service(None, index_factory=forbidden_index)
    with pytest.raises(E2EIsolationError):
        await service.cleanup(uuid4(), 1)
    assert calls == []


@pytest.mark.asyncio
async def test_gateway_identity_collision_is_rejected_before_ownership_claim(monkeypatch, tmp_path):
    statements = []

    class Cursor:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, sql, params=None):
            statements.append(sql)

        async def fetchone(self):
            # Collection exists; document INSERT collided with an existing UUID.
            return {"id": uuid4()} if len(statements) == 1 else None

    class Connection:
        def cursor(self, **kwargs):
            return Cursor()

    @asynccontextmanager
    async def fake_transaction(pool):
        yield Connection()

    monkeypatch.setattr(page_first_gateway, "transaction", fake_transaction)
    monkeypatch.setattr(page_first_gateway, "validate_publication", lambda *args: None)
    original = tmp_path / "synthetic.txt"
    original.write_text("not a PDF; no extraction occurs")
    tenant = SimpleNamespace(knowledge_scope_id=uuid4(), organization_id=uuid4(),
                             workspace_id=uuid4(), project_id=uuid4())
    request = SimpleNamespace(tenant=tenant, source_sha256="a" * 64, pipeline_version="synthetic_v1",
        attempt_key="synthetic:1", attempt_number=1, job_id=uuid4(), upload_id=uuid4(),
        knowledge_scope_code="synthetic", source_path=original, title="synthetic",
        work_family=None, actor_user_id=uuid4())
    extracted = SimpleNamespace(pages=(), language="es", content_sha256="b" * 64,
                                content_markdown="synthetic")
    with pytest.raises(E2EIsolationError, match="already exists"):
        await page_first_gateway.PostgresMilvusPageFirstGateway(None).persist_document_and_pages(request, extracted)
    assert len(statements) == 2
    assert "content_manager_manifest_resources" not in " ".join(statements)
    assert "library_ingestion_runs_v2" not in " ".join(statements)


@pytest.mark.asyncio
async def test_search_http_cannot_serialize_unrehydrated_vector(monkeypatch):
    """Real handler + hybrid orchestration; stores/auth/model are offline fakes."""
    import httpx
    from litestar import Litestar
    from modules.library import routes

    @asynccontextmanager
    async def tx(pool):
        yield object()

    async def payload(*args):
        return {"sub": str(uuid4())}

    async def pool(*args):
        return None

    async def scope(*args, **kwargs):
        return SimpleNamespace(knowledge_scope_code="synthetic_scope")

    async def no_fts(*args, **kwargs):
        return []

    async def missing_pg(*args, **kwargs):
        return {}

    monkeypatch.setattr(routes, "transaction", tx)
    monkeypatch.setattr(routes, "get_current_user_payload", payload)
    monkeypatch.setattr(routes, "get_pg_pool", pool)
    monkeypatch.setattr(routes, "get_authorized_scope_by_code", scope)
    monkeypatch.setattr(hybrid_search, "search_chunks_text", no_fts)
    monkeypatch.setattr(hybrid_search, "_enrich_chunk", missing_pg)
    monkeypatch.setattr(
        hybrid_search, "resolve_active_document_ids",
        _active_documents(["active-document"]),
    )
    monkeypatch.setattr("infrastructure.milvus.client.create_connection", lambda: None)
    monkeypatch.setattr(hybrid_search, "embed_text", lambda query: [0.0])
    monkeypatch.setattr(hybrid_search, "ensure_collection", lambda *args, **kwargs: None)
    monkeypatch.setattr(hybrid_search, "search_vectors", lambda **kwargs: [{
        "chunk_id": str(uuid4()), "document_id": str(uuid4()),
        "title": "NEW_ONLY_MARKER", "content_preview": "NEW_ONLY_MARKER", "distance": 1.0,
    }])
    app = Litestar(route_handlers=[routes.library_search])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/library/search", headers={"Authorization": "Bearer unit-test"},
                                     json={"query": "marker", "collection": "synthetic_scope", "mode": "hybrid"})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert "NEW_ONLY_MARKER" not in response.text
