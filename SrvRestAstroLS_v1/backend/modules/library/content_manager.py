"""Content Manager V1 — controlled PDF upload & ingestion orchestration."""

from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from globalVar import (
    CONTENT_MANAGER_MAX_PDF_PAGES,
    CONTENT_MANAGER_MAX_UPLOAD_BYTES,
    CONTENT_MANAGER_PIPELINE_VERSION,
    CONTENT_MANAGER_UPLOAD_TTL_HOURS,
    EMBEDDINGS_MODEL_ALIAS,
)
from modules.library.content_manager_schemas import (
    CreateJobRequest,
    DuplicateClassification,
    ExistingDocumentInfo,
    IngestionDiagnostic,
    IngestionProfile,
    IngestionStage,
    JobListItem,
    JobListResponse,
    JobProgress,
    JobResponse,
    UploadLimits,
    UploadResponse,
    UploadValidationError,
    UploadValidationStatus,
)

# ── Typed configuration ─────────────────────────────────────────────────

MAX_UPLOAD_BYTES = CONTENT_MANAGER_MAX_UPLOAD_BYTES
MAX_PDF_PAGES = CONTENT_MANAGER_MAX_PDF_PAGES
UPLOAD_TTL_HOURS = CONTENT_MANAGER_UPLOAD_TTL_HOURS
TEMP_DIR = pathlib.Path(tempfile.gettempdir()) / "tebaai_content_manager"


# ── Stage display mapping ─────────────────────────────────────────────────

STAGE_LABELS: dict[str, str] = {
    IngestionStage.UPLOADED.value: "Archivo recibido",
    IngestionStage.VALIDATING.value: "Validando el archivo",
    IngestionStage.VALIDATION_FAILED.value: "Validación fallida",
    IngestionStage.READY_TO_INGEST.value: "Listo para procesar",
    IngestionStage.QUEUED.value: "En cola de procesamiento",
    IngestionStage.CLAIMED.value: "Procesamiento asignado",
    IngestionStage.EXTRACTING.value: "Extrayendo las páginas",
    IngestionStage.NORMALIZING.value: "Normalizando el contenido",
    IngestionStage.PERSISTING_PAGES.value: "Organizando las secciones",
    IngestionStage.BUILDING_CHUNKS.value: "Preparando la búsqueda",
    IngestionStage.EMBEDDING.value: "Generando el índice",
    IngestionStage.INDEXING.value: "Indexando el contenido",
    IngestionStage.VALIDATING_RESULT.value: "Verificando el resultado",
    IngestionStage.COMPLETED.value: "Documento procesado",
    IngestionStage.COMPLETED_WITH_WARNINGS.value: "Documento procesado con observaciones",
    IngestionStage.FAILED.value: "No se pudo completar el procesamiento",
    IngestionStage.CANCELLED.value: "Procesamiento cancelado",
}

TERMINAL_STAGES = {
    IngestionStage.COMPLETED,
    IngestionStage.COMPLETED_WITH_WARNINGS,
    IngestionStage.FAILED,
    IngestionStage.CANCELLED,
}


# ── Helpers ───────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _utcnow().isoformat()


def _short_hash(sha256: str) -> str:
    return sha256[:16] + "…"


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        loaded = json.loads(value)
        return [str(item) for item in loaded] if isinstance(loaded, list) else []
    return []


def _compute_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_pdf_pages(file_path: str) -> int:
    """Count PDF pages using a lightweight header parse (no full render)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return 0
    try:
        doc = fitz.open(file_path)
        count = doc.page_count
        doc.close()
        return count
    except Exception:
        return 0


def _validate_magic_bytes(file_path: str) -> bool:
    """Check that the file starts with a valid PDF signature."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
        return header.startswith(b"%PDF-")
    except OSError:
        return False


def _sanitise_filename(original: str) -> str:
    """Produce a safe internal filename, preserving the original for display."""
    safe = "".join(c for c in original if c.isalnum() or c in "._- ")[:200]
    return safe or "upload.pdf"


# ── Upload operations ─────────────────────────────────────────────────────


async def validate_and_store_upload(
    conn: AsyncConnection,
    *,
    file_content: bytes,
    original_filename: str,
    actor_user_id: str,
    organization_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    knowledge_scope_id: str | None = None,
) -> UploadResponse:
    """Validate a PDF upload, store it temporarily, detect duplicates."""
    warnings: list[str] = []
    errors: list[UploadValidationError] = []

    # -- Size check --
    if len(file_content) == 0:
        raise ValueError("El archivo está vacío.")
    if len(file_content) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"El archivo supera el tamaño permitido de {MAX_UPLOAD_BYTES // (1024*1024)} MB."
        )

    # -- Write to temp --
    safe_name = _sanitise_filename(original_filename)
    upload_id = _uuid.uuid4()
    temp_dir = TEMP_DIR / str(upload_id)
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / safe_name
    temp_path.write_bytes(file_content)

    try:
        # -- Magic bytes --
        if not _validate_magic_bytes(str(temp_path)):
            raise ValueError("El archivo no es un PDF válido (firma inválida).")

        # -- SHA-256 --
        file_sha256 = _compute_sha256(str(temp_path))

        # -- Page count --
        page_count = _count_pdf_pages(str(temp_path))
        if page_count == 0:
            warnings.append("No se pudo detectar la cantidad de páginas.")
        elif page_count > MAX_PDF_PAGES:
            raise ValueError(
                f"El PDF supera el límite de {MAX_PDF_PAGES} páginas "
                f"({page_count} detectadas)."
            )

        # -- Duplicate detection --
        existing = await _find_existing_document(
            conn, file_sha256, original_filename, knowledge_scope_id=knowledge_scope_id,
        )
        duplicate_status = DuplicateClassification.NEW_DOCUMENT
        existing_doc = None
        if existing:
            if existing["source_sha256"] == file_sha256:
                duplicate_status = DuplicateClassification.EXACT_DUPLICATE
            else:
                duplicate_status = DuplicateClassification.POSSIBLE_REVISED_EDITION
            existing_doc = ExistingDocumentInfo(
                document_id=existing["id"],
                title=existing["title"],
                status=existing["status"],
                created_at=existing.get("created_at"),
                source_sha256_short=_short_hash(existing["source_sha256"] or ""),
            )
            warnings.append(
                "Ya existe un documento con características similares. "
                "Verificá el detalle antes de continuar."
            )

        # -- Persist upload record --
        validation_status = UploadValidationStatus.VALID
        expires_at = _utcnow() + timedelta(hours=UPLOAD_TTL_HOURS)

        await conn.execute(
            """
            INSERT INTO content_manager_uploads
                (id, organization_id, workspace_id, project_id, knowledge_scope_id, actor_user_id,
                 filename, original_filename, size_bytes, sha256, mime_type,
                 page_count, validation_status, validation_errors,
                 duplicate_status, existing_document_id,
                 temp_path, warnings, limits, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                upload_id, organization_id, workspace_id, project_id, knowledge_scope_id, actor_user_id,
                safe_name, original_filename, len(file_content), file_sha256, "application/pdf",
                page_count, validation_status.value, json.dumps([e.model_dump() for e in errors]),
                duplicate_status.value, existing_doc.document_id if existing_doc else None,
                str(temp_path), json.dumps(warnings),
                json.dumps(UploadLimits(max_upload_bytes=MAX_UPLOAD_BYTES, max_pdf_pages=MAX_PDF_PAGES).model_dump()),
                _utcnow(), expires_at,
            ),
        )

        return UploadResponse(
            upload_id=upload_id,
            filename=original_filename,
            size_bytes=len(file_content),
            sha256=file_sha256,
            mime_type="application/pdf",
            page_count=page_count,
            validation_status=validation_status,
            duplicate_status=duplicate_status,
            existing_document=existing_doc,
            warnings=warnings,
            limits=UploadLimits(max_upload_bytes=MAX_UPLOAD_BYTES, max_pdf_pages=MAX_PDF_PAGES),
        )

    except Exception:
        # Cleanup temp on failure
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        raise


async def _find_existing_document(
    conn: AsyncConnection, sha256: str, filename: str, *, knowledge_scope_id: str | None,
) -> dict[str, Any] | None:
    """Find an existing document by SHA-256 or filename."""
    cur = await conn.execute(
        """
        SELECT id, title, status, source_sha256, created_at
        FROM library_documents
        WHERE knowledge_scope_id = %(scope)s
          AND (source_sha256 = %(sha)s OR source_filename = %(fn)s)
        ORDER BY
            CASE WHEN source_sha256 = %(sha)s THEN 0 ELSE 1 END,
            created_at DESC
        LIMIT 1
        """,
        {"sha": sha256, "fn": filename, "scope": knowledge_scope_id},
    )
    rows = await cur.fetchall()
    return dict(rows[0]) if rows else None


async def get_upload(
    conn: AsyncConnection,
    upload_id: str,
    *,
    organization_id: str,
    workspace_id: str,
    project_id: str,
) -> dict[str, Any] | None:
    cur = await conn.execute(
        """SELECT * FROM content_manager_uploads
           WHERE id = %s AND organization_id = %s AND workspace_id = %s AND project_id = %s""",
        (upload_id, organization_id, workspace_id, project_id),
    )
    rows = await cur.fetchall()
    return dict(rows[0]) if rows else None


# ── Job operations ────────────────────────────────────────────────────────


async def create_job(
    conn: AsyncConnection,
    req: CreateJobRequest,
    *,
    actor_user_id: str,
    organization_id: str,
    workspace_id: str,
    project_id: str,
    knowledge_scope_id: str,
    collection_code: str,
) -> JobResponse:
    """Atomically enqueue one job for a validated, tenant-scoped upload."""
    upload = await get_upload(
        conn, str(req.upload_id), organization_id=organization_id,
        workspace_id=workspace_id, project_id=project_id,
    )
    if not upload:
        raise ValueError("Upload no encontrado en el contexto activo.")
    if upload["validation_status"] != UploadValidationStatus.VALID.value:
        raise ValueError("El upload no superó la validación.")
    if upload["duplicate_status"] == DuplicateClassification.EXACT_DUPLICATE.value:
        raise ValueError("El archivo es un duplicado exacto y no puede reingerirse.")
    if req.requested_status != "test_candidate":
        raise ValueError(
            "El Gestor de Contenidos solo puede crear candidatos para revisión; "
            "no puede publicar ni promover documentos."
        )

    profile = req.ingestion_profile.value if isinstance(req.ingestion_profile, IngestionProfile) else req.ingestion_profile
    raw_key = ":".join((knowledge_scope_id, upload["sha256"], CONTENT_MANAGER_PIPELINE_VERSION, str(profile)))
    idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    job_id = _uuid.uuid4()
    stage_states = _initial_stage_states()
    stage_states.update({"validating": "done", "ready_to_ingest": "done", "queued": "active"})

    cur = await conn.execute(
        """
        INSERT INTO content_manager_jobs
            (id, upload_id, organization_id, workspace_id, project_id, knowledge_scope_id,
             actor_user_id, title, language, work_family, administrative_notes,
             ingestion_profile, requested_status, status, current_stage, stage_states,
             pipeline_version, embedding_model, collection_code, idempotency_key,
             created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued','queued',%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (idempotency_key)
          WHERE status NOT IN ('failed', 'cancelled', 'validation_failed')
        DO NOTHING
        RETURNING id
        """,
        (
            job_id, req.upload_id, organization_id, workspace_id, project_id,
            knowledge_scope_id, actor_user_id, req.title, req.language,
            req.work_family, req.administrative_notes, profile, req.requested_status,
            json.dumps(stage_states), CONTENT_MANAGER_PIPELINE_VERSION,
            EMBEDDINGS_MODEL_ALIAS, collection_code, idempotency_key, _utcnow(), _utcnow(),
        ),
    )
    inserted = await cur.fetchone()
    if not inserted:
        cur = await conn.execute(
            """SELECT id FROM content_manager_jobs
               WHERE idempotency_key=%s
                 AND status NOT IN ('failed','cancelled','validation_failed')""",
            (idempotency_key,),
        )
        inserted = await cur.fetchone()
    resolved_job_id = str(inserted[0] if isinstance(inserted, tuple) else inserted["id"])
    if resolved_job_id == str(job_id):
        now = _utcnow()
        await conn.execute(
            """
            INSERT INTO content_manager_job_transitions
                (job_id, attempt_number, from_status, to_status, stage, actor_id, reason, occurred_at)
            VALUES
                (%s,1,'uploaded','validating','validating',%s,'validated_upload',%s),
                (%s,1,'validating','ready_to_ingest','ready_to_ingest',%s,'validation_passed',%s),
                (%s,1,'ready_to_ingest','queued','queued',%s,'editor_confirmed',%s)
            """,
            (job_id, actor_user_id, now, job_id, actor_user_id, now, job_id, actor_user_id, now),
        )
    return await get_job(
        conn, resolved_job_id, organization_id=organization_id,
        workspace_id=workspace_id, project_id=project_id,
    )  # type: ignore[return-value]


def _initial_stage_states() -> dict[str, str]:
    stages = [
        IngestionStage.VALIDATING, IngestionStage.READY_TO_INGEST, IngestionStage.QUEUED,
        IngestionStage.CLAIMED, IngestionStage.EXTRACTING, IngestionStage.NORMALIZING,
        IngestionStage.PERSISTING_PAGES, IngestionStage.BUILDING_CHUNKS,
        IngestionStage.EMBEDDING, IngestionStage.INDEXING, IngestionStage.VALIDATING_RESULT,
    ]
    return {s.value: "pending" for s in stages}


async def get_job(
    conn: AsyncConnection,
    job_id: str,
    *,
    organization_id: str,
    workspace_id: str,
    project_id: str,
) -> JobResponse | None:
    cur = await conn.execute(
        """SELECT * FROM content_manager_jobs
           WHERE id=%s AND organization_id=%s AND workspace_id=%s AND project_id=%s""",
        (job_id, organization_id, workspace_id, project_id),
    )
    rows = await cur.fetchall()
    if not rows:
        return None
    row = dict(rows[0])
    return _job_response(row)


async def list_jobs(
    conn: AsyncConnection,
    *,
    organization_id: str,
    workspace_id: str,
    project_id: str,
    limit: int = 50,
) -> JobListResponse:
    where = "WHERE j.organization_id=%(org)s AND j.workspace_id=%(ws)s AND j.project_id=%(project)s"
    params: dict[str, Any] = {
        "limit": limit, "org": organization_id, "ws": workspace_id, "project": project_id,
    }

    cur = await conn.execute(
        f"""
        SELECT j.*, u.original_filename, u.sha256
        FROM content_manager_jobs j
        LEFT JOIN content_manager_uploads u ON u.id = j.upload_id
        {where}
        ORDER BY j.created_at DESC
        LIMIT %(limit)s
        """,
        params,
    )
    rows = await cur.fetchall()
    items = []
    status_counts: dict[str, int] = {}
    for r in rows:
        r_dict = dict(r) if not isinstance(r, dict) else r
        items.append(JobListItem(
            job_id=r_dict["id"],
            upload_id=r_dict["upload_id"],
            document_id=r_dict.get("document_id"),
            title=r_dict["title"],
            language=r_dict["language"],
            status=IngestionStage(r_dict["status"]),
            current_stage=IngestionStage(r_dict.get("current_stage") or r_dict["status"]),
            created_at=r_dict.get("created_at"),
            attempt_number=r_dict.get("attempt_number", 1),
            filename=r_dict.get("original_filename"),
            sha256_short=_short_hash(r_dict.get("sha256") or "") if r_dict.get("sha256") else None,
        ))
        status = r_dict["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    return JobListResponse(jobs=items, summary=status_counts)


async def cancel_job(
    conn: AsyncConnection, job_id: str, *, actor_user_id: str,
    organization_id: str, workspace_id: str, project_id: str,
) -> JobResponse | None:
    job = await get_job(conn, job_id, organization_id=organization_id,
                        workspace_id=workspace_id, project_id=project_id)
    if not job:
        return None
    if job.status in TERMINAL_STAGES:
        return job
    if job.status not in {IngestionStage.UPLOADED, IngestionStage.VALIDATING,
                          IngestionStage.READY_TO_INGEST, IngestionStage.QUEUED}:
        raise ValueError(
            f"No se puede cancelar un job en estado '{job.status.value}'. "
            "La cancelación solo es posible antes de iniciar escrituras."
        )
    now = _utcnow()
    cur = await conn.execute(
        """UPDATE content_manager_jobs SET status='cancelled', current_stage='cancelled',
                  finished_at=%s, updated_at=%s
           WHERE id=%s AND organization_id=%s AND workspace_id=%s AND project_id=%s
             AND status=%s""",
        (now, now, job_id, organization_id, workspace_id, project_id, job.status.value),
    )
    if cur.rowcount != 1:
        raise ValueError("El job cambió de estado antes de la cancelación.")
    await conn.execute(
        """INSERT INTO content_manager_job_transitions
           (job_id,attempt_number,from_status,to_status,stage,actor_id,reason,occurred_at)
           VALUES(%s,%s,%s,'cancelled','cancelled',%s,'editor_cancelled',%s)""",
        (job_id, job.attempt_number, job.status.value, actor_user_id, now),
    )
    return await get_job(conn, job_id, organization_id=organization_id,
                         workspace_id=workspace_id, project_id=project_id)


async def retry_job(
    conn: AsyncConnection, job_id: str, *, actor_user_id: str,
    organization_id: str, workspace_id: str, project_id: str,
) -> JobResponse | None:
    cur = await conn.execute(
        """SELECT j.*, u.temp_path, u.expires_at AS upload_expires_at
           FROM content_manager_jobs j JOIN content_manager_uploads u ON u.id=j.upload_id
           WHERE j.id=%s AND j.organization_id=%s AND j.workspace_id=%s AND j.project_id=%s""",
        (job_id, organization_id, workspace_id, project_id),
    )
    row = await cur.fetchone()
    if not row:
        return None
    source = dict(row)
    if source["status"] not in {"failed", "cancelled"}:
        raise ValueError("Solo se puede reintentar un job fallido o cancelado.")
    temp_path = pathlib.Path(source.get("temp_path") or "")
    if not temp_path.is_file() or (source.get("upload_expires_at") and source["upload_expires_at"] <= _utcnow()):
        raise ValueError("reupload_required: el archivo temporal ya no está disponible.")
    if source.get("cleanup_status") in {"pending", "running", "failed"}:
        raise ValueError("El intento anterior requiere cleanup verificado antes del retry.")

    new_job_id = _uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO content_manager_jobs
            (id,upload_id,organization_id,workspace_id,project_id,knowledge_scope_id,
             actor_user_id,title,language,work_family,administrative_notes,ingestion_profile,
             requested_status,status,current_stage,stage_states,attempt_number,
             pipeline_version,document_schema_version,embedding_model,collection_code,
             idempotency_key,created_at,updated_at,recovery_status)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'test_candidate','queued','queued',%s,
               %s,%s,%s,%s,%s,%s,%s,%s,'requeued')
        """,
        (new_job_id, source["upload_id"], organization_id, workspace_id, project_id,
         source["knowledge_scope_id"], actor_user_id, source["title"], source["language"],
         source["work_family"], source["administrative_notes"], source["ingestion_profile"],
         json.dumps(_initial_stage_states()), source["attempt_number"] + 1,
         source["pipeline_version"], source["document_schema_version"], source["embedding_model"],
         source["collection_code"], source["idempotency_key"], _utcnow(), _utcnow()),
    )
    return await get_job(conn, str(new_job_id), organization_id=organization_id,
                         workspace_id=workspace_id, project_id=project_id)


async def get_diagnostic(
    conn: AsyncConnection, job_id: str, *, organization_id: str,
    workspace_id: str, project_id: str,
) -> IngestionDiagnostic | None:
    job_row = await conn.execute(
        """SELECT * FROM content_manager_jobs
           WHERE id=%s AND organization_id=%s AND workspace_id=%s AND project_id=%s""",
        (job_id, organization_id, workspace_id, project_id),
    )
    rows = await job_row.fetchall()
    if not rows:
        return None
    row = dict(rows[0])

    stored = row.get("diagnostic") or {}
    if isinstance(stored, str):
        stored = json.loads(stored)
    reconciliation = stored.get("reconciliation", {}) if isinstance(stored, dict) else {}
    duration = None
    if row.get("started_at") and row.get("finished_at"):
        duration = (row["finished_at"] - row["started_at"]).total_seconds()
    diag = IngestionDiagnostic(
        job_id=_uuid.UUID(job_id), document_id=row.get("document_id"),
        attempt_number=row.get("attempt_number", 1), job_status=row.get("status"),
        document_status=stored.get("document_status") if isinstance(stored, dict) else None,
        pipeline_version=row.get("pipeline_version"), scope=stored.get("scope") if isinstance(stored, dict) else None,
        collection_code=row.get("collection_code"), pdf_pages=stored.get("pdf_pages") if isinstance(stored, dict) else None,
        textual_pages=stored.get("textual_pages") if isinstance(stored, dict) else None,
        empty_pages=stored.get("empty_pages") if isinstance(stored, dict) else None,
        headings=stored.get("headings") if isinstance(stored, dict) else None,
        footnotes=stored.get("footnotes") if isinstance(stored, dict) else None,
        printed_references=stored.get("printed_references") if isinstance(stored, dict) else None,
        embeddings=stored.get("embeddings") if isinstance(stored, dict) else None,
        milvus_entity_count=stored.get("milvus_vectors") if isinstance(stored, dict) else None,
        pg_missing=len(reconciliation.get("pg_missing", [])),
        milvus_missing=len(reconciliation.get("missing", [])),
        milvus_orphan=len(reconciliation.get("orphans", [])),
        duplicates=len(reconciliation.get("duplicates", [])),
        warnings=stored.get("warnings", []) if isinstance(stored, dict) else [],
        errors=stored.get("errors", []) if isinstance(stored, dict) else [],
        cleanup_result=row.get("cleanup_status"), duration_seconds=duration,
    )

    if row.get("document_id"):
        doc_cur = await conn.execute(
            """
            SELECT
                (SELECT count(*) FROM library_pages_v2 WHERE document_id = %(did)s) AS pages,
                (SELECT count(*) FROM library_document_chunks WHERE document_id = %(did)s) AS chunks,
                (SELECT count(*) FROM library_chunk_embeddings WHERE chunk_id IN
                    (SELECT id FROM library_document_chunks WHERE document_id = %(did)s)) AS embeddings,
                (SELECT status FROM library_documents WHERE id = %(did)s) AS document_status
            """,
            {"did": row["document_id"]},
        )
        doc_info = await doc_cur.fetchone()
        if doc_info:
            diag = diag.model_copy(update={
                "canonical_pages": doc_info.get("pages"),
                "chunks": doc_info.get("chunks"),
                "pg_embedding_count": doc_info.get("embeddings"),
                "document_status": doc_info.get("document_status") or diag.document_status,
                "page_integrity": "match" if doc_info.get("pages") == diag.pdf_pages else "mismatch",
            })

    diag = diag.model_copy(update={
        "technical_details": {
            "upload_id": str(row.get("upload_id", "")),
            "attempt_number": row.get("attempt_number", 1),
            "created_at": str(row.get("created_at", "")),
            "finished_at": str(row.get("finished_at", "")),
        },
    })
    return diag


# ── Helpers ───────────────────────────────────────────────────────────────


def _job_response(row: dict[str, Any]) -> JobResponse:
    stage = IngestionStage(row["status"])
    stage_states = row.get("stage_states") or {}
    if isinstance(stage_states, str):
        stage_states = json.loads(stage_states)

    return JobResponse(
        job_id=row["id"],
        upload_id=row["upload_id"],
        document_id=row.get("document_id"),
        title=row["title"],
        language=row["language"],
        status=stage,
        progress=JobProgress(
            current_stage=IngestionStage(row.get("current_stage") or row["status"]),
            progress_percent=float(row.get("progress_percent", 0)),
            stage_display=STAGE_LABELS.get(row.get("current_stage") or row["status"], row["status"]),
            is_terminal=stage in TERMINAL_STAGES,
            stage_states=stage_states if isinstance(stage_states, dict) else {},
        ),
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        warning_codes=_json_list(row.get("warning_codes")),
        attempt_number=row.get("attempt_number", 1),
        ingestion_profile=IngestionProfile(row.get("ingestion_profile", "auto")),
        created_at=row.get("created_at"),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        worker_id=row.get("claimed_by"),
        claimed_at=row.get("claimed_at"),
        lease_expires_at=row.get("lease_expires_at"),
        heartbeat_at=row.get("heartbeat_at"),
        cleanup_status=row.get("cleanup_status"),
        recovery_status=row.get("recovery_status"),
        pipeline_version=row.get("pipeline_version"),
        idempotency_key=row.get("idempotency_key"),
    )


async def _load_stage_states(conn: AsyncConnection, job_id: str) -> dict[str, str]:
    cur = await conn.execute(
        "SELECT stage_states FROM content_manager_jobs WHERE id = %s", (job_id,)
    )
    row = await cur.fetchone()
    if not row:
        return {}
    raw = row[0] if isinstance(row, tuple) else row.get("stage_states", "{}")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw if isinstance(raw, dict) else {}


async def _load_timings(conn: AsyncConnection, job_id: str) -> dict[str, float]:
    cur = await conn.execute(
        "SELECT stage_timings FROM content_manager_jobs WHERE id = %s", (job_id,)
    )
    row = await cur.fetchone()
    if not row:
        return {}
    raw = row[0] if isinstance(row, tuple) else row.get("stage_timings", "{}")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw if isinstance(raw, dict) else {}


# ── Document-Centric Administrative Views ──────────────────────────────────

_PROCESSING_STATUSES: frozenset[str] = frozenset({
    "uploaded", "validating", "ready_to_ingest", "queued", "claimed",
    "extracting", "normalizing", "persisting_pages", "building_chunks",
    "embedding", "indexing", "validating_result",
})


def _e2e_clause(alias: str, include_test_data: bool) -> str:
    """Return the SQL predicate excluding the E2E scope, or empty string."""
    if include_test_data:
        return ""
    return f"AND ({alias}.knowledge_scope_code IS NULL OR {alias}.knowledge_scope_code != 'breslov_e2e')"


def _operational_state(
    *,
    document_status: str | None,
    job_status: str | None,
    is_processing: bool,
) -> str:
    """Map document + latest-job state onto an editorial operational state."""
    if is_processing or (job_status and job_status in _PROCESSING_STATUSES):
        return "processing"
    if job_status in ("failed", "validation_failed") or document_status == "ingestion_failed":
        return "failed"
    if job_status == "completed_with_warnings":
        return "needs_review"
    if job_status == "cancelled":
        return "cancelled"
    if document_status == "test_candidate":
        return "needs_review"
    if document_status == "ready":
        return "idle"
    return "idle"


async def get_content_summary(
    conn: AsyncConnection,
    *,
    organization_id: str,
    workspace_id: str,
    project_id: str,
    include_test_data: bool = False,
) -> ContentSummary:
    """Aggregated status counts for the administrative library dashboard."""
    from modules.library.content_manager_schemas import ContentSummary

    params: dict[str, Any] = {
        "org": organization_id, "ws": workspace_id, "project": project_id,
        "processing_statuses": list(_PROCESSING_STATUSES),
    }
    e2e_docs = _e2e_clause("ks", include_test_data)
    e2e_jobs = _e2e_clause("jks", include_test_data)

    # Document statuses (library_documents is the primary entity).
    doc_cur = await conn.execute(
        f"""
        SELECT
            COUNT(*) AS total_documents,
            COUNT(*) FILTER (WHERE d.status = 'ready') AS ready,
            COUNT(*) FILTER (WHERE d.status = 'test_candidate') AS test_candidate,
            COUNT(*) FILTER (WHERE d.status = 'ingestion_failed') AS ingestion_failed,
            COUNT(*) FILTER (WHERE d.status = 'draft') AS draft
        FROM library_documents d
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        WHERE d.organization_id = %(org)s
          AND d.workspace_id = %(ws)s
          AND d.project_id = %(project)s
          {e2e_docs}
        """,
        params,
    )
    doc_row = await doc_cur.fetchone()
    doc = dict(doc_row) if doc_row else {}

    # Active jobs (processing) — includes jobs without a document_id yet.
    proc_cur = await conn.execute(
        f"""
        SELECT COUNT(DISTINCT COALESCE(j.document_id::text, j.id::text)) AS processing
        FROM content_manager_jobs j
        LEFT JOIN knowledge_scopes jks ON jks.id = j.knowledge_scope_id
        WHERE j.organization_id = %(org)s
          AND j.workspace_id = %(ws)s
          AND j.project_id = %(project)s
          AND j.status = ANY(%(processing_statuses)s)
          {e2e_jobs}
        """,
        params,
    )
    proc_row = await proc_cur.fetchone()
    processing = int(dict(proc_row).get("processing", 0)) if proc_row else 0

    # Latest job per document, for warnings/failed attribution.
    latest_cur = await conn.execute(
        f"""
        WITH latest AS (
            SELECT DISTINCT ON (j.document_id) j.document_id, j.status
            FROM content_manager_jobs j
            LEFT JOIN knowledge_scopes jks ON jks.id = j.knowledge_scope_id
            WHERE j.document_id IS NOT NULL
              AND j.organization_id = %(org)s
              AND j.workspace_id = %(ws)s
              AND j.project_id = %(project)s
              {e2e_jobs}
            ORDER BY j.document_id, j.created_at DESC
        )
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed_with_warnings') AS with_warnings,
            COUNT(*) FILTER (WHERE status IN ('failed','validation_failed')) AS job_failed
        FROM latest
        """,
        params,
    )
    latest_row = await latest_cur.fetchone()
    latest = dict(latest_row) if latest_row else {}

    # Language counts from documents.
    lang_cur = await conn.execute(
        f"""
        SELECT COALESCE(d.language, 'unknown') AS lang, COUNT(*) AS cnt
        FROM library_documents d
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        WHERE d.organization_id = %(org)s
          AND d.workspace_id = %(ws)s
          AND d.project_id = %(project)s
          {e2e_docs}
        GROUP BY 1
        """,
        params,
    )
    lang_rows = await lang_cur.fetchall()
    languages: dict[str, int] = {}
    for lr in lang_rows:
        lr_dict = dict(lr) if not isinstance(lr, dict) else lr
        languages[str(lr_dict.get("lang", "unknown"))] = int(lr_dict.get("cnt", 0))

    total_documents = int(doc.get("total_documents", 0))
    failed = int(doc.get("ingestion_failed", 0)) + int(latest.get("job_failed", 0))

    return ContentSummary(
        total_documents=total_documents,
        ready=int(doc.get("ready", 0)),
        test_candidate=int(doc.get("test_candidate", 0)),
        processing=processing,
        with_warnings=int(latest.get("with_warnings", 0)),
        failed=failed,
        languages=languages,
    )


async def list_content_documents(
    conn: AsyncConnection,
    *,
    organization_id: str,
    workspace_id: str,
    project_id: str,
    include_test_data: bool = False,
    status_filter: str | None = None,
    language_filter: str | None = None,
    work_family_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DocumentListResponse:
    """Document-centric listing for the administrative library dashboard.

    Primary entity: library_documents (real documents in the productive
    scope). Each row joins its latest Content Manager job (if any) for
    activity and warnings. Active jobs that have not yet produced a document
    appear as processing rows without a document_id.
    """
    from modules.library.content_manager_schemas import (
        ContentSummary,
        DocumentListItem,
        DocumentListResponse,
    )

    params: dict[str, Any] = {
        "org": organization_id, "ws": workspace_id, "project": project_id,
        "limit": limit, "offset": offset,
        "processing_statuses": list(_PROCESSING_STATUSES),
    }
    e2e_docs = _e2e_clause("ks", include_test_data)
    e2e_jobs = _e2e_clause("jks", include_test_data)

    doc_filters = ""
    if status_filter:
        doc_filters += " AND d.status = %(status_filter)s"
        params["status_filter"] = status_filter
    if language_filter:
        doc_filters += " AND d.language = %(lang)s"
        params["lang"] = language_filter
    if work_family_filter:
        doc_filters += (
            " AND (d.bibliographic_metadata->'canonical_identity_v1'"
            "->'work_identity'->>'family_label') = %(wf)s"
        )
        params["wf"] = work_family_filter
    if search:
        doc_filters += " AND d.title ILIKE %(search)s"
        params["search"] = f"%{search}%"

    query = f"""
        WITH latest_job AS (
            SELECT DISTINCT ON (j.document_id)
                j.document_id,
                j.id AS job_id,
                j.status AS job_status,
                j.current_stage AS job_stage,
                j.updated_at AS job_updated_at,
                j.attempt_number,
                u.original_filename AS job_filename
            FROM content_manager_jobs j
            LEFT JOIN content_manager_uploads u ON u.id = j.upload_id
            LEFT JOIN knowledge_scopes jks ON jks.id = j.knowledge_scope_id
            WHERE j.document_id IS NOT NULL
              AND j.organization_id = %(org)s
              AND j.workspace_id = %(ws)s
              AND j.project_id = %(project)s
              {e2e_jobs}
            ORDER BY j.document_id, j.created_at DESC
        ),
        active_jobs AS (
            SELECT DISTINCT j.document_id
            FROM content_manager_jobs j
            LEFT JOIN knowledge_scopes jks ON jks.id = j.knowledge_scope_id
            WHERE j.organization_id = %(org)s
              AND j.workspace_id = %(ws)s
              AND j.project_id = %(project)s
              AND j.status = ANY(%(processing_statuses)s)
              {e2e_jobs}
        ),
        items AS (
            SELECT
                d.id AS document_id,
                d.title,
                d.language,
                d.status AS document_status,
                d.source_filename AS filename,
                d.edition,
                d.created_at,
                d.updated_at,
                (d.bibliographic_metadata->'canonical_identity_v1'
                    ->'work_identity'->>'family_label') AS work_family,
                (d.bibliographic_metadata->'canonical_identity_v1'
                    ->'work_identity'->>'canonical_work_label') AS canonical_work,
                (SELECT count(*) FROM library_pages_v2 p WHERE p.document_id = d.id) AS page_count,
                lj.job_id AS latest_job_id,
                lj.job_status AS latest_job_status,
                lj.job_stage AS latest_job_stage,
                lj.job_filename,
                (aj.document_id IS NOT NULL) AS is_processing,
                ks.knowledge_scope_code
            FROM library_documents d
            JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
            LEFT JOIN latest_job lj ON lj.document_id = d.id
            LEFT JOIN active_jobs aj ON aj.document_id = d.id
            WHERE d.organization_id = %(org)s
              AND d.workspace_id = %(ws)s
              AND d.project_id = %(project)s
              {e2e_docs}
              {doc_filters}

            UNION ALL

            SELECT
                NULL AS document_id,
                j.title,
                j.language,
                NULL AS document_status,
                u.original_filename AS filename,
                NULL AS edition,
                j.created_at,
                j.updated_at,
                j.work_family,
                NULL AS canonical_work,
                NULL AS page_count,
                j.id AS latest_job_id,
                j.status AS latest_job_status,
                j.current_stage AS latest_job_stage,
                u.original_filename AS job_filename,
                (j.status = ANY(%(processing_statuses)s)) AS is_processing,
                jks.knowledge_scope_code
            FROM content_manager_jobs j
            LEFT JOIN content_manager_uploads u ON u.id = j.upload_id
            LEFT JOIN knowledge_scopes jks ON jks.id = j.knowledge_scope_id
            WHERE j.organization_id = %(org)s
              AND j.workspace_id = %(ws)s
              AND j.project_id = %(project)s
              AND (
                  j.document_id IS NULL
                  OR NOT EXISTS (
                      SELECT 1 FROM library_documents d2 WHERE d2.id = j.document_id
                  )
              )
              {e2e_jobs}
        )
        SELECT *
        FROM items
        ORDER BY
            CASE
                WHEN is_processing THEN 0
                WHEN document_status = 'ingestion_failed' OR latest_job_status IN ('failed','validation_failed') THEN 1
                WHEN latest_job_status = 'completed_with_warnings' THEN 2
                WHEN document_status = 'test_candidate' THEN 3
                ELSE 4
            END,
            COALESCE(updated_at, created_at) DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """

    cur = await conn.execute(query, params)
    rows = await cur.fetchall()

    items: list[DocumentListItem] = []
    for row in rows:
        r = dict(row) if not isinstance(row, dict) else row
        doc_status = r.get("document_status") or ""
        job_status = str(r.get("latest_job_status") or "") or None
        is_processing = bool(r.get("is_processing"))

        items.append(DocumentListItem(
            document_id=r.get("document_id"),
            title=str(r.get("title") or ""),
            work_family=r.get("work_family"),
            canonical_work=r.get("canonical_work"),
            language=str(r.get("language") or "unknown"),
            page_count=r.get("page_count"),
            document_status=doc_status or None,
            operational_state=_operational_state(
                document_status=doc_status or None,
                job_status=job_status,
                is_processing=is_processing,
            ),
            last_activity_at=r.get("updated_at") or r.get("created_at"),
            has_warnings=job_status == "completed_with_warnings",
            latest_job_id=r.get("latest_job_id"),
            latest_job_status=job_status,
            latest_job_stage=r.get("latest_job_stage"),
            filename=r.get("filename") or r.get("job_filename") or r.get("source_filename"),
            is_test_data=r.get("knowledge_scope_code") == "breslov_e2e",
        ))

    summary = await get_content_summary(
        conn,
        organization_id=organization_id,
        workspace_id=workspace_id,
        project_id=project_id,
        include_test_data=include_test_data,
    )

    return DocumentListResponse(documents=items, summary=summary)
