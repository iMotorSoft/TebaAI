"""Reusable, document-agnostic page-first ingestion pipeline.

Extraction is canonical PyMuPDF4LLM page-by-page. Original Markdown is kept for
citations while a separate NFKC/ligature-normalized surface supports search.
Persistence, embeddings and vectors are adapters so unit tests never contact
external services.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import UUID

from modules.library.content_manager_repository import ClaimedJob, ContentTenantContext
from modules.library.content_manager_schemas import IngestionStage
from modules.library.content_manager_worker import Advance, Heartbeat, PageFirstPipeline, PipelineResult
from modules.library.pdf_ligature_normalization import normalize_pdf_search_text

_HEBREW_RE = re.compile(r"[\u0590-\u05ff]")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_UPPER_HEADING_RE = re.compile(r"^(?:\d+\s*[■▪•.-]?\s*)?([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s]{4,80})$", re.MULTILINE)
_FOOTNOTE_RE = re.compile(r"(?m)^\s*(\d{1,3})[.)]?\s+\S.+$")
_PRINTED_REFERENCE_RE = re.compile(
    r"(?iu)(?:[\wÁÉÍÓÚÜÑáéíóúüñ]{3,}(?:[ \t]+[\wÁÉÍÓÚÜÑáéíóúüñ]{2,}){0,2})[ \t]+\d{1,3}:\d{1,3}(?!\d)"
)


@dataclass(frozen=True)
class PageFirstIngestionRequest:
    upload_id: UUID
    job_id: UUID
    attempt_number: int
    source_path: Path
    source_sha256: str
    title: str
    language: str
    work_family: str | None
    ingestion_profile: str
    pipeline_version: str
    embedding_model: str
    collection_code: str
    tenant: ContentTenantContext
    actor_user_id: UUID

    @property
    def attempt_key(self) -> str:
        return f"{self.job_id}:{self.attempt_number}"


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    original_markdown: str
    search_text_normalized: str
    language: str
    headings: tuple[str, ...]
    footnote_numbers: tuple[int, ...]
    printed_references: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.original_markdown.strip()


@dataclass(frozen=True)
class ExtractedDocument:
    pages: tuple[ExtractedPage, ...]
    content_markdown: str
    content_sha256: str
    language: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PersistedDocument:
    document_id: UUID
    document_text_id: UUID
    ingestion_run_id: UUID
    manifest_id: UUID
    page_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class PersistedChunk:
    chunk_id: UUID
    chunk_uid: str
    page_number: int
    chunk_index: int
    content: str
    content_sha256: str
    language: str


@dataclass(frozen=True)
class PersistedEmbedding:
    embedding_id: UUID
    chunk: PersistedChunk
    vector: tuple[float, ...]


@dataclass(frozen=True)
class ReconciliationResult:
    job_id: UUID
    attempt_number: int
    document_id: UUID
    expected_chunks: int
    expected_embeddings: int
    expected_vectors: int
    found_vectors: int
    missing_vectors: tuple[str, ...] = ()
    orphan_vectors: tuple[str, ...] = ()
    duplicate_vectors: tuple[str, ...] = ()
    metadata_mismatches: tuple[str, ...] = ()

    @property
    def consistent(self) -> bool:
        return not (
            self.missing_vectors or self.orphan_vectors
            or self.duplicate_vectors or self.metadata_mismatches
        ) and self.expected_chunks == self.expected_embeddings == self.expected_vectors == self.found_vectors


class PageFirstGateway(Protocol):
    async def load_request(self, job: ClaimedJob) -> PageFirstIngestionRequest: ...
    async def persist_document_and_pages(
        self, request: PageFirstIngestionRequest, extracted: ExtractedDocument,
    ) -> PersistedDocument: ...
    async def persist_chunks(
        self, request: PageFirstIngestionRequest, persisted: PersistedDocument,
        extracted: ExtractedDocument,
    ) -> tuple[PersistedChunk, ...]: ...
    async def persist_embeddings(
        self, request: PageFirstIngestionRequest, persisted: PersistedDocument,
        chunks: tuple[PersistedChunk, ...], vectors: tuple[tuple[float, ...], ...],
    ) -> tuple[PersistedEmbedding, ...]: ...
    async def index_vectors(
        self, request: PageFirstIngestionRequest, persisted: PersistedDocument,
        embeddings: tuple[PersistedEmbedding, ...],
    ) -> tuple[str, ...]: ...
    async def reconcile(
        self, request: PageFirstIngestionRequest, persisted: PersistedDocument,
    ) -> ReconciliationResult: ...
    async def finalize(
        self, request: PageFirstIngestionRequest, persisted: PersistedDocument,
        reconciliation: ReconciliationResult, extracted: ExtractedDocument,
    ) -> None: ...
    async def embed(self, texts: tuple[str, ...], model: str) -> tuple[tuple[float, ...], ...]: ...


def reconcile_resource_sets(
    *, job_id: UUID, attempt_number: int, document_id: UUID,
    chunk_ids: tuple[str, ...], embedding_chunk_ids: tuple[str, ...],
    expected_vector_ids: tuple[str, ...], found_vectors: tuple[dict[str, object], ...],
) -> ReconciliationResult:
    """Pure attempt-bounded reconciliation used by unit and real adapters."""
    found_ids = tuple(str(row["pk"]) for row in found_vectors)
    duplicates = tuple(sorted({item for item in found_ids if found_ids.count(item) > 1}))
    missing = tuple(sorted(set(expected_vector_ids) - set(found_ids)))
    orphans = tuple(sorted(set(found_ids) - set(expected_vector_ids)))
    mismatches = tuple(sorted(str(row["pk"]) for row in found_vectors if
        str(row.get("document_id")) != str(document_id)
        or str(row.get("job_id")) != str(job_id)
        or int(row.get("attempt_number", -1)) != attempt_number))
    if set(embedding_chunk_ids) != set(chunk_ids):
        mismatches = tuple(sorted(set(mismatches) | {"embedding_chunk_set"}))
    return ReconciliationResult(
        job_id, attempt_number, document_id, len(chunk_ids), len(embedding_chunk_ids),
        len(expected_vector_ids), len(found_ids), missing, orphans, duplicates, mismatches,
    )


class PipelineConsistencyError(RuntimeError):
    error_code = "pg_milvus_reconciliation_failed"


class ConcretePageFirstPipeline(PageFirstPipeline):
    def __init__(self, gateway: PageFirstGateway, *, extractor=None) -> None:
        self.gateway = gateway
        self.extractor = extractor or extract_pdf_page_first

    async def run(self, job: ClaimedJob, *, advance: Advance, heartbeat: Heartbeat) -> PipelineResult:
        request = await self.gateway.load_request(job)
        await advance(IngestionStage.EXTRACTING, "page_first_extraction_started", 5.0)
        await heartbeat()
        extracted = await asyncio.to_thread(self.extractor, request.source_path, request.language)

        await advance(IngestionStage.NORMALIZING, "physical_pages_extracted", 18.0)
        await heartbeat()
        # Normalization and conservative editorial signals are produced by extraction.

        await advance(IngestionStage.PERSISTING_PAGES, "unicode_normalization_completed", 30.0)
        persisted = await self.gateway.persist_document_and_pages(request, extracted)
        await heartbeat()

        await advance(IngestionStage.BUILDING_CHUNKS, "canonical_pages_persisted", 45.0)
        chunks = await self.gateway.persist_chunks(request, persisted, extracted)
        if not chunks:
            raise PipelineConsistencyError("No textual chunks were produced")
        await heartbeat()

        await advance(IngestionStage.EMBEDDING, "page_scoped_chunks_persisted", 62.0)
        vectors = await self.gateway.embed(tuple(chunk.content for chunk in chunks), request.embedding_model)
        if len(vectors) != len(chunks):
            raise PipelineConsistencyError("Embedding count does not match chunk count")
        embeddings = await self.gateway.persist_embeddings(request, persisted, chunks, vectors)
        await heartbeat()

        await advance(IngestionStage.INDEXING, "embeddings_persisted", 78.0)
        vector_ids = await self.gateway.index_vectors(request, persisted, embeddings)
        await heartbeat()

        await advance(IngestionStage.VALIDATING_RESULT, "isolated_vectors_indexed", 92.0)
        reconciliation = await self.gateway.reconcile(request, persisted)
        if not reconciliation.consistent:
            raise PipelineConsistencyError(f"Attempt reconciliation failed: {reconciliation}")
        await self.gateway.finalize(request, persisted, reconciliation, extracted)

        pages = extracted.pages
        warnings = list(extracted.warnings)
        if any(page.is_empty for page in pages):
            warnings.append("empty_pages_preserved")
        return PipelineResult(
            document_id=persisted.document_id,
            warnings=tuple(dict.fromkeys(warnings)),
            page_ids=persisted.page_ids,
            chunk_ids=tuple(item.chunk_id for item in chunks),
            embedding_ids=tuple(item.embedding_id for item in embeddings),
            vector_ids=vector_ids,
            page_count=len(pages),
            textual_page_count=sum(not page.is_empty for page in pages),
            empty_page_count=sum(page.is_empty for page in pages),
            heading_count=sum(len(page.headings) for page in pages),
            footnote_count=sum(len(page.footnote_numbers) for page in pages),
            printed_reference_count=sum(len(page.printed_references) for page in pages),
            diagnostics={
                "expected_chunks": reconciliation.expected_chunks,
                "expected_embeddings": reconciliation.expected_embeddings,
                "expected_vectors": reconciliation.expected_vectors,
                "found_vectors": reconciliation.found_vectors,
                "missing": list(reconciliation.missing_vectors),
                "orphans": list(reconciliation.orphan_vectors),
                "duplicates": list(reconciliation.duplicate_vectors),
            },
        )


def detect_language(text: str, requested: str = "auto") -> str:
    if requested in {"es", "en", "he"}:
        return requested
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "es"
    hebrew = len(_HEBREW_RE.findall(text))
    return "he" if hebrew / len(letters) >= 0.4 else "es"


def analyze_page(page_number: int, markdown: str, requested_language: str = "auto") -> ExtractedPage:
    original = markdown.replace("\x00", "").strip()
    normalized = normalize_pdf_search_text(original)
    headings = [match.group(1).strip() for match in _MARKDOWN_HEADING_RE.finditer(original)]
    headings.extend(match.group(1).strip() for match in _UPPER_HEADING_RE.finditer(original))
    footnotes = tuple(dict.fromkeys(int(match.group(1)) for match in _FOOTNOTE_RE.finditer(original)))
    references = tuple(dict.fromkeys(match.group(0).strip() for match in _PRINTED_REFERENCE_RE.finditer(original)))
    return ExtractedPage(
        page_number=page_number,
        original_markdown=original,
        search_text_normalized=normalized,
        language=detect_language(original, requested_language),
        headings=tuple(dict.fromkeys(headings)),
        footnote_numbers=footnotes,
        printed_references=references,
    )


def extract_pdf_page_first(path: Path, requested_language: str = "auto") -> ExtractedDocument:
    if not path.is_file():
        raise FileNotFoundError("Validated upload temporary file is unavailable")
    import pymupdf as fitz
    import pymupdf4llm

    with fitz.open(path) as document:
        page_count = document.page_count
    pages = tuple(
        analyze_page(index + 1, pymupdf4llm.to_markdown(str(path), pages=[index]), requested_language)
        for index in range(page_count)
    )
    content = "\n\n".join(f"## Page {page.page_number}\n\n{page.original_markdown}" for page in pages)
    warnings: list[str] = []
    if not any(not page.is_empty for page in pages):
        raise ValueError("PDF contains no extractable text")
    if any(page.is_empty for page in pages):
        warnings.append("physical_empty_pages_detected")
    language = detect_language(content, requested_language)
    return ExtractedDocument(
        pages=pages,
        content_markdown=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        language=language,
        warnings=tuple(warnings),
    )
