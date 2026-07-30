"""Library HTTP routes."""

from __future__ import annotations

from uuid import UUID

from litestar import Request, get, post
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    PermissionDeniedException,
)

from core.dependencies import get_pg_pool
from infrastructure.postgres.transaction import transaction
from modules.auth.dependencies import get_current_user_payload
from modules.auth.guards import require_auth
from modules.library.book_qa_schemas import (
    BookQALatestRunResponse,
    BookQARequest,
    BookQAResponse,
    BookQARunsResponse,
)
from modules.library.book_qa_service import (
    get_latest_book_qa_run,
    list_book_qa_runs,
    run_book_qa,
)
from modules.library.errors import ScopeAccessDeniedError
from modules.library.hybrid_search import search_chunks_hybrid
from modules.library.relation_qa_schemas import RelationQARequest, RelationQAResponse
from modules.library.relation_qa_service import run_relation_qa
from modules.library.repository import get_authorized_scope_by_code
from modules.library.schemas import (
    LibrarySearchRequest,
    LibrarySearchResponse,
    LibrarySearchResult,
)
from modules.library.text_search import search_chunks_text
from modules.library.investigative_qa_v1 import (
    PreparedQuery,
    QaRequest,
    interpret_only,
    run as run_investigative_qa_v1,
)
from modules.library.multilingual_query import QueryInterpretation
from modules.library.named_topics import NamedTopicResolution
from modules.library.query_confirmation import (
    INTERPRETATION_STORE,
    InterpretationStateError,
)
from modules.library.simple_research_rag import run_simple_rag
from globalVar import RESEARCH_PIPELINE


async def _run_research_pipeline(
    conn: object,
    data: QaRequest,
    *,
    pipeline: str,
    prepared: PreparedQuery | None = None,
) -> dict:
    """Keep legacy and confirmation-phase execution on the same pipeline."""
    if pipeline == "advanced":
        return await run_investigative_qa_v1(conn, data, prepared=prepared)

    simple = await run_simple_rag(conn, data)
    if pipeline != "compare":
        return simple
    try:
        advanced = await run_investigative_qa_v1(conn, data, prepared=prepared)
        simple["comparison"] = {
            "advanced_status": advanced.get("status"),
            "advanced_hits": len(advanced.get("hits", [])),
            "advanced_primary_evidence": len(
                advanced.get("primary_evidence_ids", [])
            ),
            "advanced_duration_ms": advanced.get("execution", {}).get(
                "duration_ms"
            ),
        }
    except Exception as exc:
        simple["comparison"] = {
            "advanced_status": "failed",
            "warning": f"advanced_enrichment_failed:{type(exc).__name__}",
        }
        simple["warnings"].append(
            "La interpretación avanzada no estuvo disponible; "
            "la respuesta simple se conservó."
        )
    return simple


@post("/library/investigative-qa/v1", status_code=200, guards=[require_auth])
async def investigative_qa_v1(request: Request, data: QaRequest) -> dict:
    """Run simple grounded RAG by default; preserve advanced compatibility phases."""
    payload = await get_current_user_payload(request)
    user_id = str(payload.get("sub") or "")
    if not user_id:
        raise NotAuthorizedException("Invalid authenticated subject")

    conversation_id = data.conversation.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise HTTPException(status_code=400, detail="Invalid conversation")

    if data.phase == "interpret":
        try:
            prepared, response = await interpret_only(data)
            if data.supersedes_interpretation_id:
                await INTERPRETATION_STORE.supersede(
                    data.supersedes_interpretation_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )
            record = await INTERPRETATION_STORE.create(
                user_id=user_id,
                conversation_id=conversation_id,
                original_query=data.question,
                structured=prepared.structured.model_dump(),
                named_topic=(
                    prepared.named_topic.model_dump()
                    if prepared.named_topic is not None
                    else None
                ),
                interpretation_warnings=list(prepared.warnings),
                display_interpretation=response["display_interpretation"],
                query_understanding=response["query_understanding"],
            )
            response.update({
                "interpretation_id": record.interpretation_id,
                "conversation_id": record.conversation_id,
                "expires_at": record.expires_at,
            })
            return response
        except InterpretationStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Query interpretation failed") from exc

    if data.phase == "analyze":
        if not data.interpretation_id:
            raise HTTPException(status_code=400, detail="interpretation_id is required")
        try:
            record, owns_execution = await INTERPRETATION_STORE.begin_analysis(
                data.interpretation_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if not owns_execution:
                return await INTERPRETATION_STORE.wait_for_result(record)

            authoritative = data.model_copy(update={
                "question": record.original_query,
                "conversation": {
                    **data.conversation,
                    "conversation_id": record.conversation_id,
                },
            })
            prepared = PreparedQuery(
                structured=QueryInterpretation.model_validate(record.structured),
                named_topic=(
                    NamedTopicResolution.model_validate(record.named_topic)
                    if record.named_topic is not None
                    else None
                ),
                warnings=tuple(record.interpretation_warnings),
                preprocessing={},
                glossary_duration_ms=0,
            )
            pool = await get_pg_pool(request)
            pipeline = data.pipeline or RESEARCH_PIPELINE
            async with transaction(pool) as conn:
                result = await _run_research_pipeline(
                    conn,
                    authoritative,
                    pipeline=pipeline,
                    prepared=prepared,
                )
            result.update({
                "phase": "analysis",
                "interpretation_id": record.interpretation_id,
                "approved_interpretation": {
                    "original_query": record.original_query,
                    "display_interpretation": record.display_interpretation,
                    "query_understanding": record.query_understanding,
                    "status": "analyzed",
                },
            })
            await INTERPRETATION_STORE.finish(record, result)
            return result
        except InterpretationStateError as exc:
            status = 410 if str(exc) == "interpretation_expired" else 409
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            if "record" in locals() and "owns_execution" in locals() and owns_execution:
                await INTERPRETATION_STORE.fail(record, "analysis_failed")
            raise HTTPException(status_code=500, detail="Investigative QA failed") from exc

    pipeline = data.pipeline or RESEARCH_PIPELINE
    pool = await get_pg_pool(request)
    try:
        async with transaction(pool) as conn:
            return await _run_research_pipeline(
                conn,
                data,
                pipeline=pipeline,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Investigative QA failed") from exc


@post("/library/relation-qa", status_code=200, guards=[require_auth])
async def relation_qa(
    request: Request,
    data: RelationQARequest,
) -> RelationQAResponse:
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthorizedException("Invalid authenticated subject") from exc
    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=user_id, knowledge_scope_code=data.knowledge_scope_code,
            )
            return await run_relation_qa(conn, data, scope, allow_debug=payload.get("role") == "admin")
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Relation QA failed") from exc


@post("/library/book-qa", status_code=200, guards=[require_auth])
async def book_qa(
    request: Request,
    data: BookQARequest,
) -> BookQAResponse:
    """Book QA V2 SQL-only — grounded in library_pages_v2."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthorizedException("Invalid authenticated subject") from exc
    try:
        async with transaction(pool) as conn:
            return await run_book_qa(
                conn=conn,
                question=data.question,
                run_id=data.run_id,
                document_id=data.document_id,
                scope_code=data.scope_code,
                top_k=data.top_k,
                options=data.options.model_dump() if data.options else {},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Book QA failed") from exc


# ── Book QA V2 Discovery ───────────────────────────────────────────────────


@get("/library/book-qa/runs", status_code=200, guards=[require_auth])
async def book_qa_runs(
    request: Request,
    scope_code: str | None = None,
    document_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> BookQARunsResponse:
    """List Book QA V2 runs."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthorizedException("Invalid authenticated subject") from exc
    try:
        async with transaction(pool) as conn:
            runs = await list_book_qa_runs(
                conn,
                scope_code=scope_code,
                document_id=document_id,
                status_filter=status,
                limit=min(limit, 100),
            )
            return BookQARunsResponse(runs=runs, count=len(runs))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Book QA runs failed") from exc


@get("/library/book-qa/runs/latest", status_code=200, guards=[require_auth])
async def book_qa_runs_latest(
    request: Request,
    scope_code: str | None = None,
    document_id: str | None = None,
    pipeline_version: str | None = None,
) -> BookQALatestRunResponse:
    """Get latest usable Book QA V2 run."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthorizedException("Invalid authenticated subject") from exc
    try:
        async with transaction(pool) as conn:
            run = await get_latest_book_qa_run(
                conn,
                scope_code=scope_code,
                document_id=document_id,
                pipeline_version=pipeline_version,
            )
            if not run:
                return BookQALatestRunResponse(warnings=["no_book_qa_v2_run_found"])
            return BookQALatestRunResponse(run=run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Book QA latest run failed") from exc


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
                conn, user_id=user_id, knowledge_scope_code=data.collection,
            )
            knowledge_scope_code = scope.knowledge_scope_code
            if data.mode == "hybrid":
                raw_results = await search_chunks_hybrid(
                    conn, knowledge_scope_code=knowledge_scope_code,
                    query=data.query, top_k=data.top_k, language=data.language,
                )
            else:
                raw_results = await search_chunks_text(
                    conn, knowledge_scope_code=knowledge_scope_code,
                    query=data.query, top_k=data.top_k, mode=data.mode, language=data.language,
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
        query=data.query, collection=knowledge_scope_code,
        mode=data.mode, language=data.language, total=len(results), results=results,
    )
