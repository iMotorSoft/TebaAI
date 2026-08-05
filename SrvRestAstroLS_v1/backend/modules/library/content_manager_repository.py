"""PostgreSQL persistence for durable Content Manager orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from modules.library.content_manager_schemas import IngestionStage
from modules.library.content_manager_state import assert_transition


@dataclass(frozen=True)
class ContentTenantContext:
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    knowledge_scope_id: UUID


@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    upload_id: UUID
    attempt_number: int
    worker_id: str
    lease_expires_at: datetime
    status: IngestionStage
    title: str
    language: str
    ingestion_profile: str
    pipeline_version: str
    embedding_model: str
    collection_code: str
    tenant: ContentTenantContext


async def claim_next_job(
    conn: AsyncConnection,
    *,
    worker_id: str,
    lease_seconds: int,
) -> ClaimedJob | None:
    """Atomically claim one queued job; concurrent workers skip the locked row."""
    now = datetime.now(timezone.utc)
    lease_expires = now + timedelta(seconds=lease_seconds)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            WITH candidate AS (
                SELECT id
                FROM content_manager_jobs
                WHERE status = 'queued'
                  AND (lease_expires_at IS NULL OR lease_expires_at <= %(now)s)
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE content_manager_jobs j
            SET status = 'claimed', current_stage = 'claimed',
                claimed_by = %(worker)s, claimed_at = %(now)s,
                heartbeat_at = %(now)s, lease_expires_at = %(lease)s,
                started_at = COALESCE(started_at, %(now)s), updated_at = %(now)s
            FROM candidate
            WHERE j.id = candidate.id
            RETURNING j.*
            """,
            {"now": now, "worker": worker_id, "lease": lease_expires},
        )
        row = await cur.fetchone()
        if not row:
            return None
        await cur.execute(
            """
            INSERT INTO content_manager_job_attempts
                (job_id, attempt_number, worker_id, status, started_at)
            VALUES (%(job)s, %(attempt)s, %(worker)s, 'running', %(now)s)
            ON CONFLICT (job_id, attempt_number) DO UPDATE
              SET worker_id = EXCLUDED.worker_id, status = 'running',
                  started_at = COALESCE(content_manager_job_attempts.started_at, EXCLUDED.started_at)
            """,
            {"job": row["id"], "attempt": row["attempt_number"], "worker": worker_id, "now": now},
        )
        await cur.execute(
            """
            INSERT INTO content_manager_job_transitions
                (job_id, attempt_number, from_status, to_status, stage, actor_id, reason)
            VALUES (%s, %s, 'queued', 'claimed', 'claimed', %s, 'exclusive_claim')
            """,
            (row["id"], row["attempt_number"], worker_id),
        )
    return _claimed_job(row, worker_id, lease_expires)


async def heartbeat_claim(
    conn: AsyncConnection,
    *,
    job_id: UUID,
    worker_id: str,
    lease_seconds: int,
) -> bool:
    now = datetime.now(timezone.utc)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE content_manager_jobs
            SET heartbeat_at = %(now)s,
                lease_expires_at = %(lease)s,
                updated_at = %(now)s
            WHERE id = %(job)s AND claimed_by = %(worker)s
              AND status NOT IN ('completed','completed_with_warnings','failed','cancelled')
            """,
            {
                "now": now,
                "lease": now + timedelta(seconds=lease_seconds),
                "job": job_id,
                "worker": worker_id,
            },
        )
        return cur.rowcount == 1


async def transition_claimed_job(
    conn: AsyncConnection,
    *,
    job_id: UUID,
    worker_id: str,
    current: IngestionStage,
    target: IngestionStage,
    attempt_number: int,
    reason: str,
    progress_percent: float,
) -> None:
    """Validate and compare-and-swap a worker-owned transition."""
    assert_transition(current, target)
    now = datetime.now(timezone.utc)
    terminal = target in {
        IngestionStage.COMPLETED,
        IngestionStage.COMPLETED_WITH_WARNINGS,
        IngestionStage.FAILED,
        IngestionStage.CANCELLED,
    }
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE content_manager_jobs
            SET status = %(target)s, current_stage = %(target)s,
                progress_percent = %(progress)s, updated_at = %(now)s,
                finished_at = CASE WHEN %(terminal)s THEN %(now)s ELSE finished_at END,
                lease_expires_at = CASE WHEN %(terminal)s THEN NULL ELSE lease_expires_at END
            WHERE id = %(job)s AND status = %(current)s AND claimed_by = %(worker)s
            """,
            {
                "target": target.value,
                "progress": progress_percent,
                "now": now,
                "terminal": terminal,
                "job": job_id,
                "current": current.value,
                "worker": worker_id,
            },
        )
        if cur.rowcount != 1:
            raise RuntimeError("Job transition lost ownership or compare-and-swap failed")
        await cur.execute(
            """
            INSERT INTO content_manager_job_transitions
                (job_id, attempt_number, from_status, to_status, stage, actor_id, reason, occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (job_id, attempt_number, current.value, target.value, target.value, worker_id, reason, now),
        )
        if terminal:
            await cur.execute(
                """
                UPDATE content_manager_job_attempts
                SET status = %s, finished_at = %s
                WHERE job_id = %s AND attempt_number = %s
                """,
                (target.value, now, job_id, attempt_number),
            )


async def recover_expired_claims(conn: AsyncConnection, *, recovery_actor: str) -> dict[str, int]:
    """Requeue untouched claims; fail stale jobs that own persisted resources."""
    now = datetime.now(timezone.utc)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT j.id, j.status, j.attempt_number,
                   EXISTS (
                     SELECT 1 FROM content_manager_ingestion_manifests m
                     JOIN content_manager_manifest_resources r ON r.manifest_id = m.id
                     WHERE m.job_id = j.id AND m.attempt_number = j.attempt_number
                       AND r.was_preexisting = false AND r.cleaned_at IS NULL
                   ) AS has_partial_writes
            FROM content_manager_jobs j
            WHERE j.lease_expires_at < %(now)s
              AND j.status NOT IN ('completed','completed_with_warnings','failed','cancelled')
            FOR UPDATE SKIP LOCKED
            """,
            {"now": now},
        )
        rows = await cur.fetchall()
        counts = {"requeued": 0, "manual_review_required": 0}
        for row in rows:
            target = "failed" if row["has_partial_writes"] else "queued"
            recovery = "manual_review_required" if row["has_partial_writes"] else "requeued"
            await cur.execute(
                """
                UPDATE content_manager_jobs
                SET status=%s, current_stage=%s, recovery_status=%s,
                    claimed_by=NULL, claimed_at=NULL, heartbeat_at=NULL,
                    lease_expires_at=NULL, updated_at=%s,
                    error_code=CASE WHEN %s='failed' THEN 'stale_partial_attempt' ELSE error_code END
                WHERE id=%s
                """,
                (target, target, recovery, now, target, row["id"]),
            )
            await cur.execute(
                """
                INSERT INTO content_manager_job_transitions
                    (job_id, attempt_number, from_status, to_status, stage, actor_id, reason, occurred_at)
                VALUES (%s,%s,%s,%s,%s,%s,'expired_lease_recovery',%s)
                """,
                (row["id"], row["attempt_number"], row["status"], target, target, recovery_actor, now),
            )
            counts[recovery] += 1
        return counts


def _claimed_job(row: dict[str, Any], worker_id: str, lease_expires: datetime) -> ClaimedJob:
    return ClaimedJob(
        job_id=row["id"], upload_id=row["upload_id"], attempt_number=row["attempt_number"],
        worker_id=worker_id, lease_expires_at=lease_expires, status=IngestionStage.CLAIMED,
        title=row["title"], language=row["language"], ingestion_profile=row["ingestion_profile"],
        pipeline_version=row["pipeline_version"], embedding_model=row["embedding_model"],
        collection_code=row["collection_code"],
        tenant=ContentTenantContext(
            organization_id=row["organization_id"], workspace_id=row["workspace_id"],
            project_id=row["project_id"], knowledge_scope_id=row["knowledge_scope_id"],
        ),
    )
