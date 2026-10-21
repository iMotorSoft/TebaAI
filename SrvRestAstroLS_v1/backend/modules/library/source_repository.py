"""Scope-authorized original source and regional audit metadata (no rejected text)."""
from uuid import UUID

from infrastructure.postgres.transaction import fetch_one
from modules.library.errors import ScopeAccessDeniedError
from modules.library.repository import get_authorized_scope_by_code


async def get_authorized_source(conn, *, user_id: UUID, document_id: UUID):
    row = await fetch_one(conn, """
        SELECT d.id,d.source_path,d.source_sha256,d.organization_id,d.workspace_id,
               d.project_id,d.knowledge_scope_id,ks.knowledge_scope_code
        FROM library_documents d JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
        WHERE d.id=%(id)s AND d.status IN ('ready','test_candidate')
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
    row = await fetch_one(conn, """
        SELECT p.layout_notes->'region_publication' AS publication
        FROM library_pages_v2 p JOIN library_ingestion_runs_v2 r ON r.run_id=p.run_id
        WHERE p.document_id=%(id)s AND p.page_number=%(page)s AND r.status='completed'
        ORDER BY r.finished_at DESC LIMIT 1
        """, {"id": document_id, "page": page})
    return row["publication"] if row else None
