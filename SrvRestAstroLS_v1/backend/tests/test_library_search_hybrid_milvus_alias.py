"""Tests for Milvus metadata aliases used by library hybrid search."""

from __future__ import annotations

import pytest

from modules.library import hybrid_search
from modules.library.hybrid_search import resolve_milvus_collection_code_for_scope


def test_resolve_milvus_collection_code_breslov_primary_alias() -> None:
    assert resolve_milvus_collection_code_for_scope("breslov_primary") == "breslov"


def test_resolve_milvus_collection_code_breslov_passthrough() -> None:
    assert resolve_milvus_collection_code_for_scope("breslov") == "breslov"


def test_resolve_milvus_collection_code_other_scope_passthrough() -> None:
    assert resolve_milvus_collection_code_for_scope("other_scope") == "other_scope"


def test_resolve_milvus_collection_code_none_passthrough() -> None:
    assert resolve_milvus_collection_code_for_scope(None) is None


@pytest.mark.asyncio
async def test_hybrid_search_uses_milvus_alias_for_breslov_primary(monkeypatch) -> None:
    calls: dict[str, object] = {}

    async def fake_search_chunks_text(conn, **kwargs):
        calls["fts_scope"] = kwargs["knowledge_scope_code"]
        return [
            {
                "chunk_id": "fts-chunk",
                "document_id": "doc-1",
                "document_title": "FTS doc",
                "rank": 1.0,
                "plain_excerpt": "fts",
                "highlighted_excerpt": "fts",
                "content_length": 3,
            }
        ]

    async def fake_fetch_one(conn, query, params):
        calls["enrich_scope"] = params["code"]
        return {
            "document_id": "doc-2",
            "document_title": "Vector doc",
            "author": None,
            "chunk_index": 7,
            "language": "es",
            "page_start": None,
            "page_end": None,
            "chapter": None,
            "section": None,
            "reference_label": None,
            "content": "vector content",
            "content_length": 14,
        }

    def fake_search_vectors(**kwargs):
        calls["milvus_expr"] = kwargs["expr"]
        return [
            {
                "chunk_id": "vector-chunk",
                "document_id": "doc-2",
                "title": "Vector doc",
                "chunk_index": 7,
                "distance": 0.55,
            }
        ]

    monkeypatch.setattr("infrastructure.milvus.client.create_connection", lambda: None)
    monkeypatch.setattr(hybrid_search, "search_chunks_text", fake_search_chunks_text)
    monkeypatch.setattr(hybrid_search, "embed_text", lambda query: [0.1, 0.2, 0.3])
    monkeypatch.setattr(hybrid_search, "ensure_collection", lambda *args, **kwargs: None)
    monkeypatch.setattr(hybrid_search, "search_vectors", fake_search_vectors)
    monkeypatch.setattr(hybrid_search, "fetch_one", fake_fetch_one)

    results = await hybrid_search.search_chunks_hybrid(
        object(),
        knowledge_scope_code="breslov_primary",
        query="alegría plegaria",
        top_k=10,
        language="es",
    )

    assert calls["fts_scope"] == "breslov_primary"
    assert calls["enrich_scope"] == "breslov_primary"
    assert calls["milvus_expr"] == 'collection_code == "breslov"'
    assert "breslov_primary" not in str(calls["milvus_expr"])
    assert any("vector" in row["source_signals"] for row in results)
