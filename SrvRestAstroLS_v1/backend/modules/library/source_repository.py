"""Scope-authorized original source and regional audit metadata (no rejected text).

Visibility rules:

* the original source is served for the document that carries the ACTIVE
  generation of its logical document;
* the published page metadata is resolved from the ACTIVE generation, never
  from "the most recent completed run". A candidate generation that completes
  before a cutover must not steal the viewer from the active generation.
"""
from uuid import UUID

from infrastructure.postgres.transaction import fetch_one
from modules.library.errors import ScopeAccessDeniedError
from modules.library.repository import get_authorized_scope_by_code


async def get_authorized_source(conn, *, user_id: UUID, document_id: UUID):
    row = await fetch_one(conn, """
        SELECT d.id,d.source_path,d.source_sha256,d.organization_id,d.workspace_id,
               d.project_id,d.knowledge_scope_id,ks.knowledge_scope_code
        FROM library_visible_documents d
        JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
        WHERE d.id=%(id)s
        """, {"id": document_id})
    if not row:
        raise ScopeAccessDeniedError("Source unavailable")
    scope = await get_authorized_scope_by_code(
        conn, user_id=user_id, knowledge_scope_code=row["knowledge_scope_code"],
    )
    if any(str(row[name]) != str(getattr(scope, name)) for name in
           ("organization_id", "workspace_id", "project_id")) or str(row["knowledge_scope_id"]) != str(scope.id):
        raise ScopeAccessDeniedError("Source unavailable")
    return row


async def get_page_publication(conn, document_id: UUID, page: int):
    """Published region metadata of the ACTIVE generation for one physical page.

    The generation is resolved through the active pointer. A candidate or
    inactive generation never contributes page metadata, even when its run
    completed later than the active one.
    """
    row = await fetch_one(conn, """
        SELECT p.layout_notes->'region_publication' AS publication
        FROM library_pages_v2 p
        JOIN library_document_generations g
          ON g.document_id = p.document_id AND g.status = 'ACTIVE'
        JOIN library_logical_document_active_generations ap
          ON ap.logical_document_id = g.logical_document_id
         AND ap.generation_id = g.id
        WHERE p.document_id=%(id)s
          AND p.page_number=%(page)s
          AND (g.run_id IS NULL OR p.run_id = g.run_id)
        """, {"id": document_id, "page": page})
    return row["publication"] if row else None


async def get_generation_page_publication(
    conn, document_id: UUID, generation_id: UUID, page: int,
):
    """Administrative page metadata for one explicit generation."""
    row = await fetch_one(conn, """
        SELECT p.layout_notes->'region_publication' AS publication
        FROM library_pages_v2 p
        JOIN library_document_generations g ON g.document_id = p.document_id
        WHERE p.document_id=%(id)s
          AND g.id=%(generation)s
          AND p.page_number=%(page)s
        """, {"id": document_id, "generation": generation_id, "page": page})
    return row["publication"] if row else None
