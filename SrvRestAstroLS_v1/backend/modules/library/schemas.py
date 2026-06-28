"""Pydantic schemas for library CLI and service boundaries."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class IngestDocumentRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    language: str = Field(..., pattern=r"^(es|en|he)$")
    collection: str = Field(..., min_length=1)
    source_type: str = Field(..., pattern=r"^(book|article|pdf|markdown|text|other)$")
    collection_name: str | None = None
    subtitle: str | None = None
    author: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    bibliographic_ref: str | None = None
    version_label: str | None = None
    metadata_json: str | None = None
    created_by_email: str | None = None
    dry_run: bool = False


class IngestDocumentResult(BaseModel):
    document_id: UUID
    collection_code: str
    title: str
    language: str
    source_sha256: str
    content_sha256: str
    content_length: int
    status: str
    is_new: bool
    dry_run: bool = False
