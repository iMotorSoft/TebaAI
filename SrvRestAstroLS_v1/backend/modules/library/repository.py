"""Library PostgreSQL repository using async psycopg 3."""

from __future__ import annotations

import json
from uuid import UUID

from psycopg import AsyncConnection

from infrastructure.postgres.transaction import execute, fetch_all, fetch_one
from modules.library.domain import (
    LibraryCollection,
    LibraryDocument,
    LibraryDocumentReference,
    LibraryDocumentText,
)
from modules.library.errors import CollectionNotFoundError, DocumentNotFoundError


# ── Collections ────────────────────────────────────────────────────────


async def get_or_create_collection(
    conn: AsyncConnection,
    code: str,
    name: str,
    default_language: str | None = None,
) -> tuple[LibraryCollection, bool]:
    row = await fetch_one(
        conn,
        "SELECT * FROM library_collections WHERE code = %(code)s",
        {"code": code.strip().lower()},
    )
    if row:
        return _row_to_collection(row), False

    collection = LibraryCollection.create(
        code=code,
        name=name,
        default_language=default_language,
    )
    await execute(
        conn,
        """
        INSERT INTO library_collections (id, code, name, description, default_language, metadata, is_active, created_at, updated_at)
        VALUES (%(id)s, %(code)s, %(name)s, %(description)s, %(default_language)s, %(metadata)s, %(is_active)s, %(created_at)s, %(updated_at)s)
        """,
        {
            "id": str(collection.id),
            "code": collection.code,
            "name": collection.name,
            "description": collection.description,
            "default_language": collection.default_language,
            "metadata": json.dumps(collection.metadata),
            "is_active": collection.is_active,
            "created_at": collection.created_at,
            "updated_at": collection.updated_at,
        },
    )
    return collection, True


async def get_collection_by_code(conn: AsyncConnection, code: str) -> LibraryCollection | None:
    row = await fetch_one(
        conn,
        "SELECT * FROM library_collections WHERE code = %(code)s",
        {"code": code.strip().lower()},
    )
    return _row_to_collection(row) if row else None


# ── Documents ──────────────────────────────────────────────────────────


async def get_document_by_sha256(conn: AsyncConnection, collection_id: UUID, sha256: str) -> LibraryDocument | None:
    row = await fetch_one(
        conn,
        "SELECT * FROM library_documents WHERE collection_id = %(collection_id)s AND source_sha256 = %(sha256)s",
        {"collection_id": str(collection_id), "sha256": sha256},
    )
    return _row_to_document(row) if row else None


async def get_document_by_id(conn: AsyncConnection, document_id: UUID) -> LibraryDocument | None:
    row = await fetch_one(
        conn,
        "SELECT * FROM library_documents WHERE id = %(id)s",
        {"id": str(document_id)},
    )
    return _row_to_document(row) if row else None


async def create_document(
    conn: AsyncConnection,
    document: LibraryDocument,
) -> LibraryDocument:
    await execute(
        conn,
        """
        INSERT INTO library_documents (
            id, collection_id, title, subtitle, language, source_type,
            source_path, source_uri, source_filename, source_mime_type,
            source_size_bytes, source_sha256, bibliographic_ref, author,
            publisher, publication_year, version_label, status, metadata,
            created_by, created_at, updated_at
        ) VALUES (
            %(id)s, %(collection_id)s, %(title)s, %(subtitle)s, %(language)s, %(source_type)s,
            %(source_path)s, %(source_uri)s, %(source_filename)s, %(source_mime_type)s,
            %(source_size_bytes)s, %(source_sha256)s, %(bibliographic_ref)s, %(author)s,
            %(publisher)s, %(publication_year)s, %(version_label)s, %(status)s, %(metadata)s,
            %(created_by)s, %(created_at)s, %(updated_at)s
        )
        """,
        {
            "id": str(document.id),
            "collection_id": str(document.collection_id),
            "title": document.title,
            "subtitle": document.subtitle,
            "language": document.language,
            "source_type": document.source_type,
            "source_path": document.source_path,
            "source_uri": document.source_uri,
            "source_filename": document.source_filename,
            "source_mime_type": document.source_mime_type,
            "source_size_bytes": document.source_size_bytes,
            "source_sha256": document.source_sha256,
            "bibliographic_ref": document.bibliographic_ref,
            "author": document.author,
            "publisher": document.publisher,
            "publication_year": document.publication_year,
            "version_label": document.version_label,
            "status": document.status,
            "metadata": json.dumps(document.metadata),
            "created_by": str(document.created_by) if document.created_by else None,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        },
    )
    return document


async def list_documents(
    conn: AsyncConnection,
    collection_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[LibraryDocument], int]:
    if collection_id:
        rows = await fetch_all(
            conn,
            "SELECT * FROM library_documents WHERE collection_id = %(collection_id)s ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s",
            {"collection_id": str(collection_id), "limit": limit, "offset": offset},
        )
        total_row = await fetch_one(
            conn,
            "SELECT COUNT(*) AS cnt FROM library_documents WHERE collection_id = %(collection_id)s",
            {"collection_id": str(collection_id)},
        )
    else:
        rows = await fetch_all(
            conn,
            "SELECT * FROM library_documents ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s",
            {"limit": limit, "offset": offset},
        )
        total_row = await fetch_one(conn, "SELECT COUNT(*) AS cnt FROM library_documents")

    total = total_row["cnt"] if total_row else 0
    return [_row_to_document(r) for r in rows], total


# ── Document texts ─────────────────────────────────────────────────────


async def create_document_text(
    conn: AsyncConnection,
    text: LibraryDocumentText,
) -> LibraryDocumentText:
    await execute(
        conn,
        """
        INSERT INTO library_document_texts (id, document_id, text_format, content, content_sha256, content_length, extraction_method, extraction_metadata, created_at)
        VALUES (%(id)s, %(document_id)s, %(text_format)s, %(content)s, %(content_sha256)s, %(content_length)s, %(extraction_method)s, %(extraction_metadata)s, %(created_at)s)
        """,
        {
            "id": str(text.id),
            "document_id": str(text.document_id),
            "text_format": text.text_format,
            "content": text.content,
            "content_sha256": text.content_sha256,
            "content_length": text.content_length,
            "extraction_method": text.extraction_method,
            "extraction_metadata": json.dumps(text.extraction_metadata),
            "created_at": text.created_at,
        },
    )
    return text


async def get_document_text_by_document_id(
    conn: AsyncConnection, document_id: UUID
) -> LibraryDocumentText | None:
    row = await fetch_one(
        conn,
        "SELECT * FROM library_document_texts WHERE document_id = %(document_id)s ORDER BY created_at DESC LIMIT 1",
        {"document_id": str(document_id)},
    )
    return _row_to_document_text(row) if row else None


# ── References ─────────────────────────────────────────────────────────


async def create_document_reference(
    conn: AsyncConnection,
    ref: LibraryDocumentReference,
) -> LibraryDocumentReference:
    await execute(
        conn,
        """
        INSERT INTO library_document_references (id, document_id, ref_type, ref_label, ref_value, page_start, page_end, chapter, section, metadata, created_at)
        VALUES (%(id)s, %(document_id)s, %(ref_type)s, %(ref_label)s, %(ref_value)s, %(page_start)s, %(page_end)s, %(chapter)s, %(section)s, %(metadata)s, %(created_at)s)
        """,
        {
            "id": str(ref.id),
            "document_id": str(ref.document_id),
            "ref_type": ref.ref_type,
            "ref_label": ref.ref_label,
            "ref_value": ref.ref_value,
            "page_start": ref.page_start,
            "page_end": ref.page_end,
            "chapter": ref.chapter,
            "section": ref.section,
            "metadata": ref.metadata,
            "created_at": ref.created_at,
        },
    )
    return ref


# ── Row converters ─────────────────────────────────────────────────────


def _row_to_collection(row: dict) -> LibraryCollection:
    return LibraryCollection(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        description=row.get("description"),
        default_language=row.get("default_language"),
        metadata=row.get("metadata") or {},
        is_active=row["is_active"],
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_document(row: dict) -> LibraryDocument:
    return LibraryDocument(
        id=row["id"],
        collection_id=row["collection_id"],
        title=row["title"],
        subtitle=row.get("subtitle"),
        language=row["language"],
        source_type=row["source_type"],
        source_path=row.get("source_path"),
        source_uri=row.get("source_uri"),
        source_filename=row.get("source_filename"),
        source_mime_type=row.get("source_mime_type"),
        source_size_bytes=row.get("source_size_bytes"),
        source_sha256=row["source_sha256"],
        bibliographic_ref=row.get("bibliographic_ref"),
        author=row.get("author"),
        publisher=row.get("publisher"),
        publication_year=row.get("publication_year"),
        version_label=row.get("version_label"),
        status=row["status"],
        metadata=row.get("metadata") or {},
        created_by=row.get("created_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_document_text(row: dict) -> LibraryDocumentText:
    return LibraryDocumentText(
        id=row["id"],
        document_id=row["document_id"],
        text_format=row["text_format"],
        content=row["content"],
        content_sha256=row["content_sha256"],
        content_length=row["content_length"],
        extraction_method=row["extraction_method"],
        extraction_metadata=row.get("extraction_metadata") or {},
        created_at=row.get("created_at"),
    )
