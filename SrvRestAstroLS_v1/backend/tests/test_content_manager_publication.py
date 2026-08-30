from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from modules.library.content_manager import publish_document


class FakeCursor:
    rowcount = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, query, params):
        self.rowcount = 1


class FakeConnection:
    def cursor(self):
        return FakeCursor()


def candidate():
    return {
        "job_id": uuid4(),
        "document_id": uuid4(),
        "vector_ids": ["v1", "v2"],
        "chunks": 2,
        "embeddings": 2,
    }


@pytest.mark.asyncio
async def test_publication_requires_exact_document_bounded_vectors():
    item = candidate()
    with pytest.raises(ValueError, match="Milvus"):
        await publish_document(
            FakeConnection(),
            item,
            actor_user_id=str(uuid4()),
            found_vectors=[{"pk": "v1", "document_id": str(item["document_id"])}],
        )


@pytest.mark.asyncio
async def test_publication_promotes_only_after_exact_recheck():
    item = candidate()
    rows = [
        {"pk": vector_id, "document_id": str(item["document_id"])}
        for vector_id in item["vector_ids"]
    ]
    result = await publish_document(
        FakeConnection(), item, actor_user_id=str(uuid4()), found_vectors=rows,
    )
    assert result.status == "ready"
    assert result.chunks == result.embeddings == result.vectors == 2
    assert isinstance(result.published_at, datetime)
    assert result.published_at.tzinfo == timezone.utc
