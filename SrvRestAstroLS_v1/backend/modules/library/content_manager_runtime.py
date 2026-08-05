"""Runtime wiring for the durable Content Manager worker."""

from __future__ import annotations

import json
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from globalVar import (
    CONTENT_MANAGER_E2E_SCOPE,
    CONTENT_MANAGER_WORKER_LEASE_SECONDS,
)
from infrastructure.postgres.transaction import transaction
from modules.library.content_manager_cleanup import ManifestCleanupService
from modules.library.content_manager_repository import (
    ClaimedJob,
    claim_next_job,
    heartbeat_claim,
    recover_expired_claims,
    transition_claimed_job,
)
from modules.library.content_manager_schemas import IngestionStage
from modules.library.content_manager_worker import PipelineResult, WorkerStore


class PsycopgWorkerStore(WorkerStore):
    def __init__(self, pool: AsyncConnectionPool, *, allowed_scope_code: str = CONTENT_MANAGER_E2E_SCOPE) -> None:
        self.pool = pool
        self.allowed_scope_code = allowed_scope_code

    async def recover_expired(self, worker_id: str) -> dict[str, int]:
        async with transaction(self.pool) as conn:
            return await recover_expired_claims(conn, recovery_actor=worker_id)

    async def claim(self, worker_id: str) -> ClaimedJob | None:
        async with transaction(self.pool) as conn:
            return await claim_next_job(
                conn, worker_id=worker_id, lease_seconds=CONTENT_MANAGER_WORKER_LEASE_SECONDS,
                allowed_scope_code=self.allowed_scope_code,
            )

    async def transition(self, job, current, target, reason, progress_percent) -> None:
        async with transaction(self.pool) as conn:
            await transition_claimed_job(
                conn, job_id=job.job_id, worker_id=job.worker_id, current=current,
                target=target, attempt_number=job.attempt_number, reason=reason,
                progress_percent=progress_percent,
            )

    async def heartbeat(self, job: ClaimedJob) -> bool:
        async with transaction(self.pool) as conn:
            return await heartbeat_claim(
                conn, job_id=job.job_id, worker_id=job.worker_id,
                lease_seconds=CONTENT_MANAGER_WORKER_LEASE_SECONDS,
            )

    async def attach_result(self, job: ClaimedJob, result: PipelineResult) -> None:
        diagnostic = {
            "document_id": str(result.document_id), "job_id": str(job.job_id),
            "attempt_number": job.attempt_number, "document_status": "test_candidate",
            "job_status": "validating_result", "pipeline_version": job.pipeline_version,
            "pdf_pages": result.page_count, "canonical_pages": result.page_count,
            "textual_pages": result.textual_page_count, "empty_pages": result.empty_page_count,
            "headings": result.heading_count, "footnotes": result.footnote_count,
            "printed_references": result.printed_reference_count,
            "chunks": len(result.chunk_ids), "embeddings": len(result.embedding_ids),
            "milvus_vectors": len(result.vector_ids), "warnings": list(result.warnings),
            "errors": [], "cleanup_status": "not_required",
            "scope": self.allowed_scope_code, "collection_code": job.collection_code,
            "reconciliation": result.diagnostics or {},
        }
        async with transaction(self.pool) as conn:
            await conn.execute(
                """UPDATE content_manager_jobs SET document_id=%s,diagnostic=%s::jsonb,
                   warning_codes=%s::jsonb,technical_details=%s::jsonb WHERE id=%s""",
                (result.document_id, json.dumps(diagnostic), json.dumps(list(result.warnings)),
                 json.dumps({"pipeline_version": job.pipeline_version,
                             "attempt_number": job.attempt_number,
                             "collection_code": job.collection_code}), job.job_id),
            )

    async def record_failure(self, job: ClaimedJob, stage: IngestionStage, error_code: str) -> None:
        async with transaction(self.pool) as conn:
            await conn.execute(
                """UPDATE content_manager_jobs SET error_code=%s,error_message=%s,
                   recovery_status='failed_recoverable',cleanup_status='pending' WHERE id=%s""",
                (error_code, f"La etapa {stage.value} no pudo completarse.", job.job_id),
            )
            await conn.execute(
                """UPDATE content_manager_job_attempts SET failure_stage=%s,error_code=%s,
                   error_detail='sanitized_pipeline_failure' WHERE job_id=%s AND attempt_number=%s""",
                (stage.value, error_code, job.job_id, job.attempt_number),
            )
            await conn.execute(
                """UPDATE library_documents SET status='ingestion_failed',updated_at=now()
                   WHERE id=(SELECT document_id FROM content_manager_jobs WHERE id=%s)
                     AND status='draft'""", (job.job_id,),
            )
        # If no manifest exists the failure happened before writes. Otherwise
        # exact compensation runs; the validated upload remains for a safe retry.
        try:
            await ManifestCleanupService(self.pool).cleanup(
                job.job_id, job.attempt_number, remove_temporary=False,
            )
        except ValueError:
            async with transaction(self.pool) as conn:
                await conn.execute(
                    """UPDATE content_manager_jobs SET cleanup_status='not_required',
                       recovery_status='failed_recoverable' WHERE id=%s""", (job.job_id,),
                )
