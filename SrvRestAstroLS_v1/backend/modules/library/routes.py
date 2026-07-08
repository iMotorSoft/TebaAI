"""Library HTTP routes."""

from __future__ import annotations

from uuid import UUID

from litestar import Request, post
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    PermissionDeniedException,
)

from core.dependencies import get_pg_pool
from infrastructure.postgres.transaction import transaction
from modules.auth.dependencies import get_current_user_payload
from modules.auth.guards import require_auth
from modules.library.errors import ScopeAccessDeniedError
from modules.library.hybrid_search import search_chunks_hybrid
from modules.library.repository import get_authorized_scope_by_code
from modules.library.relation_qa_schemas import RelationQARequest, RelationQAResponse
from modules.library.relation_qa_service import run_relation_qa
from modules.library.schemas import (
    LibrarySearchRequest,
    LibrarySearchResponse,
    LibrarySearchResult,
)
from modules.library.text_search import search_chunks_text


@post("/library/relation-qa", status_code=200, guards=[require_auth])
async def relation_qa(
    request: Request,
    data: RelationQARequest,
) -> RelationQAResponse:
    """Run authenticated, scope-authorized and read-only relation QA."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthorizedException("Invalid authenticated subject") from exc

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn,
                user_id=user_id,
                knowledge_scope_code=data.knowledge_scope_code,
            )
            return await run_relation_qa(
                conn,
                data,
                scope,
                allow_debug=payload.get("role") == "admin",
            )
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Relation QA failed") from exc


@post("/library/search", status_code=200, guards=[require_auth])
async def library_search(
    request: Request,
    data: LibrarySearchRequest,
) -> LibrarySearchResponse:
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthorizedException("Invalid authenticated subject") from exc

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn,
                user_id=user_id,
                knowledge_scope_code=data.collection,
            )
            knowledge_scope_code = scope.knowledge_scope_code
            if data.mode == "hybrid":
                raw_results = await search_chunks_hybrid(
                    conn,
                    knowledge_scope_code=knowledge_scope_code,
                    query=data.query,
                    top_k=data.top_k,
                    language=data.language,
                )
            else:
                raw_results = await search_chunks_text(
                    conn,
                    knowledge_scope_code=knowledge_scope_code,
                    query=data.query,
                    top_k=data.top_k,
                    mode=data.mode,
                    language=data.language,
                )
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Search failed") from exc

    results = [
        LibrarySearchResult(
            document_id=r["document_id"],
            document_title=r.get("document_title", ""),
            author=r.get("author"),
            knowledge_scope_code=r.get("knowledge_scope_code", knowledge_scope_code),
            chunk_id=r["chunk_id"],
            chunk_index=r["chunk_index"],
            language=r.get("language"),
            page_start=r.get("page_start"),
            page_end=r.get("page_end"),
            chapter=r.get("chapter"),
            section=r.get("section"),
            match_type=r.get("match_type", data.mode),
            rank=r.get("rank"),
            fts_rank=r.get("fts_rank"),
            vector_score=r.get("vector_score"),
            hybrid_score=r.get("hybrid_score"),
            source_signals=r.get("source_signals", []),
            plain_excerpt=r.get("plain_excerpt"),
            highlighted_excerpt=r.get("highlighted_excerpt", ""),
            content_length=r.get("content_length", 0),
        )
        for r in raw_results
    ]

    return LibrarySearchResponse(
        query=data.query,
        collection=knowledge_scope_code,
        mode=data.mode,
        language=data.language,
        total=len(results),
        results=results,
    )
