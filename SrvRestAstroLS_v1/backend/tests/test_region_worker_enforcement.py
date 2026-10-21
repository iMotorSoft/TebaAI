"""Worker publication enforcement; these fixtures declare, not certify, quality."""
from dataclasses import replace
import json
from uuid import uuid4

import pytest

from modules.library.page_first_pipeline import (
    ConcretePageFirstPipeline, document_from_certificates,
)
from modules.library.page_first_gateway import build_region_chunks, publication_metadata, validate_publication
from modules.library.durable_source import preserve_source, file_sha256, source_reference
from tests.test_page_first_pipeline import FakeGateway
from tests.test_region_publication import GOOD_A, GOOD_B, BAD, SOURCE, certified_fixture


CASES = [
    ((GOOD_A,), ("ACCEPTED",), "FULL", 1),
    ((BAD,), ("UNRESOLVED",), "UNUSABLE", 0),
    ((GOOD_A, BAD, GOOD_B), ("ACCEPTED", "PLATFORM_EXTRACTION_ERROR", "ACCEPTED"), "PARTIAL", 2),
    ((BAD, GOOD_A, BAD), ("SOURCE_PDF_ERROR", "ACCEPTED", "UNRESOLVED"), "PARTIAL", 1),
    ((BAD, BAD), ("UNRESOLVED", "PLATFORM_EXTRACTION_ERROR"), "UNUSABLE", 0),
]


@pytest.mark.parametrize("texts,statuses,state,count", CASES)
@pytest.mark.asyncio
async def test_actual_pipeline_chunk_builder_embeds_only_accepted_regions(texts, statuses, state, count):
    extracted = document_from_certificates((certified_fixture(texts, statuses),))
    assert BAD not in extracted.content_markdown
    assert extracted.pages[0].publication.status.value == state

    class Gateway(FakeGateway):
        async def load_request(self, job):
            return replace(await super().load_request(job), source_sha256=SOURCE)

        async def persist_document_and_pages(self, request, document):
            validate_publication(request, document)
            self.persisted = await super().persist_document_and_pages(request, document)
            metadata = publication_metadata(document.pages[0], self.document_id)
            assert metadata['partial_source'] == (state == 'PARTIAL')
            assert BAD not in json.dumps(metadata)
            return self.persisted

        async def persist_chunks(self, request, persisted, document):
            self.chunks = tuple(build_region_chunks(request, persisted, document))
            return self.chunks

        async def embed(self, texts, model):
            self.calls.append('embed')
            assert len(texts) == count
            assert all(BAD not in t for t in texts)
            assert all(not (GOOD_A in t and GOOD_B in t) for t in texts)
            return tuple((0.0, 1.0) for _ in texts)

        async def persist_embeddings(self, request, persisted, chunks, vectors):
            from modules.library.page_first_pipeline import PersistedEmbedding
            return tuple(PersistedEmbedding(uuid4(), c, v) for c, v in zip(chunks, vectors, strict=True))

        async def index_vectors(self, request, persisted, embeddings):
            assert len(embeddings) == count
            return tuple(e.chunk.chunk_uid for e in embeddings)

        async def reconcile(self, request, persisted):
            from modules.library.page_first_pipeline import ReconciliationResult
            return ReconciliationResult(request.job_id, request.attempt_number, self.document_id,
                                        count, count, count, count)

    gateway = Gateway()
    async def noop(*args): pass
    result = await ConcretePageFirstPipeline(gateway, extractor=lambda *args: extracted).run(
        gateway.job, advance=noop, heartbeat=noop)
    assert len(result.chunk_ids) == len(result.embedding_ids) == len(result.vector_ids) == count
    assert ('embed' in gateway.calls) == bool(count)
    assert 'finalize' in gateway.calls


@pytest.mark.asyncio
async def test_publication_exception_fails_before_any_persistence(monkeypatch):
    import modules.library.page_first_pipeline as module
    def fail(*args, **kwargs): raise RuntimeError('unexpected publication failure')
    monkeypatch.setattr(module, 'publish_certified_page', fail)
    gateway = FakeGateway()
    def extractor(*args):
        return document_from_certificates((certified_fixture((GOOD_A,), ('ACCEPTED',)),))
    async def noop(*args): pass
    with pytest.raises(RuntimeError, match='unexpected publication failure'):
        await ConcretePageFirstPipeline(gateway, extractor=extractor).run(
            gateway.job, advance=noop, heartbeat=noop)
    assert gateway.calls == ['load']


def test_gateway_rejects_tampered_canonical_and_source():
    from types import SimpleNamespace
    extracted = document_from_certificates((certified_fixture((GOOD_A, BAD), ('ACCEPTED','UNRESOLVED')),))
    request = SimpleNamespace(source_sha256=SOURCE)
    validate_publication(request, extracted)
    with pytest.raises(ValueError):
        validate_publication(SimpleNamespace(source_sha256='b'*64), extracted)
    with pytest.raises(ValueError):
        validate_publication(request, replace(extracted, content_markdown=BAD))
    with pytest.raises(ValueError):
        validate_publication(request, replace(extracted, pages=(replace(extracted.pages[0], publication=None),)))


def test_region_chunk_ids_and_quarantine_metadata_are_deterministic():
    from types import SimpleNamespace
    extracted = document_from_certificates((certified_fixture((GOOD_A, BAD, GOOD_B), ('ACCEPTED','UNRESOLVED','ACCEPTED')),))
    request = SimpleNamespace(pipeline_version='region-worker-test-v1')
    persisted = SimpleNamespace(document_id=uuid4())
    first = build_region_chunks(request, persisted, extracted)
    second = build_region_chunks(request, persisted, extracted)
    assert first == second
    assert len({c.chunk_id for c in first}) == 2
    assert {c.region_id for c in first} == {'region-0','region-2'}
    assert publication_metadata(extracted.pages[0], persisted.document_id) == publication_metadata(extracted.pages[0], persisted.document_id)


def test_durable_source_survives_upload_cleanup_and_is_hash_checked(tmp_path, monkeypatch):
    import modules.library.durable_source as module
    monkeypatch.setattr(module, 'CONTENT_MANAGER_STORAGE_DIR', str(tmp_path / 'existing-storage'))
    original = tmp_path / 'upload.pdf'
    original.write_bytes(b'%PDF-1.4 original visual source')
    sha = file_sha256(original)
    document_id = uuid4()
    target = preserve_source(original, document_id, sha)
    original.unlink()
    assert target.is_file() and file_sha256(target) == sha
    assert preserve_source(original, document_id, sha) == target
    assert source_reference(document_id, 55).endswith('/source#page=55')
    with pytest.raises(ValueError): preserve_source(original, document_id, 'a'*64)
    module.remove_source(document_id)
    assert not target.exists()


def test_default_worker_never_uses_legacy_page_extractor():
    from modules.library.page_first_pipeline import extract_pdf_region_published
    assert ConcretePageFirstPipeline(FakeGateway()).extractor is extract_pdf_region_published


@pytest.mark.asyncio
async def test_actual_worker_marks_publication_failure_explicitly_and_never_falls_back(monkeypatch):
    import modules.library.page_first_pipeline as module
    from modules.library.content_manager_worker import ContentManagerWorker
    from modules.library.content_manager_schemas import IngestionStage
    from tests.test_content_manager_orchestration import FakeStore
    def fail(*args, **kwargs): raise RuntimeError('injected publication error')
    monkeypatch.setattr(module, 'publish_certified_page', fail)
    gateway = FakeGateway()
    store = FakeStore([gateway.job])
    def extractor(*args):
        return document_from_certificates((certified_fixture((GOOD_A,), ('ACCEPTED',)),))
    worker = ContentManagerWorker(worker_id='region-test', store=store,
        pipeline=ConcretePageFirstPipeline(gateway, extractor=extractor))
    assert await worker.run_once()
    assert gateway.calls == ['load']
    assert store.failures == [(IngestionStage.EXTRACTING, 'pipeline_stage_failed')]
    assert store.transitions[-1][1] == IngestionStage.FAILED
    assert store.results == []


def test_failed_source_copy_keeps_upload(tmp_path, monkeypatch):
    import modules.library.durable_source as module
    monkeypatch.setattr(module, 'CONTENT_MANAGER_STORAGE_DIR', str(tmp_path / 'storage'))
    original = tmp_path / 'upload.pdf'; original.write_bytes(b'%PDF source')
    document_id = uuid4()
    with pytest.raises(ValueError): preserve_source(original, document_id, 'a'*64)
    assert original.is_file()
    assert not module.source_path(document_id).exists()
