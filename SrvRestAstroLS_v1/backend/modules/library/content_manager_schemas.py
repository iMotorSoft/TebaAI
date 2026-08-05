"""Schemas for the Content Manager V1 — controlled PDF upload & ingestion."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Upload ───────────────────────────────────────────────────────────────


class UploadValidationStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class DuplicateClassification(str, enum.Enum):
    NEW_DOCUMENT = "new_document"
    EXACT_DUPLICATE = "exact_duplicate"
    KNOWN_SOURCE_NEW_INSTANCE = "known_source_new_instance"
    POSSIBLE_REVISED_EDITION = "possible_revised_edition"


class UploadLimits(BaseModel):
    max_upload_bytes: int
    max_pdf_pages: int


class ExistingDocumentInfo(BaseModel):
    document_id: UUID
    title: str
    status: str
    created_at: datetime | None = None
    source_sha256_short: str | None = None


class UploadResponse(BaseModel):
    upload_id: UUID
    filename: str
    size_bytes: int
    sha256: str
    mime_type: str
    page_count: int | None = None
    validation_status: UploadValidationStatus
    duplicate_status: DuplicateClassification
    existing_document: ExistingDocumentInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    limits: UploadLimits


class UploadValidationError(BaseModel):
    code: str
    detail: str
    field: str | None = None


# ── Ingestion Job ─────────────────────────────────────────────────────────


class IngestionStage(str, enum.Enum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    READY_TO_INGEST = "ready_to_ingest"
    QUEUED = "queued"
    CLAIMED = "claimed"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    PERSISTING_PAGES = "persisting_pages"
    BUILDING_CHUNKS = "building_chunks"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    VALIDATING_RESULT = "validating_result"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionProfile(str, enum.Enum):
    AUTO = "auto"
    NEEDS_REVIEW = "needs_pipeline_review"


class CreateJobRequest(BaseModel):
    upload_id: UUID
    knowledge_scope_code: str = Field(default="breslov_primary", min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    language: str = Field(default="auto", pattern=r"^(auto|es|en|he|mixed|unknown)$")
    work_family: str | None = Field(default=None, max_length=100)
    administrative_notes: str | None = Field(default=None, max_length=2000)
    ingestion_profile: IngestionProfile = IngestionProfile.AUTO
    requested_status: str = Field(default="test_candidate")

    @property
    def requested_status_value(self) -> str:
        return self.requested_status


class JobProgress(BaseModel):
    current_stage: IngestionStage
    progress_percent: float = 0.0
    stage_display: str | None = None
    is_terminal: bool = False
    stage_states: dict[str, str] = Field(default_factory=dict)  # stage -> pending|active|done|failed|warning


class JobResponse(BaseModel):
    job_id: UUID
    upload_id: UUID
    document_id: UUID | None = None
    title: str
    language: str
    status: IngestionStage
    progress: JobProgress | None = None
    error_code: str | None = None
    error_message: str | None = None
    warning_codes: list[str] = Field(default_factory=list)
    attempt_number: int = 1
    ingestion_profile: IngestionProfile = IngestionProfile.AUTO
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    worker_id: str | None = None
    claimed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    cleanup_status: str | None = None
    recovery_status: str | None = None
    pipeline_version: str | None = None
    idempotency_key: str | None = None


class JobListItem(BaseModel):
    job_id: UUID
    upload_id: UUID
    document_id: UUID | None = None
    title: str
    language: str
    status: IngestionStage
    current_stage: IngestionStage | None = None
    created_at: datetime | None = None
    attempt_number: int = 1
    filename: str | None = None
    sha256_short: str | None = None


class JobListResponse(BaseModel):
    jobs: list[JobListItem]
    summary: dict[str, int]  # status -> count


# ── Diagnostic Result ─────────────────────────────────────────────────────


class IngestionDiagnostic(BaseModel):
    document_id: UUID | None = None
    job_id: UUID
    pdf_pages: int | None = None
    canonical_pages: int | None = None
    textual_pages: int | None = None
    empty_pages: int | None = None
    chunks: int | None = None
    embeddings: int | None = None
    pg_embedding_count: int | None = None
    milvus_entity_count: int | None = None
    pg_missing: int | None = None
    milvus_missing: int | None = None
    milvus_orphan: int | None = None
    page_integrity: str | None = None  # "match", "mismatch", "pending"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    stage_timings: dict[str, float] = Field(default_factory=dict)  # stage -> seconds
    cleanup_result: str | None = None
    technical_details: dict[str, Any] = Field(default_factory=dict)


# ── Summary View ──────────────────────────────────────────────────────────


class DocumentIngestionSummary(BaseModel):
    document_id: UUID
    title: str
    status: str
    language: str
    source_sha256: str | None = None
    pdf_pages: int | None = None
    chunks: int | None = None
    embeddings: int | None = None
    warnings: list[str] = Field(default_factory=list)
    latest_job_id: UUID | None = None
    created_at: datetime | None = None
