"""Separate declared worker contracts from frozen full-pipeline outcomes.

No real certifier or external store is invoked by this module. The actual worker,
pipeline, publication policy, validation and region chunk builder run unchanged.
Only upstream certificates and I/O adapters are controlled.
"""
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

import pytest

from modules.library.content_manager_worker import ContentManagerWorker
from modules.library.page_first_gateway import build_region_chunks, validate_publication
from modules.library.page_first_pipeline import (
    ConcretePageFirstPipeline, PersistedEmbedding, ReconciliationResult,
    document_from_certificates,
)
from tests.region_fixture_contract import (
    certifier_recall_miss, partial_page_searchable, worker_metrics,
)
from tests.test_content_manager_orchestration import FakeStore
from tests.test_page_first_pipeline import FakeGateway
from tests.test_region_publication import certified_fixture

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / 'data/reports/breslov/region-quarantine-fixture-applicability-v1'
PREVIOUS = ROOT / 'data/reports/breslov/region-quarantine-worker-e2e-v1'


@pytest.mark.parametrize('case', json.loads((REPORT / 'worker-only-fixtures.json').read_text()))
@pytest.mark.asyncio
async def test_worker_obeys_declared_boundary(case):
    texts = tuple(r['text'] for r in case['regions'])
    qualities = tuple(r['quality'] for r in case['regions'])
    certified = certified_fixture(texts, qualities)
    certified = replace(certified, certificates=tuple(
        replace(c, provenance_status=r['provenance'])
        for c, r in zip(certified.certificates, case['regions'], strict=True)))
    boundary = {c.region_id: (c.quality_status, c.provenance_status)
                for c in certified.certificates}
    expected = {r['id'] for r in case['regions'] if r['publish']}
    observed = {}

    class Gateway(FakeGateway):
        async def persist_document_and_pages(self, request, document):
            validate_publication(request, document)
            observed['canonical'] = {rid for p in document.pages
                                     for rid, text in p.publication.evidence_units if text.strip()}
            for region in case['regions']:
                assert (region['text'] in document.content_markdown) == region['publish']
            self.document = document
            return await super().persist_document_and_pages(request, document)

        async def persist_chunks(self, request, persisted, document):
            self.chunks = tuple(build_region_chunks(request, persisted, document))
            observed['chunks'] = {c.region_id for c in self.chunks}
            return self.chunks

        async def embed(self, texts, model):
            assert texts == tuple(c.content for c in self.chunks)
            observed['embedding_inputs'] = {c.region_id for c in self.chunks}
            return tuple((0.0, 1.0) for _ in texts)

        async def persist_embeddings(self, request, persisted, chunks, vectors):
            embeddings = tuple(PersistedEmbedding(uuid4(), c, v)
                               for c, v in zip(chunks, vectors, strict=True))
            observed['embeddings'] = {e.chunk.region_id for e in embeddings}
            return embeddings

        async def index_vectors(self, request, persisted, embeddings):
            observed['vectors'] = {e.chunk.region_id for e in embeddings}
            return tuple(e.chunk.chunk_uid for e in embeddings)

        async def reconcile(self, request, persisted):
            count = len(self.chunks)
            return ReconciliationResult(request.job_id, request.attempt_number,
                                        persisted.document_id, count, count, count, count)

    gateway = Gateway()
    store = FakeStore([gateway.job])
    pipeline = ConcretePageFirstPipeline(gateway, extractor=lambda *args:
                                         document_from_certificates((certified,)))
    worker = ContentManagerWorker(worker_id='fixture-applicability', store=store, pipeline=pipeline)
    assert await worker.run_once()
    assert not store.failures
    assert len(store.results) == 1
    observed.setdefault('embedding_inputs', set())  # zero-chunk branch does not call embed
    assert all(ids == expected for ids in observed.values())
    visual = {r['region_id'] for r in gateway.document.pages[0].publication.metadata()['regions']
              if r['visual_reference']['source_reference'] and r['visual_reference']['bbox']}
    assert worker_metrics(boundary, observed, visual) == {
        'GOOD_NEIGHBOR_LOSS': 0, 'BAD_REGION_LEAK': 0, 'SOURCE_PRESERVATION_FAIL': 0}
    assert partial_page_searchable(boundary, observed) == case['partial']


@pytest.mark.parametrize('quality,provenance,survives,visual,expected', [
    ('ACCEPTED', 'CERTIFIED', True, True, (0, 0, 0)),
    ('ACCEPTED', 'CERTIFIED', False, True, (1, 0, 0)),
    ('UNRESOLVED', 'CERTIFIED', False, True, (0, 0, 0)),
    ('UNRESOLVED', 'CERTIFIED', True, True, (0, 1, 0)),
    ('QUARANTINED', 'UNRESOLVED', False, True, (0, 0, 0)),
    ('QUARANTINED', 'UNRESOLVED', False, False, (0, 0, 1)),
    ('ACCEPTED', 'UNRESOLVED', True, True, (0, 1, 0)),
])
def test_metric_truth_table(quality, provenance, survives, visual, expected):
    result = worker_metrics({'r': (quality, provenance)},
                            {'chunks': {'r'} if survives else set()}, {'r'} if visual else set())
    assert tuple(result.values()) == expected


@pytest.mark.parametrize('stage', ['canonical', 'chunks', 'embedding_inputs', 'embeddings',
                                   'vectors', 'retrieval', 'citations'])
def test_negative_control_detects_loss_at_each_required_stage(stage):
    stages = {s: {'A', 'C'} for s in ['canonical', 'chunks', 'embedding_inputs', 'embeddings',
                                     'vectors', 'retrieval', 'citations']}
    stages[stage].remove('C')  # controlled harness mutation, not a production edit
    assert worker_metrics({'A': ('ACCEPTED', 'CERTIFIED'), 'C': ('ACCEPTED', 'CERTIFIED')},
                          stages, {'A', 'C'})['GOOD_NEIGHBOR_LOSS'] == 1


def test_negative_control_bad_publication_and_equal_count_substitution():
    boundary = {'A': ('ACCEPTED', 'CERTIFIED'), 'B': ('UNRESOLVED', 'UNRESOLVED')}
    # A lost, B incorrectly passed downstream; unchanged total must not conceal either defect.
    assert worker_metrics(boundary, {'chunks': {'B'}, 'vectors': {'B'}}, {'A', 'B'}) == {
        'GOOD_NEIGHBOR_LOSS': 1, 'BAD_REGION_LEAK': 1, 'SOURCE_PRESERVATION_FAIL': 0}


def test_frozen_synthetic_evidence_has_upstream_mismatches_not_worker_losses():
    cases = json.loads((PREVIOUS / 'controlled-test-cases.json').read_text())
    results = {r['case']: r for r in json.loads((PREVIOUS / 'worker-integration-results.json').read_text())}
    total_recall = 0
    for case in cases:
        result = results[case['case']]
        regions = [r for p in result['page_results'] for r in p['regions']]
        assert len(regions) == len(case['texts'])
        boundary = {r['region_id']: (r['quality_status'], r['provenance_status']) for r in regions}
        author_good = {r['region_id'] for r, label in zip(regions, case['expected_region_publication'], strict=True)
                       if label == 'ACCEPTED'}
        assert all(r['quality_status'] == 'UNRESOLVED' and r['publication_status'] == 'QUARANTINED'
                   for r in regions)
        assert result['published_chunks'] == result['embeddings'] == result['vectors'] == 0
        assert result['bad_retrieval_hits'] == result['bad_textual_citations'] == 0
        assert result['accepted_region_loss'] == 0
        total_recall += certifier_recall_miss(author_good, boundary)
        metrics = worker_metrics(boundary, {'chunks': set(), 'vectors': set()}, set(boundary))
        assert metrics['GOOD_NEIGHBOR_LOSS'] == metrics['BAD_REGION_LEAK'] == 0
    assert total_recall == 4


def test_frozen_real_evidence_keeps_three_accepted_regions_and_partial_pages():
    real = json.loads((PREVIOUS / 'real-source-case.json').read_text())['result']
    accepted = {r['region_id'] for p in real['page_results'] for r in p['regions']
                if (r['quality_status'], r['provenance_status']) == ('ACCEPTED', 'CERTIFIED')}
    assert len(accepted) == real['published_chunks'] == real['embeddings'] == real['vectors'] == 3
    assert {r['region_id'] for r in real['retrieval'] if r['expected'] == 'accepted hit'} == accepted
    assert {r['region_id'] for r in real['hybrid_retrieval']} == accepted
    assert {r['region_id'] for r in real['citations']} == accepted
    assert real['visual_source_available']
    assert all(real[k] == 0 for k in ['bad_chunks', 'bad_embeddings', 'bad_vectors',
                                     'bad_retrieval_hits', 'bad_textual_citations', 'accepted_region_loss'])
    for page in real['page_results']:
        boundary = {r['region_id']: (r['quality_status'], r['provenance_status']) for r in page['regions']}
        assert partial_page_searchable(boundary, {'retrieval': accepted, 'citations': accepted})
