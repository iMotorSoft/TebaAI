"""Library ingestion service orchestrator."""

from __future__ import annotations

import json
import pathlib
from uuid import UUID

from psycopg import AsyncConnection

from modules.auth.repository import get_user_by_email
from modules.library.domain import (
    LibraryCollection,
    LibraryDocument,
    LibraryDocumentText,
    ExtractionMethod,
    TextFormat,
)
from modules.library.errors import (
    DuplicateDocumentError,
    UserNotFoundError,
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
    get_document_by_sha256,
    get_or_create_collection,
)
from modules.library.schemas import IngestDocumentRequest, IngestDocumentResult


async def ingest_document(
    conn: AsyncConnection,
    req: IngestDocumentRequest,
) -> IngestDocumentResult:
    """Ingest a document from a file path into the library."""

    path = pathlib.Path(req.file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {req.file_path}")

    # Compute file SHA-256
    file_sha256 = compute_file_sha256(str(path))
    file_size = path.stat().st_size

    # Extract text content
    content, text_format, extraction_method, extraction_metadata = extract_text(str(path))
    content_sha256 = compute_sha256(content.encode("utf-8"))

    # Resolve created_by user if email given
    created_by: UUID | None = None
    if req.created_by_email:
        user = await get_user_by_email(conn, req.created_by_email)
        if not user:
            raise UserNotFoundError(f"User not found: {req.created_by_email}")
        created_by = user.id

    # Parse metadata_json if given
    bibliographic_metadata: dict = {}
    if req.metadata_json:
        try:
            bibliographic_metadata = json.loads(req.metadata_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid metadata_json: {exc}") from exc
        if not isinstance(bibliographic_metadata, dict):
            raise ValueError("metadata_json must contain a JSON object")

    collection_name = req.collection_name or _default_collection_name(req.collection)
    is_test_collection = req.collection.strip().lower().endswith("_test")
    collection_metadata = {"status": "test"} if is_test_collection else {}
    if req.dry_run:
        collection = await get_collection_by_code(conn, req.collection)
        collection_exists = collection is not None
        if collection is None:
            collection = LibraryCollection.create(
                code=req.collection,
                name=collection_name,
                default_language=req.language,
                metadata=collection_metadata,
            )
    else:
        collection, _ = await get_or_create_collection(
            conn,
            code=req.collection,
            name=collection_name,
            default_language=req.language if req.collection_name or is_test_collection else None,
            metadata=collection_metadata,
        )
        collection_exists = True

    # Check duplicate by SHA-256 within collection
    existing = (
        await get_document_by_sha256(conn, collection.id, file_sha256)
        if collection_exists
        else None
    )
    is_new = True
    if existing:
        is_new = False
        if not req.dry_run:
            raise DuplicateDocumentError(
                f"Document already exists in collection '{req.collection}' "
                f"(id={existing.id}, title='{existing.title}')"
            )

    # Build document
    document = LibraryDocument.create(
        collection_id=collection.id,
        title=req.title,
        language=req.language,
        source_type=req.source_type,
        source_sha256=file_sha256,
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

    # Build text
    doc_text = LibraryDocumentText.create(
        document_id=document.id,
        text_format=text_format.value,
        content=content,
        content_sha256=content_sha256,
        extraction_method=extraction_method.value,
        extraction_metadata=extraction_metadata,
    )

    # Persist (unless dry-run)
    if not req.dry_run:
        await create_document(conn, document)
        await create_document_text(conn, doc_text)

    return IngestDocumentResult(
        document_id=document.id,
        collection_code=collection.code,
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
