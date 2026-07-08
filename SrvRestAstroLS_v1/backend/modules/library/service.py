"""Library ingestion service orchestrator."""

from __future__ import annotations

import json
import pathlib
from uuid import UUID

from psycopg import AsyncConnection

from modules.auth.repository import get_user_by_email
from modules.library.domain import (
    LibraryDocument,
    LibraryDocumentText,
    ExtractionMethod,
    TextFormat,
    KnowledgeScope,
)
from modules.library.errors import (
    DuplicateDocumentError,
    UserNotFoundError,
    ScopeNotFoundError,
)
from modules.library.extractors import (
    compute_file_sha256,
    compute_sha256,
    extract_text,
)
from modules.library.repository import (
    create_document,
    create_document_text,
    get_collection_by_code,
    get_scope_by_code,
    get_document_by_sha256,
)
from modules.library.schemas import IngestDocumentRequest, IngestDocumentResult


async def _resolve_scope(
    conn: AsyncConnection,
    collection_code: str,
) -> KnowledgeScope:
    """Resolve a canonical scope code or a metadata-backed legacy alias."""
    code = collection_code.strip().lower()
    scope = await get_scope_by_code(conn, code)
    if scope:
        return scope

    legacy_collection = await get_collection_by_code(conn, code)
    scope_code = (
        legacy_collection.metadata.get("knowledge_scope_code")
        if legacy_collection
        else None
    )
    if isinstance(scope_code, str) and scope_code.strip():
        scope = await get_scope_by_code(conn, scope_code)
        if scope:
            return scope

    raise ScopeNotFoundError(f"Knowledge scope not found for code: {code}")


async def _resolve_legacy_collection_id(
    conn: AsyncConnection,
    collection_code: str,
) -> UUID:
    """Resolve a legacy collection_id for backward DB compat (NOT NULL constraint).
    Collection is preserved but is not the primary routing key anymore."""
    coll = await get_collection_by_code(conn, collection_code)
    if coll:
        return coll.id
    return UUID("00000000-0000-0000-0000-000000000001")


async def ingest_document(
    conn: AsyncConnection,
    req: IngestDocumentRequest,
) -> IngestDocumentResult:
    """Ingest a document from a file path into the library.
    Uses knowledge_scopes for routing. collection is legacy metadata only.
    """

    path = pathlib.Path(req.file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {req.file_path}")

    file_sha256 = compute_file_sha256(str(path))
    file_size = path.stat().st_size

    content, text_format, extraction_method, extraction_metadata = extract_text(str(path))
    content_sha256 = compute_sha256(content.encode("utf-8"))

    created_by: UUID | None = None
    if req.created_by_email:
        user = await get_user_by_email(conn, req.created_by_email)
        if not user:
            raise UserNotFoundError(f"User not found: {req.created_by_email}")
        created_by = user.id

    bibliographic_metadata: dict = {}
    if req.metadata_json:
        try:
            bibliographic_metadata = json.loads(req.metadata_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid metadata_json: {exc}") from exc
        if not isinstance(bibliographic_metadata, dict):
            raise ValueError("metadata_json must contain a JSON object")

    scope = await _resolve_scope(conn, req.collection)
    legacy_collection_id = await _resolve_legacy_collection_id(conn, req.collection)

    existing = await get_document_by_sha256(conn, file_sha256, knowledge_scope_id=scope.id)
    is_new = True
    if existing:
        is_new = False
        if not req.dry_run:
            raise DuplicateDocumentError(
                f"Document already exists in scope '{scope.knowledge_scope_code}' "
                f"(id={existing.id}, title='{existing.title}')"
            )

    document = LibraryDocument.create(
        collection_id=legacy_collection_id,
        title=req.title,
        language=req.language,
        source_type=req.source_type,
        source_sha256=file_sha256,
        knowledge_scope_id=scope.id,
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        project_id=scope.project_id,
        subtitle=req.subtitle,
        source_path=str(path.resolve()),
        source_filename=path.name,
        source_mime_type=_guess_mime_type(path.suffix),
        source_size_bytes=file_size,
        bibliographic_ref=req.bibliographic_ref,
        author=req.author,
        publisher=req.publisher,
        publication_year=req.publication_year,
        version_label=req.version_label,
        status=req.status,
        bibliographic_metadata=bibliographic_metadata,
        created_by=created_by,
    )

    doc_text = LibraryDocumentText.create(
        document_id=document.id,
        text_format=text_format.value,
        content=content,
        content_sha256=content_sha256,
        extraction_method=extraction_method.value,
        knowledge_scope_id=scope.id,
        extraction_metadata=extraction_metadata,
    )

    if not req.dry_run:
        await create_document(conn, document)
        await create_document_text(conn, doc_text)

    return IngestDocumentResult(
        document_id=document.id,
        knowledge_scope_code=scope.knowledge_scope_code,
        title=document.title,
        language=document.language,
        source_sha256=file_sha256,
        content_sha256=content_sha256,
        content_length=len(content),
        status=document.status,
        is_new=is_new,
        dry_run=req.dry_run,
    )


def _guess_mime_type(extension: str) -> str | None:
    mime_map = {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
    }
    return mime_map.get(extension.lower())


def _default_collection_name(code: str) -> str:
    normalized = code.strip().lower()
    if normalized.endswith("_test"):
        base = normalized.removesuffix("_test").replace("_", " ").title()
        return f"{base} Test Corpus"
    return normalized
