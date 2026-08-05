from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from modules.library.content_manager_schemas import IngestionStage
from modules.library.content_manager_worker import PipelineResult
from modules.library.page_first_pipeline import (
    ConcretePageFirstPipeline, ExtractedDocument, PersistedChunk, PersistedDocument,
    PersistedEmbedding, ReconciliationResult, analyze_page, reconcile_resource_sets,
)
from tests.test_content_manager_orchestration import make_job


def test_page_analysis_preserves_unicode_ligatures_hebrew_and_niqqud() -> None:
    text = "# TÍTULO\n\nreﬁ namiento\n\nטֶקְסְט עִבְרִי\n\n35 Nota breve\nSalmos 16:1"
    page = analyze_page(1, text)
    assert page.original_markdown == text
    assert "refi namiento" in page.search_text_normalized
    assert "טֶקְסְט" in page.original_markdown
    assert page.headings == ("TÍTULO",)
    assert page.footnote_numbers == (35,)
    assert page.printed_references == ("Salmos 16:1",)


def test_empty_physical_page_is_preserved_without_false_signals() -> None:
    page = analyze_page(3, "  \n")
    assert page.is_empty
    assert page.headings == page.footnote_numbers == page.printed_references == ()


@pytest.mark.parametrize("requested,expected", [("es", "es"), ("he", "he"), ("auto", "he")])
def test_language_contract(requested: str, expected: str) -> None:
    assert analyze_page(1, "טֶקְסְט עִבְרִי", requested).language == expected


class FakeGateway:
    def __init__(self, *, consistent=True):
        self.job = make_job(); self.calls=[]; self.consistent=consistent
        self.document_id=uuid4(); self.manifest_id=uuid4(); self.run_id=uuid4(); self.text_id=uuid4()
        self.chunk=PersistedChunk(uuid4(), "vec-1", 1, 0, "contenido", "abc", "es")
        self.embedding=PersistedEmbedding(uuid4(), self.chunk, (0.0, 1.0))

    async def load_request(self, job):
        from modules.library.page_first_pipeline import PageFirstIngestionRequest
        self.calls.append("load")
        return PageFirstIngestionRequest(job.upload_id,job.job_id,job.attempt_number,Path("fixture.pdf"),
            "a"*64,job.title,job.language,None,job.ingestion_profile,job.pipeline_version,
            job.embedding_model,job.collection_code,job.tenant,uuid4())
    async def persist_document_and_pages(self, request, extracted):
        self.calls.append("pages")
        return PersistedDocument(self.document_id,self.text_id,self.run_id,self.manifest_id,(uuid4(),uuid4()))
    async def persist_chunks(self,*args): self.calls.append("chunks"); return (self.chunk,)
    async def embed(self,texts,model): self.calls.append("embed"); return ((0.0,1.0),)
    async def persist_embeddings(self,*args): self.calls.append("embeddings"); return (self.embedding,)
    async def index_vectors(self,*args): self.calls.append("vectors"); return ("vec-1",)
    async def reconcile(self,request,persisted):
        self.calls.append("reconcile")
        return ReconciliationResult(request.job_id,request.attempt_number,persisted.document_id,1,1,1,
                                    1 if self.consistent else 0,
                                    () if self.consistent else ("vec-1",))
    async def finalize(self,*args): self.calls.append("finalize")


def fake_extractor(path, language):
    pages=(analyze_page(1,"# TÍTULO\n\ncontenido"), analyze_page(2,""))
    return ExtractedDocument(pages,"## Page 1\ncontenido\n\n## Page 2","hash","es",("fixture_warning",))


@pytest.mark.asyncio
async def test_pipeline_executes_real_stage_contract_and_incremental_manifest_order() -> None:
    gateway=FakeGateway(); stages=[]
    async def advance(stage,reason,progress): stages.append(stage)
    async def heartbeat(): pass
    result=await ConcretePageFirstPipeline(gateway,extractor=fake_extractor).run(
        gateway.job,advance=advance,heartbeat=heartbeat)
    assert stages == [IngestionStage.EXTRACTING,IngestionStage.NORMALIZING,
        IngestionStage.PERSISTING_PAGES,IngestionStage.BUILDING_CHUNKS,
        IngestionStage.EMBEDDING,IngestionStage.INDEXING,IngestionStage.VALIDATING_RESULT]
    assert gateway.calls == ["load","pages","chunks","embed","embeddings","vectors","reconcile","finalize"]
    assert result.document_id == gateway.document_id
    assert result.page_count == 2 and result.empty_page_count == 1
    assert set(result.warnings) == {"fixture_warning","empty_pages_preserved"}


@pytest.mark.asyncio
async def test_pipeline_reconciliation_failure_never_finalizes() -> None:
    gateway=FakeGateway(consistent=False)
    async def advance(*args): pass
    async def heartbeat(): pass
    with pytest.raises(RuntimeError,match="reconciliation"):
        await ConcretePageFirstPipeline(gateway,extractor=fake_extractor).run(
            gateway.job,advance=advance,heartbeat=heartbeat)
    assert "finalize" not in gateway.calls


def _row(pk,job,attempt,document):
    return {"pk":pk,"job_id":str(job),"attempt_number":attempt,"document_id":str(document)}


def test_reconciliation_consistent() -> None:
    job,doc=uuid4(),uuid4()
    result=reconcile_resource_sets(job_id=job,attempt_number=1,document_id=doc,
        chunk_ids=("c1",),embedding_chunk_ids=("c1",),expected_vector_ids=("v1",),
        found_vectors=(_row("v1",job,1,doc),))
    assert result.consistent


@pytest.mark.parametrize("found,missing,orphan,duplicate", [
    ((),("v1",),(),()),
    (("v1","v2"),(),("v2",),()),
    (("v1","v1"),(),(),("v1",)),
])
def test_reconciliation_detects_vector_set_failures(found,missing,orphan,duplicate) -> None:
    job,doc=uuid4(),uuid4(); rows=tuple(_row(v,job,1,doc) for v in found)
    result=reconcile_resource_sets(job_id=job,attempt_number=1,document_id=doc,
        chunk_ids=("c1",),embedding_chunk_ids=("c1",),expected_vector_ids=("v1",),found_vectors=rows)
    assert result.missing_vectors == missing
    assert result.orphan_vectors == orphan
    assert result.duplicate_vectors == duplicate
    assert not result.consistent


def test_reconciliation_rejects_attempt_document_and_embedding_scope_mismatch() -> None:
    job,doc=uuid4(),uuid4()
    result=reconcile_resource_sets(job_id=job,attempt_number=2,document_id=doc,
        chunk_ids=("c1",),embedding_chunk_ids=("other",),expected_vector_ids=("v1",),
        found_vectors=(_row("v1",uuid4(),1,uuid4()),))
    assert "embedding_chunk_set" in result.metadata_mismatches
    assert "v1" in result.metadata_mismatches
    assert not result.consistent
