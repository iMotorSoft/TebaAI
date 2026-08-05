from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from modules.library.content_manager_repository import ClaimedJob, ContentTenantContext
from modules.library.content_manager_schemas import IngestionStage
from modules.library.content_manager_state import (
    ALLOWED_TRANSITIONS,
    InvalidIngestionTransition,
    assert_transition,
    can_cancel,
)
from modules.library.content_manager_worker import (
    ContentManagerWorker,
    LostWorkerLease,
    PipelineResult,
)


def make_job() -> ClaimedJob:
    tenant = ContentTenantContext(uuid4(), uuid4(), uuid4(), uuid4())
    return ClaimedJob(
        job_id=uuid4(), upload_id=uuid4(), attempt_number=1,
        worker_id="worker-a", lease_expires_at=datetime.now(timezone.utc),
        status=IngestionStage.CLAIMED, title="Fixture", language="es",
        ingestion_profile="auto", pipeline_version="content_page_first_v1",
        embedding_model="openai_text_embedding_3_small",
        collection_code="tebaai_content_manager_e2e_v1", tenant=tenant,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [(current, target) for current, targets in ALLOWED_TRANSITIONS.items() for target in targets],
)
def test_every_declared_transition_is_valid(current: IngestionStage, target: IngestionStage) -> None:
    assert_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (IngestionStage.QUEUED, IngestionStage.EXTRACTING),
        (IngestionStage.CLAIMED, IngestionStage.COMPLETED),
        (IngestionStage.EMBEDDING, IngestionStage.COMPLETED),
        (IngestionStage.COMPLETED, IngestionStage.QUEUED),
        (IngestionStage.FAILED, IngestionStage.EXTRACTING),
    ],
)
def test_invalid_or_skipped_transition_is_rejected(current: IngestionStage, target: IngestionStage) -> None:
    with pytest.raises(InvalidIngestionTransition):
        assert_transition(current, target)


def test_only_pre_write_states_are_cancellable() -> None:
    assert can_cancel(IngestionStage.QUEUED)
    assert can_cancel(IngestionStage.READY_TO_INGEST)
    assert not can_cancel(IngestionStage.CLAIMED)
    assert not can_cancel(IngestionStage.EMBEDDING)
    assert not can_cancel(IngestionStage.INDEXING)


class FakeStore:
    def __init__(self, jobs: list[ClaimedJob], *, heartbeat_ok: bool = True) -> None:
        self.jobs = jobs
        self.heartbeat_ok = heartbeat_ok
        self.claimed: set[UUID] = set()
        self.transitions: list[tuple[IngestionStage, IngestionStage]] = []
        self.failures: list[tuple[IngestionStage, str]] = []
        self.results: list[PipelineResult] = []
        self.recoveries = 0

    async def recover_expired(self, worker_id: str) -> dict[str, int]:
        self.recoveries += 1
        return {"requeued": 0, "manual_review_required": 0}

    async def claim(self, worker_id: str) -> ClaimedJob | None:
        for job in self.jobs:
            if job.job_id not in self.claimed:
                self.claimed.add(job.job_id)
                return job
        return None

    async def transition(self, job, current, target, reason, progress_percent):
        assert_transition(current, target)
        self.transitions.append((current, target))

    async def heartbeat(self, job) -> bool:
        return self.heartbeat_ok

    async def attach_result(self, job, result) -> None:
        self.results.append(result)

    async def record_failure(self, job, stage, error_code) -> None:
        self.failures.append((stage, error_code))


class SuccessfulPipeline:
    def __init__(self, *, warnings: tuple[str, ...] = ()) -> None:
        self.calls = 0
        self.warnings = warnings

    async def run(self, job, *, advance, heartbeat):
        self.calls += 1
        stages = [
            IngestionStage.EXTRACTING,
            IngestionStage.NORMALIZING,
            IngestionStage.PERSISTING_PAGES,
            IngestionStage.BUILDING_CHUNKS,
            IngestionStage.EMBEDDING,
            IngestionStage.INDEXING,
            IngestionStage.VALIDATING_RESULT,
        ]
        for index, stage in enumerate(stages, start=1):
            await heartbeat()
            await advance(stage, "stage_completed", index * 12.5)
        return PipelineResult(document_id=uuid4(), warnings=self.warnings)


class PipelineStageError(RuntimeError):
    error_code = "embedding_unavailable"


class FailingPipeline:
    async def run(self, job, *, advance, heartbeat):
        await advance(IngestionStage.EXTRACTING, "started", 5)
        await advance(IngestionStage.NORMALIZING, "extracted", 15)
        await advance(IngestionStage.PERSISTING_PAGES, "normalized", 30)
        await advance(IngestionStage.BUILDING_CHUNKS, "pages_persisted", 45)
        await advance(IngestionStage.EMBEDDING, "chunks_built", 60)
        raise PipelineStageError("embedding failed")


@pytest.mark.asyncio
async def test_worker_claims_and_invokes_pipeline_once() -> None:
    store = FakeStore([make_job()])
    pipeline = SuccessfulPipeline()
    worker = ContentManagerWorker(worker_id="worker-a", store=store, pipeline=pipeline)
    assert await worker.run_once() is True
    assert pipeline.calls == 1
    assert len(store.claimed) == 1
    assert store.transitions[-1][1] is IngestionStage.COMPLETED


@pytest.mark.asyncio
async def test_two_workers_cannot_claim_same_job() -> None:
    store = FakeStore([make_job()])
    first = ContentManagerWorker(worker_id="worker-a", store=store, pipeline=SuccessfulPipeline())
    second_pipeline = SuccessfulPipeline()
    second = ContentManagerWorker(worker_id="worker-b", store=store, pipeline=second_pipeline)
    assert await first.run_once() is True
    assert await second.run_once() is False
    assert second_pipeline.calls == 0


@pytest.mark.asyncio
async def test_warnings_end_in_completed_with_warnings() -> None:
    store = FakeStore([make_job()])
    worker = ContentManagerWorker(
        worker_id="worker-a", store=store,
        pipeline=SuccessfulPipeline(warnings=("empty_page",)),
    )
    await worker.run_once()
    assert store.transitions[-1][1] is IngestionStage.COMPLETED_WITH_WARNINGS


@pytest.mark.asyncio
async def test_partial_stage_failure_is_diagnostic_and_terminal() -> None:
    store = FakeStore([make_job()])
    worker = ContentManagerWorker(worker_id="worker-a", store=store, pipeline=FailingPipeline())
    await worker.run_once()
    assert store.failures == [(IngestionStage.EMBEDDING, "embedding_unavailable")]
    assert store.transitions[-1] == (IngestionStage.EMBEDDING, IngestionStage.FAILED)


@pytest.mark.asyncio
async def test_lost_lease_stops_without_false_failure_transition() -> None:
    store = FakeStore([make_job()], heartbeat_ok=False)
    worker = ContentManagerWorker(worker_id="worker-a", store=store, pipeline=SuccessfulPipeline())
    with pytest.raises(LostWorkerLease):
        await worker.run_once()
    assert store.failures == []
    assert store.transitions == []


@pytest.mark.asyncio
async def test_empty_queue_is_recoverable_and_does_not_run_pipeline() -> None:
    store = FakeStore([])
    pipeline = SuccessfulPipeline()
    worker = ContentManagerWorker(worker_id="worker-a", store=store, pipeline=pipeline)
    assert await worker.run_once() is False
    assert store.recoveries == 1
    assert pipeline.calls == 0
