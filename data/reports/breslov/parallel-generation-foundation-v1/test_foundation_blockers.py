"""Reproductions of CURRENT blockers, not acceptance tests or safety PASS.

No real stores/model/PDF/worker. A green test here proves an unsafe behavior
still exists. Delete/replace these reproductions when implementing isolation.
"""
from pathlib import Path
import importlib.util

import pytest

from modules.library import hybrid_search, source_repository, text_search

HERE = Path(__file__).resolve().parent


@pytest.mark.asyncio
async def test_valid_pg_candidate_leaks_and_competes_before_top_k(monkeypatch):
    calls = []

    async def no_fts(*args, **kwargs):
        return []

    async def valid_candidate(*args, **kwargs):
        # Real hydration currently has no pointer/status predicate. This is
        # canonical PG data for NEW, not an orphan or identity mismatch.
        return {'document_id': 'new-generation', 'document_title': 'Synthetic X',
                'chunk_index': 0, 'content': 'NEW_ONLY_MARKER', 'content_length': 15}

    def vector_search(**kwargs):
        calls.append(kwargs)
        # Candidate beats OLD at top-1. Postfiltering cannot restore OLD.
        return [{'chunk_id': 'new-chunk', 'document_id': 'new-generation', 'distance': 1.0}]

    monkeypatch.setattr(hybrid_search, 'search_chunks_text', no_fts)
    monkeypatch.setattr(hybrid_search, '_enrich_chunk', valid_candidate)
    monkeypatch.setattr('infrastructure.milvus.client.create_connection', lambda: None)
    monkeypatch.setattr(hybrid_search, 'embed_text', lambda query: [0.0])
    monkeypatch.setattr(hybrid_search, 'ensure_collection', lambda *a, **k: None)
    monkeypatch.setattr(hybrid_search, 'search_vectors', vector_search)
    results = await hybrid_search.search_chunks_hybrid(
        object(), 'synthetic_scope', 'marker', top_k=1, vector_limit=1)
    assert results[0]['document_id'] == 'new-generation'
    assert results[0]['plain_excerpt'] == 'NEW_ONLY_MARKER'
    assert calls[0]['expr'] == 'collection_code == "synthetic_scope"'
    assert 'document_id' not in calls[0]['expr']


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['_search_fts', '_search_phrase', '_search_trigram'])
async def test_literal_readers_have_no_active_identity_resolution(monkeypatch, method):
    captured = []

    async def rows(conn, sql, params):
        captured.append(sql)
        return []

    monkeypatch.setattr(text_search, 'fetch_all', rows)
    await getattr(text_search, method)(object(), 'synthetic_scope', 'marker', 'marker', 1)
    assert len(captured) == 1
    assert 'active_generation' not in captured[0]
    assert 'logical_document' not in captured[0]
    assert 'd.status' not in captured[0]


@pytest.mark.asyncio
async def test_viewer_publication_still_chooses_latest_run(monkeypatch):
    captured = []

    async def row(conn, sql, params):
        captured.append(sql)
        return None

    monkeypatch.setattr(source_repository, 'fetch_one', row)
    assert await source_repository.get_page_publication(object(), 'synthetic-document', 1) is None
    assert 'ORDER BY r.finished_at DESC LIMIT 1' in captured[0]
    assert 'active_generation' not in captured[0]


def test_foundation_probe_redirects_output_without_changing_predecessor():
    spec = importlib.util.spec_from_file_location('foundation_probe_test', HERE / 'inventory_readonly.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = module.PREDECESSOR.read_bytes()
    collector = module.collector()
    assert collector.OUT == HERE
    assert collector.TARGET_C_DOCUMENT_ID == 'ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa'
    assert module.PREDECESSOR.read_bytes() == before
