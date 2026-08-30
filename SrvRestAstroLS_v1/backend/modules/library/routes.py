"""Library HTTP routes."""

from __future__ import annotations

import asyncio
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
from modules.library.content_manager import (
    cancel_job,
    create_job,
    get_content_summary,
    get_diagnostic,
    get_job,
    get_publish_candidate,
    list_content_documents,
    list_jobs,
    retry_job,
    publish_document,
    validate_and_store_upload,
    MAX_UPLOAD_BYTES,
)
from modules.library.content_manager_schemas import (
    ContentSummary,
    CreateJobRequest,
    DocumentListResponse,
    IngestionDiagnostic,
    JobListResponse,
    JobResponse,
    PublishResponse,
    UploadResponse,
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
from modules.library.page_first_gateway import MilvusAttemptIndex
from globalVar import (
    CONTENT_MANAGER_E2E_COLLECTION,
    CONTENT_MANAGER_E2E_SCOPE,
    MILVUS_COLLECTION_BRESLOV,
    RESEARCH_PIPELINE,
)


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


# ── Content Manager V1 ────────────────────────────────────────────────────


def _content_scope_kwargs(scope: object) -> dict[str, str]:
    return {
        "organization_id": str(scope.organization_id),
        "workspace_id": str(scope.workspace_id),
        "project_id": str(scope.project_id),
    }


def _content_collection(scope_code: str) -> str:
    if scope_code == CONTENT_MANAGER_E2E_SCOPE:
        return CONTENT_MANAGER_E2E_COLLECTION
    return MILVUS_COLLECTION_BRESLOV


@post("/admin/content/uploads", status_code=201, guards=[require_auth])
async def content_manager_upload(
    request: Request, knowledge_scope_code: str = "breslov_primary",
) -> UploadResponse:
    """Validate and register a PDF upload. Admin-only."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_id = payload.get("sub", "")
    user_role = payload.get("role", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    form = await request.form()
    uploaded_file = form.get("file")
    if not uploaded_file or not hasattr(uploaded_file, "read"):
        raise HTTPException(status_code=400, detail="Se requiere un archivo PDF")

    file_content = await uploaded_file.read(MAX_UPLOAD_BYTES + 1)
    original_filename = getattr(uploaded_file, "filename", "upload.pdf")
    declared_mime_type = getattr(uploaded_file, "content_type", None)

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            result = await validate_and_store_upload(
                conn, file_content=file_content, original_filename=original_filename,
                declared_mime_type=declared_mime_type,
                actor_user_id=user_id, knowledge_scope_id=str(scope.id),
                **_content_scope_kwargs(scope),
            )
        return result
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al validar el upload") from exc


@post("/admin/content/jobs", status_code=201, guards=[require_auth])
async def content_manager_create_job(request: Request, data: CreateJobRequest) -> JobResponse:
    """Create an ingestion job from a validated upload. Admin-only."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_id = payload.get("sub", "")
    user_role = payload.get("role", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=data.knowledge_scope_code,
            )
            job = await create_job(
                conn, data, actor_user_id=user_id, knowledge_scope_id=str(scope.id),
                collection_code=_content_collection(scope.knowledge_scope_code),
                **_content_scope_kwargs(scope),
            )
        return job
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al crear el job") from exc


@get("/admin/content/jobs", status_code=200, guards=[require_auth])
async def content_manager_list_jobs(
    request: Request, knowledge_scope_code: str = "breslov_primary",
) -> JobListResponse:
    """List recent ingestion jobs. Admin-only."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_role = payload.get("role", "")
    user_id = payload.get("sub", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            return await list_jobs(conn, **_content_scope_kwargs(scope))
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al listar jobs") from exc


@get("/admin/content/jobs/{job_id:str}", status_code=200, guards=[require_auth])
async def content_manager_get_job(
    request: Request, job_id: str, knowledge_scope_code: str = "breslov_primary",
) -> JobResponse:
    """Get a single job's status. Admin-only."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_role = payload.get("role", "")
    user_id = payload.get("sub", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            job = await get_job(conn, job_id, **_content_scope_kwargs(scope))
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        return job
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al obtener el job") from exc


@post("/admin/content/jobs/{job_id:str}/retry", status_code=200, guards=[require_auth])
async def content_manager_retry_job(
    request: Request, job_id: str, knowledge_scope_code: str = "breslov_primary",
) -> JobResponse:
    """Retry a failed job. Admin-only."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_id = payload.get("sub", "")
    user_role = payload.get("role", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            job = await retry_job(
                conn, job_id, actor_user_id=user_id, **_content_scope_kwargs(scope),
            )
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        return job
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al reintentar el job") from exc


@post("/admin/content/jobs/{job_id:str}/cancel", status_code=200, guards=[require_auth])
async def content_manager_cancel_job(
    request: Request, job_id: str, knowledge_scope_code: str = "breslov_primary",
) -> JobResponse:
    """Cancel a pending job. Admin-only."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_role = payload.get("role", "")
    user_id = payload.get("sub", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            job = await cancel_job(
                conn, job_id, actor_user_id=user_id, **_content_scope_kwargs(scope),
            )
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        return job
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al cancelar el job") from exc


@get("/admin/content/jobs/{job_id:str}/diagnostic", status_code=200, guards=[require_auth])
async def content_manager_diagnostic(
    request: Request, job_id: str, knowledge_scope_code: str = "breslov_primary",
) -> IngestionDiagnostic:
    """Get the diagnostic report for a job. Admin-only."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_role = payload.get("role", "")
    user_id = payload.get("sub", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            diag = await get_diagnostic(conn, job_id, **_content_scope_kwargs(scope))
        if not diag:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        return diag
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al obtener el diagnóstico") from exc


@post("/admin/content/jobs/{job_id:str}/publish", status_code=200, guards=[require_auth])
async def content_manager_publish_job(
    request: Request, job_id: str, knowledge_scope_code: str = "breslov_primary",
) -> PublishResponse:
    """Publish a reconciled primary candidate after an exact Milvus recheck."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_id = payload.get("sub", "")
    if payload.get("role", "") not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            candidate = await get_publish_candidate(
                conn, job_id, **_content_scope_kwargs(scope),
            )
        if not candidate:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        found_vectors = await asyncio.to_thread(
            MilvusAttemptIndex(candidate["collection_code"]).list_ids,
            candidate["vector_ids"],
        )
        async with transaction(pool) as conn:
            return await publish_document(
                conn, candidate, actor_user_id=user_id, found_vectors=found_vectors,
            )
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al publicar el documento") from exc


# ── Document-Centric Administrative Views ──────────────────────────────────


@get("/admin/content/summary", status_code=200, guards=[require_auth])
async def content_manager_summary(
    request: Request,
    knowledge_scope_code: str = "breslov_primary",
    include_test_data: bool = False,
) -> ContentSummary:
    """Aggregated status summary for the administrative library dashboard."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_role = payload.get("role", "")
    user_id = payload.get("sub", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            return await get_content_summary(
                conn,
                **_content_scope_kwargs(scope),
                include_test_data=include_test_data,
            )
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al obtener el resumen") from exc


@get("/admin/content/documents", status_code=200, guards=[require_auth])
async def content_manager_documents(
    request: Request,
    knowledge_scope_code: str = "breslov_primary",
    include_test_data: bool = False,
    status: str | None = None,
    language: str | None = None,
    work_family: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DocumentListResponse:
    """Document-centric listing for the administrative library dashboard."""
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_role = payload.get("role", "")
    user_id = payload.get("sub", "")

    if user_role not in ("admin", "editor"):
        raise PermissionDeniedException("Se requiere rol admin o editor")

    try:
        async with transaction(pool) as conn:
            scope = await get_authorized_scope_by_code(
                conn, user_id=UUID(user_id), knowledge_scope_code=knowledge_scope_code,
            )
            return await list_content_documents(
                conn,
                **_content_scope_kwargs(scope),
                include_test_data=include_test_data,
                status_filter=status,
                language_filter=language,
                work_family_filter=work_family,
                search=search,
                limit=limit,
                offset=offset,
            )
    except ScopeAccessDeniedError as exc:
        raise PermissionDeniedException("Knowledge scope is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al listar documentos") from exc
