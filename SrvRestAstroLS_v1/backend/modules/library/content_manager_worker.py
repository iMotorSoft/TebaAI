"""Durable Content Manager worker orchestration independent of HTTP requests."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Awaitable, Callable, Protocol
from uuid import UUID

from modules.library.content_manager_repository import ClaimedJob
from modules.library.content_manager_schemas import IngestionStage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    document_id: UUID
    warnings: tuple[str, ...] = ()
    page_ids: tuple[UUID, ...] = ()
    chunk_ids: tuple[UUID, ...] = ()
    embedding_ids: tuple[UUID, ...] = ()
    vector_ids: tuple[str, ...] = ()
    page_count: int = 0
    textual_page_count: int = 0
    empty_page_count: int = 0
    heading_count: int = 0
    footnote_count: int = 0
    printed_reference_count: int = 0
    diagnostics: dict[str, object] | None = None


Advance = Callable[[IngestionStage, str, float], Awaitable[None]]
Heartbeat = Callable[[], Awaitable[None]]


class PageFirstPipeline(Protocol):
    async def run(
        self,
        job: ClaimedJob,
        *,
        advance: Advance,
        heartbeat: Heartbeat,
    ) -> PipelineResult: ...


class WorkerStore(Protocol):
    async def recover_expired(self, worker_id: str) -> dict[str, int]: ...
    async def claim(self, worker_id: str) -> ClaimedJob | None: ...
    async def transition(
        self,
        job: ClaimedJob,
        current: IngestionStage,
        target: IngestionStage,
        reason: str,
        progress_percent: float,
    ) -> None: ...
    async def heartbeat(self, job: ClaimedJob) -> bool: ...
    async def attach_result(self, job: ClaimedJob, result: PipelineResult) -> None: ...
    async def record_failure(self, job: ClaimedJob, stage: IngestionStage, error_code: str) -> None: ...


class LostWorkerLease(RuntimeError):
    pass


class ContentManagerWorker:
    """Claims at most one job and drives its persisted state transitions."""

    def __init__(self, *, worker_id: str, store: WorkerStore, pipeline: PageFirstPipeline) -> None:
        self.worker_id = worker_id
        self.store = store
        self.pipeline = pipeline

    async def run_once(self) -> bool:
        await self.store.recover_expired(self.worker_id)
        job = await self.store.claim(self.worker_id)
        if job is None:
            return False

        current = IngestionStage.CLAIMED

        async def advance(target: IngestionStage, reason: str, progress: float) -> None:
            nonlocal current
            await self.store.transition(job, current, target, reason, progress)
            current = target

        async def heartbeat() -> None:
            if not await self.store.heartbeat(job):
                raise LostWorkerLease(f"Worker {self.worker_id} lost job {job.job_id}")

        try:
            result = await self.pipeline.run(job, advance=advance, heartbeat=heartbeat)
            if current is not IngestionStage.VALIDATING_RESULT:
                raise RuntimeError("Pipeline returned before validating_result")
            await self.store.attach_result(job, result)
            terminal = (
                IngestionStage.COMPLETED_WITH_WARNINGS
                if result.warnings else IngestionStage.COMPLETED
            )
            await advance(terminal, "reconciliation_passed", 100.0)
        except LostWorkerLease:
            raise
        except Exception as exc:
            logger.exception("Content Manager attempt failed at stage %s", current.value)
            error_code = getattr(exc, "error_code", "pipeline_stage_failed")
            await self.store.record_failure(job, current, str(error_code))
            if current not in {
                IngestionStage.COMPLETED,
                IngestionStage.COMPLETED_WITH_WARNINGS,
                IngestionStage.FAILED,
                IngestionStage.CANCELLED,
            }:
                await self.store.transition(job, current, IngestionStage.FAILED, str(error_code), 0.0)
        return True
