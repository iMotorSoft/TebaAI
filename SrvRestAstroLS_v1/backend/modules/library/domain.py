"""Library domain: enums and dataclasses for collections, documents and text."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


class DocumentLanguage(str, enum.Enum):
    ES = "es"
    EN = "en"
    HE = "he"


class DocumentSourceType(str, enum.Enum):
    BOOK = "book"
    ARTICLE = "article"
    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    TEST_CANDIDATE = "test_candidate"
    ARCHIVED = "archived"
    ERROR = "error"


class TextFormat(str, enum.Enum):
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"


class ExtractionMethod(str, enum.Enum):
    RAW_MARKDOWN = "raw_markdown"
    RAW_TEXT = "raw_text"
    PYMUPDF4LLM = "pymupdf4llm"
    MANUAL = "manual"


class RefType(str, enum.Enum):
    BOOK = "book"
    CHAPTER = "chapter"
    SECTION = "section"
    PAGE = "page"
    PARAGRAPH = "paragraph"
    EXTERNAL = "external"


@dataclass
class LibraryCollection:
    id: UUID
    code: str
    name: str
    description: str | None = None
    default_language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        code: str,
        name: str,
        default_language: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LibraryCollection:
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            code=code.strip().lower(),
            name=name.strip(),
            default_language=default_language,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )


@dataclass
class LibraryDocument:
    id: UUID
    collection_id: UUID
    title: str
    language: str
    source_type: str
    source_sha256: str
    subtitle: str | None = None
    source_path: str | None = None
    source_uri: str | None = None
    source_filename: str | None = None
    source_mime_type: str | None = None
    source_size_bytes: int | None = None
    bibliographic_ref: str | None = None
    author: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    version_label: str | None = None
    status: str = DocumentStatus.DRAFT.value
    metadata: dict[str, Any] = field(default_factory=dict)
    bibliographic_metadata: dict[str, Any] = field(default_factory=dict)
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        collection_id: UUID,
        title: str,
        language: str,
        source_type: str,
        source_sha256: str,
        subtitle: str | None = None,
        source_path: str | None = None,
        source_uri: str | None = None,
        source_filename: str | None = None,
        source_mime_type: str | None = None,
        source_size_bytes: int | None = None,
        bibliographic_ref: str | None = None,
        author: str | None = None,
        publisher: str | None = None,
        publication_year: int | None = None,
        version_label: str | None = None,
        status: str = DocumentStatus.READY.value,
        bibliographic_metadata: dict[str, Any] | None = None,
        created_by: UUID | None = None,
    ) -> LibraryDocument:
        document_status = DocumentStatus(status).value
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            collection_id=collection_id,
            title=title.strip(),
            language=language,
            source_type=source_type,
            source_sha256=source_sha256,
            subtitle=subtitle.strip() if subtitle else None,
            source_path=source_path,
            source_uri=source_uri,
            source_filename=source_filename,
            source_mime_type=source_mime_type,
            source_size_bytes=source_size_bytes,
            bibliographic_ref=bibliographic_ref,
            author=author,
            publisher=publisher,
            publication_year=publication_year,
            version_label=version_label,
            status=document_status,
            bibliographic_metadata=bibliographic_metadata or {},
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )


@dataclass
class LibraryDocumentText:
    id: UUID
    document_id: UUID
    text_format: str
    content: str
    content_sha256: str
    content_length: int
    extraction_method: str
    extraction_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        document_id: UUID,
        text_format: str,
        content: str,
        content_sha256: str,
        extraction_method: str,
        extraction_metadata: dict[str, Any] | None = None,
    ) -> LibraryDocumentText:
        return cls(
            id=uuid4(),
            document_id=document_id,
            text_format=text_format,
            content=content,
            content_sha256=content_sha256,
            content_length=len(content),
            extraction_method=extraction_method,
            extraction_metadata=extraction_metadata or {},
            created_at=datetime.utcnow(),
        )


@dataclass
class LibraryDocumentReference:
    id: UUID
    document_id: UUID
    ref_type: str
    ref_label: str
    ref_value: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        document_id: UUID,
        ref_type: str,
        ref_label: str,
        ref_value: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        chapter: str | None = None,
        section: str | None = None,
    ) -> LibraryDocumentReference:
        return cls(
            id=uuid4(),
            document_id=document_id,
            ref_type=ref_type,
            ref_label=ref_label,
            ref_value=ref_value,
            page_start=page_start,
            page_end=page_end,
            chapter=chapter,
            section=section,
            created_at=datetime.utcnow(),
        )
