"""Content Manager V1 — controlled PDF upload & ingestion orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import tempfile
import time
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row

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

# ── Configuration (overridable via env / globalVar) ──────────────────────

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_PDF_PAGES = 2000
UPLOAD_TTL_HOURS = 24
TEMP_DIR = pathlib.Path(tempfile.gettempdir()) / "tebaai_content_manager"


# ── Stage display mapping ─────────────────────────────────────────────────

STAGE_LABELS: dict[str, str] = {
    IngestionStage.UPLOADED.value: "Archivo recibido",
    IngestionStage.VALIDATING.value: "Validando el archivo",
    IngestionStage.VALIDATION_FAILED.value: "Validación fallida",
    IngestionStage.READY_TO_INGEST.value: "Listo para procesar",
    IngestionStage.QUEUED.value: "En cola de procesamiento",
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
        existing = await _find_existing_document(conn, file_sha256, original_filename)
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
                (id, organization_id, workspace_id, project_id, actor_user_id,
                 filename, original_filename, size_bytes, sha256, mime_type,
                 page_count, validation_status, validation_errors,
                 duplicate_status, existing_document_id,
                 temp_path, warnings, limits, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                upload_id, organization_id, workspace_id, project_id, actor_user_id,
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
    conn: AsyncConnection, sha256: str, filename: str
) -> dict[str, Any] | None:
    """Find an existing document by SHA-256 or filename."""
    cur = await conn.execute(
        """
        SELECT id, title, status, source_sha256, created_at
        FROM library_documents
        WHERE source_sha256 = %(sha)s
           OR source_filename = %(fn)s
        ORDER BY
            CASE WHEN source_sha256 = %(sha)s THEN 0 ELSE 1 END,
            created_at DESC
        LIMIT 1
        """,
        {"sha": sha256, "fn": filename},
    )
    rows = await cur.fetchall()
    return dict(rows[0]) if rows else None


async def get_upload(conn: AsyncConnection, upload_id: str) -> dict[str, Any] | None:
    cur = await conn.execute(
        "SELECT * FROM content_manager_uploads WHERE id = %s", (upload_id,)
    )
    rows = await cur.fetchall()
    return dict(rows[0]) if rows else None


# ── Job operations ────────────────────────────────────────────────────────


async def create_job(
    conn: AsyncConnection,
    req: CreateJobRequest,
    *,
    actor_user_id: str,
    organization_id: str | None = None,
) -> JobResponse:
    """Create a new ingestion job from a validated upload."""
    upload = await get_upload(conn, str(req.upload_id))
    if not upload:
        raise ValueError("Upload no encontrado.")
    if upload["validation_status"] != UploadValidationStatus.VALID.value:
        raise ValueError("El upload no superó la validación.")

    # Reject ready status
    if req.requested_status == "ready":
        raise ValueError(
            "No se puede solicitar estado 'ready' desde el Gestor de Contenidos. "
            "El documento debe ser promovido mediante un proceso de revisión separado."
        )

    # Check for existing job with same upload (idempotency)
    cur = await conn.execute(
        """
        SELECT id FROM content_manager_jobs
        WHERE upload_id = %s AND status NOT IN ('failed', 'cancelled')
        ORDER BY created_at DESC LIMIT 1
        """,
        (req.upload_id,),
    )
    existing = await cur.fetchone()
    if existing:
        job_id = str(existing[0]) if isinstance(existing, tuple) else str(existing["id"])
        return await get_job(conn, job_id)  # type: ignore[return-value]

    job_id = _uuid.uuid4()
    profile = req.ingestion_profile.value if isinstance(req.ingestion_profile, IngestionProfile) else req.ingestion_profile

    await conn.execute(
        """
        INSERT INTO content_manager_jobs
            (id, upload_id, organization_id, actor_user_id, title, language,
             work_family, administrative_notes, ingestion_profile,
             requested_status, status, current_stage, stage_states, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            job_id, req.upload_id, organization_id, actor_user_id,
            req.title, req.language, req.work_family, req.administrative_notes,
            profile, req.requested_status,
            IngestionStage.VALIDATING.value, IngestionStage.VALIDATING.value,
            json.dumps(_initial_stage_states()), _utcnow(), _utcnow(),
        ),
    )

    return await get_job(conn, str(job_id))  # type: ignore[return-value]


def _initial_stage_states() -> dict[str, str]:
    stages = [
        IngestionStage.VALIDATING, IngestionStage.READY_TO_INGEST, IngestionStage.QUEUED,
        IngestionStage.EXTRACTING, IngestionStage.NORMALIZING, IngestionStage.PERSISTING_PAGES,
        IngestionStage.BUILDING_CHUNKS, IngestionStage.EMBEDDING, IngestionStage.INDEXING,
        IngestionStage.VALIDATING_RESULT,
    ]
    return {s.value: "pending" for s in stages}


async def get_job(conn: AsyncConnection, job_id: str) -> JobResponse | None:
    cur = await conn.execute(
        "SELECT * FROM content_manager_jobs WHERE id = %s", (job_id,)
    )
    rows = await cur.fetchall()
    if not rows:
        return None
    row = dict(rows[0])
    return _job_response(row)


async def list_jobs(
    conn: AsyncConnection,
    *,
    organization_id: str | None = None,
    limit: int = 50,
) -> JobListResponse:
    where = "WHERE 1=1"
    params: dict[str, Any] = {"limit": limit}
    if organization_id:
        where += " AND organization_id = %(org)s"
        params["org"] = organization_id

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


async def update_job_stage(
    conn: AsyncConnection,
    job_id: str,
    stage: IngestionStage,
    *,
    progress_percent: float | None = None,
    warning_codes: list[str] | None = None,
    document_id: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    stage_timing: float | None = None,
) -> JobResponse | None:
    """Advance a job to a new stage."""
    job = await get_job(conn, job_id)
    if not job:
        return None

    stage_states = _load_stage_states(conn, job_id)
    stage_states[stage.value] = "done" if stage not in TERMINAL_STAGES else (
        "done" if stage in (IngestionStage.COMPLETED, IngestionStage.COMPLETED_WITH_WARNINGS) else "failed"
    )

    now = _utcnow()
    updates: dict[str, Any] = {
        "status": stage.value,
        "current_stage": stage.value,
        "stage_states": json.dumps(stage_states),
        "updated_at": now,
    }
    if progress_percent is not None:
        updates["progress_percent"] = progress_percent
    if document_id:
        updates["document_id"] = document_id
    if error_code:
        updates["error_code"] = error_code
    if error_message:
        updates["error_message"] = error_message
    if warning_codes:
        existing = job.warning_codes or []
        updates["warning_codes"] = json.dumps(list(set(existing + warning_codes)))
    if stage == IngestionStage.QUEUED and not job.started_at:
        updates["started_at"] = now
    if stage in TERMINAL_STAGES:
        updates["finished_at"] = now
    if stage_timing is not None:
        timing = _load_timings(conn, job_id)
        timing[job.current_stage.value if job.current_stage else "unknown"] = stage_timing
        updates["stage_timings"] = json.dumps(timing)

    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    await conn.execute(
        f"UPDATE content_manager_jobs SET {set_clause} WHERE id = %(jid)s",
        {**updates, "jid": job_id},
    )
    return await get_job(conn, job_id)


async def cancel_job(conn: AsyncConnection, job_id: str) -> JobResponse | None:
    job = await get_job(conn, job_id)
    if not job:
        return None
    if job.status in TERMINAL_STAGES:
        return job
    cancellable = {IngestionStage.UPLOADED, IngestionStage.VALIDATING, IngestionStage.READY_TO_INGEST, IngestionStage.QUEUED}
    if job.status not in cancellable:
        raise ValueError(
            f"No se puede cancelar un job en estado '{job.status.value}'. "
            "La cancelación solo es posible antes de iniciar la escritura de datos."
        )
    return await update_job_stage(conn, job_id, IngestionStage.CANCELLED, progress_percent=0.0)


async def retry_job(conn: AsyncConnection, job_id: str, *, actor_user_id: str) -> JobResponse | None:
    job = await get_job(conn, job_id)
    if not job:
        return None
    if job.status not in {IngestionStage.FAILED, IngestionStage.CANCELLED}:
        raise ValueError("Solo se puede reintentar un job fallido o cancelado.")

    upload = await get_upload(conn, str(job.upload_id) if hasattr(job, 'upload_id') else "")
    if not upload:
        raise ValueError("El upload original ya no está disponible. Cargá el archivo nuevamente.")

    new_job_id = _uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO content_manager_jobs
            (id, upload_id, organization_id, actor_user_id, title, language,
             work_family, administrative_notes, ingestion_profile,
             requested_status, status, current_stage, stage_states,
             attempt_number, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            new_job_id, job.upload_id if hasattr(job, 'upload_id') else None, None, actor_user_id,
            job.title, job.language, None, None,
            job.ingestion_profile.value if hasattr(job.ingestion_profile, 'value') else "auto",
            "test_candidate", IngestionStage.QUEUED.value, IngestionStage.QUEUED.value,
            json.dumps(_initial_stage_states()),
            job.attempt_number + 1, _utcnow(), _utcnow(),
        ),
    )
    return await get_job(conn, str(new_job_id))


async def get_diagnostic(conn: AsyncConnection, job_id: str) -> IngestionDiagnostic | None:
    job_row = await conn.execute(
        "SELECT * FROM content_manager_jobs WHERE id = %s", (job_id,)
    )
    rows = await job_row.fetchall()
    if not rows:
        return None
    row = dict(rows[0])

    diag = IngestionDiagnostic(
        job_id=_uuid.UUID(job_id),
        document_id=row.get("document_id"),
    )

    if row.get("document_id"):
        doc_cur = await conn.execute(
            """
            SELECT
                (SELECT count(*) FROM library_pages_v2 WHERE document_id = %(did)s) AS pages,
                (SELECT count(*) FROM library_document_chunks WHERE document_id = %(did)s) AS chunks,
                (SELECT count(*) FROM library_chunk_embeddings WHERE chunk_id IN
                    (SELECT id FROM library_document_chunks WHERE document_id = %(did)s)) AS embeddings
            """,
            {"did": row["document_id"]},
        )
        doc_info = await doc_cur.fetchone()
        if doc_info:
            diag = diag.model_copy(update={
                "canonical_pages": doc_info.get("pages"),
                "chunks": doc_info.get("chunks"),
                "pg_embedding_count": doc_info.get("embeddings"),
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
        warning_codes=json.loads(row.get("warning_codes") or "[]"),
        attempt_number=row.get("attempt_number", 1),
        ingestion_profile=IngestionProfile(row.get("ingestion_profile", "auto")),
        created_at=row.get("created_at"),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
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
