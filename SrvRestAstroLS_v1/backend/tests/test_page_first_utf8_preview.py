from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.library.page_first_gateway import PostgresMilvusPageFirstGateway


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [
    "a" * 1100, "á" * 1100, "יְהִי רָצוֹן " * 150,
    "Texto English: שלום, 80 = פ; " * 100, "a" * 1023 + "ש",
])
async def test_indexing_bounds_preview_in_bytes_and_keeps_canonical_content(monkeypatch, content):
    import modules.library.page_first_gateway as module

    class Cursor:
        async def execute(self, *args):
            pass

    @asynccontextmanager
    async def cursor():
        yield Cursor()

    @asynccontextmanager
    async def transaction(pool):
        yield SimpleNamespace(cursor=cursor)

    captured = []

    class Index:
        def __init__(self, name):
            pass

        def upsert(self, rows):
            captured.extend(rows)
            for row in rows:
                assert len(row["content_preview"].encode("utf-8")) <= 1024
                assert "\ufffd" not in row["content_preview"]

    monkeypatch.setattr(module, "transaction", transaction)
    monkeypatch.setattr(module, "MilvusAttemptIndex", Index)
    request = SimpleNamespace(
        collection_code="tebaai_content_manager_e2e_v1", milvus_collection_code="breslov_e2e",
        knowledge_scope_code="breslov_e2e", title="DEV", source_sha256="a" * 64,
        attempt_key="job:1", job_id=uuid4(), attempt_number=1,
    )
    chunk = SimpleNamespace(chunk_uid="vector", chunk_id=uuid4(), language="he",
                            content_sha256="b" * 64, chunk_index=0, page_number=187, content=content)
    embedding = SimpleNamespace(chunk=chunk, vector=(0.0,), embedding_id=uuid4())
    persisted = SimpleNamespace(document_id=uuid4(), manifest_id=uuid4())
    await PostgresMilvusPageFirstGateway(None).index_vectors(request, persisted, (embedding,))
    assert content.startswith(captured[0]["content_preview"])
    assert chunk.content == content
