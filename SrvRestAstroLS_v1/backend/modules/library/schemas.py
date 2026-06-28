"""Pydantic schemas for library CLI and service boundaries."""

from __future__ import annotations

from typing import Literal
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


# ── Search ──────────────────────────────────────────────────────────────────


class LibrarySearchRequest(BaseModel):
    collection: str = Field(default="breslov", min_length=1, max_length=100)
    query: str = Field(..., min_length=1, max_length=300)
    mode: Literal["auto", "fts", "phrase", "trigram"] = "auto"
    top_k: int = Field(default=10, ge=1, le=50)
    language: Literal["es", "en", "he"] = "es"


class LibrarySearchResult(BaseModel):
    document_id: UUID
    document_title: str
    author: str | None = None
    collection_code: str
    chunk_id: UUID
    chunk_index: int
    language: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = None
    section: str | None = None
    match_type: str
    rank: float | None = None
    plain_excerpt: str | None = None
    highlighted_excerpt: str = ""
    content_length: int = 0


class LibrarySearchResponse(BaseModel):
    query: str
    collection: str
    mode: str
    language: str
    total: int
    results: list[LibrarySearchResult]
