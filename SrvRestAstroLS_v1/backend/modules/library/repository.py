"""Library PostgreSQL repository using async psycopg 3."""

from __future__ import annotations

import json
from uuid import UUID

from psycopg import AsyncConnection

from infrastructure.postgres.transaction import execute, fetch_all, fetch_one
from modules.library.domain import (
    LibraryDocument,
    LibraryDocumentReference,
    LibraryDocumentText,
    KnowledgeScope,
)
from modules.library.errors import (
    DocumentNotFoundError,
    ScopeAccessDeniedError,
    ScopeNotFoundError,
)


# ── Knowledge Scopes ───────────────────────────────────────────────────


async def get_scope_by_code(
    conn: AsyncConnection,
    knowledge_scope_code: str,
    organization_id: UUID | None = None,
) -> KnowledgeScope | None:
    """Resolve a knowledge_scope_code to a KnowledgeScope dataclass."""
    if organization_id:
        row = await fetch_one(
            conn,
            "SELECT * FROM knowledge_scopes WHERE knowledge_scope_code = %(code)s AND organization_id = %(org_id)s",
            {"code": knowledge_scope_code.strip().lower(), "org_id": str(organization_id)},
        )
    else:
        row = await fetch_one(
            conn,
            "SELECT * FROM knowledge_scopes WHERE knowledge_scope_code = %(code)s",
            {"code": knowledge_scope_code.strip().lower()},
        )
    return _row_to_scope(row) if row else None


async def get_scope_by_id(conn: AsyncConnection, scope_id: UUID) -> KnowledgeScope | None:
    row = await fetch_one(
        conn,
        "SELECT * FROM knowledge_scopes WHERE id = %(id)s",
        {"id": str(scope_id)},
    )
    return _row_to_scope(row) if row else None


# @lat: [[tenant-context-authorization-policy#Scope Isolation]]
async def get_authorized_scope_by_code(
    conn: AsyncConnection,
    *,
    user_id: UUID,
    knowledge_scope_code: str,
) -> KnowledgeScope:
    """Resolve an active scope through the user's complete tenant membership chain."""
    row = await fetch_one(
        conn,
        """
        SELECT ks.*
        FROM knowledge_scopes ks
        JOIN projects p
          ON p.id = ks.project_id
         AND p.organization_id = ks.organization_id
         AND p.workspace_id = ks.workspace_id
         AND p.status = 'active'
        JOIN workspaces w
          ON w.id = ks.workspace_id
         AND w.organization_id = ks.organization_id
         AND w.status = 'active'
        JOIN organizations o
          ON o.id = ks.organization_id
         AND o.status = 'active'
        JOIN users u
          ON u.id = %(user_id)s
         AND u.is_active = true
        JOIN organization_members om
          ON om.organization_id = o.id
         AND om.user_id = u.id
         AND om.status = 'active'
        JOIN workspace_members wm
          ON wm.workspace_id = w.id
         AND wm.user_id = u.id
         AND wm.status = 'active'
        JOIN project_members pm
          ON pm.project_id = p.id
         AND pm.user_id = u.id
         AND pm.status = 'active'
        WHERE ks.knowledge_scope_code = %(scope_code)s
          AND ks.status = 'active'
        """,
        {
            "user_id": str(user_id),
            "scope_code": knowledge_scope_code.strip().lower(),
        },
    )
    if row is None:
        raise ScopeAccessDeniedError("Knowledge scope is unavailable")
    return _row_to_scope(row)


async def resolve_scope_context(
    conn: AsyncConnection,
    organization_code: str = "tebaai",
    workspace_code: str = "breslov",
    project_code: str = "breslov_library",
    knowledge_scope_code: str = "breslov_primary",
) -> KnowledgeScope:
    """Resolve multi-tenant context to a KnowledgeScope.
    This is the canonical entry point for all runtime scope resolution."""
    row = await fetch_one(
        conn,
        """
        SELECT ks.*
        FROM knowledge_scopes ks
        JOIN projects p ON p.id = ks.project_id
        JOIN workspaces w ON w.id = p.workspace_id
        JOIN organizations o ON o.id = w.organization_id
        WHERE o.organization_code = %(org)s
          AND w.workspace_code = %(ws)s
          AND p.project_code = %(proj)s
          AND ks.knowledge_scope_code = %(scope)s
        """,
        {
            "org": organization_code.strip().lower(),
            "ws": workspace_code.strip().lower(),
            "proj": project_code.strip().lower(),
            "scope": knowledge_scope_code.strip().lower(),
        },
    )
    if not row:
        raise ScopeNotFoundError(
            f"Knowledge scope not found: {organization_code}/{workspace_code}/{project_code}/{knowledge_scope_code}"
        )
    return _row_to_scope(row)


# ── Legacy Collections (DEPRECATED) ────────────────────────────────────
# These functions exist only for backward compatibility with library_collections_legacy.
# Do not use for new code. Use get_scope_by_code / resolve_scope_context instead.


async def get_or_create_collection(
    conn: AsyncConnection,
    code: str,
    name: str,
    default_language: str | None = None,
    metadata: dict | None = None,
) -> tuple:
    """DEPRECATED: pre-knowledge_scopes. Do not use for new ingestions."""
    from modules.library.domain import LibraryCollection
    row = await fetch_one(
        conn,
        "SELECT * FROM library_collections_legacy WHERE code = %(code)s",
        {"code": code.strip().lower()},
    )
    if row:
        return _row_to_collection(row), False

    collection = LibraryCollection.create(
        code=code,
        name=name,
        default_language=default_language,
        metadata=metadata,
    )
    await execute(
        conn,
        """
        INSERT INTO library_collections_legacy (id, code, name, description, default_language, metadata, is_active, created_at, updated_at)
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


async def get_collection_by_code(conn: AsyncConnection, code: str):
    """DEPRECATED: pre-knowledge_scopes. Do not use for new code."""
    from modules.library.domain import LibraryCollection
    row = await fetch_one(
        conn,
        "SELECT * FROM library_collections_legacy WHERE code = %(code)s",
        {"code": code.strip().lower()},
    )
    return _row_to_collection(row) if row else None


# ── Documents ──────────────────────────────────────────────────────────


async def get_document_by_sha256(conn: AsyncConnection, sha256: str, knowledge_scope_id: UUID | None = None) -> LibraryDocument | None:
    """Get document by SHA-256, optionally scoped to a knowledge_scope_id."""
    if knowledge_scope_id:
        row = await fetch_one(
            conn,
            "SELECT * FROM library_documents WHERE knowledge_scope_id = %(scope_id)s AND source_sha256 = %(sha256)s",
            {"scope_id": str(knowledge_scope_id), "sha256": sha256},
        )
    else:
        row = await fetch_one(
            conn,
            "SELECT * FROM library_documents WHERE source_sha256 = %(sha256)s",
            {"sha256": sha256},
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
            bibliographic_metadata,
            knowledge_scope_id, organization_id, workspace_id, project_id,
            document_code, content_sha256, canonical_text_role,
            editor, translator, edition, chunk_set_version, archived_at,
            created_by, created_at, updated_at
        ) VALUES (
            %(id)s, %(collection_id)s, %(title)s, %(subtitle)s, %(language)s, %(source_type)s,
            %(source_path)s, %(source_uri)s, %(source_filename)s, %(source_mime_type)s,
            %(source_size_bytes)s, %(source_sha256)s, %(bibliographic_ref)s, %(author)s,
            %(publisher)s, %(publication_year)s, %(version_label)s, %(status)s, %(metadata)s,
            %(bibliographic_metadata)s,
            %(knowledge_scope_id)s, %(organization_id)s, %(workspace_id)s, %(project_id)s,
            %(document_code)s, %(content_sha256)s, %(canonical_text_role)s,
            %(editor)s, %(translator)s, %(edition)s, %(chunk_set_version)s, %(archived_at)s,
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
            "bibliographic_metadata": json.dumps(document.bibliographic_metadata),
            "knowledge_scope_id": str(document.knowledge_scope_id) if document.knowledge_scope_id else None,
            "organization_id": str(document.organization_id) if document.organization_id else None,
            "workspace_id": str(document.workspace_id) if document.workspace_id else None,
            "project_id": str(document.project_id) if document.project_id else None,
            "document_code": document.document_code,
            "content_sha256": document.content_sha256,
            "canonical_text_role": document.canonical_text_role,
            "editor": document.editor,
            "translator": document.translator,
            "edition": document.edition,
            "chunk_set_version": document.chunk_set_version,
            "archived_at": document.archived_at,
            "created_by": str(document.created_by) if document.created_by else None,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        },
    )
    return document


async def list_documents(
    conn: AsyncConnection,
    knowledge_scope_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[LibraryDocument], int]:
    if knowledge_scope_id:
        rows = await fetch_all(
            conn,
            "SELECT * FROM library_documents WHERE knowledge_scope_id = %(scope_id)s ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s",
            {"scope_id": str(knowledge_scope_id), "limit": limit, "offset": offset},
        )
        total_row = await fetch_one(
            conn,
            "SELECT COUNT(*) AS cnt FROM library_documents WHERE knowledge_scope_id = %(scope_id)s",
            {"scope_id": str(knowledge_scope_id)},
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
        INSERT INTO library_document_texts (id, document_id, text_format, content, content_sha256, content_length, extraction_method, text_role, knowledge_scope_id, page_markers_enabled, page_count, extraction_metadata, created_at)
        VALUES (%(id)s, %(document_id)s, %(text_format)s, %(content)s, %(content_sha256)s, %(content_length)s, %(extraction_method)s, %(text_role)s, %(knowledge_scope_id)s, %(page_markers_enabled)s, %(page_count)s, %(extraction_metadata)s, %(created_at)s)
        """,
        {
            "id": str(text.id),
            "document_id": str(text.document_id),
            "text_format": text.text_format,
            "content": text.content,
            "content_sha256": text.content_sha256,
            "content_length": text.content_length,
            "extraction_method": text.extraction_method,
            "text_role": text.text_role,
            "knowledge_scope_id": str(text.knowledge_scope_id) if text.knowledge_scope_id else None,
            "page_markers_enabled": text.page_markers_enabled,
            "page_count": text.page_count,
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


def _row_to_scope(row: dict) -> KnowledgeScope:
    return KnowledgeScope(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        project_id=row["project_id"],
        knowledge_scope_code=row["knowledge_scope_code"],
        name=row["name"],
        description=row.get("description"),
        scope_type=row.get("scope_type") or "bibliographic_corpus",
        language_policy=row.get("language_policy"),
        status=row.get("status") or "draft",
        metadata=row.get("metadata") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_collection(row: dict):
    """DEPRECATED: pre-knowledge_scopes converter for library_collections_legacy."""
    from modules.library.domain import LibraryCollection
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
        editor=row.get("editor"),
        translator=row.get("translator"),
        edition=row.get("edition"),
        version_label=row.get("version_label"),
        status=row["status"],
        metadata=row.get("metadata") or {},
        bibliographic_metadata=row.get("bibliographic_metadata") or {},
        knowledge_scope_id=row.get("knowledge_scope_id"),
        organization_id=row.get("organization_id"),
        workspace_id=row.get("workspace_id"),
        project_id=row.get("project_id"),
        document_code=row.get("document_code"),
        content_sha256=row.get("content_sha256"),
        canonical_text_role=row.get("canonical_text_role") or "candidate",
        chunk_set_version=row.get("chunk_set_version"),
        created_by=row.get("created_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        archived_at=row.get("archived_at"),
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
        text_role=row.get("text_role") or "canonical",
        knowledge_scope_id=row.get("knowledge_scope_id"),
        page_markers_enabled=row.get("page_markers_enabled") or False,
        page_count=row.get("page_count"),
        extraction_metadata=row.get("extraction_metadata") or {},
        created_at=row.get("created_at"),
    )
