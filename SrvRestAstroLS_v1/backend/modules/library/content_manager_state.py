"""Canonical state and recovery rules for Content Manager ingestion jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from modules.library.content_manager_schemas import IngestionStage


class InvalidIngestionTransition(ValueError):
    """Raised when a job attempts a transition outside the canonical graph."""


ALLOWED_TRANSITIONS: dict[IngestionStage, frozenset[IngestionStage]] = {
    IngestionStage.UPLOADED: frozenset({IngestionStage.VALIDATING, IngestionStage.CANCELLED}),
    IngestionStage.VALIDATING: frozenset({
        IngestionStage.VALIDATION_FAILED,
        IngestionStage.READY_TO_INGEST,
        IngestionStage.FAILED,
        IngestionStage.CANCELLED,
    }),
    IngestionStage.VALIDATION_FAILED: frozenset({IngestionStage.FAILED}),
    IngestionStage.READY_TO_INGEST: frozenset({IngestionStage.QUEUED, IngestionStage.CANCELLED}),
    IngestionStage.QUEUED: frozenset({IngestionStage.CLAIMED, IngestionStage.CANCELLED}),
    IngestionStage.CLAIMED: frozenset({IngestionStage.EXTRACTING, IngestionStage.FAILED}),
    IngestionStage.EXTRACTING: frozenset({IngestionStage.NORMALIZING, IngestionStage.FAILED}),
    IngestionStage.NORMALIZING: frozenset({IngestionStage.PERSISTING_PAGES, IngestionStage.FAILED}),
    IngestionStage.PERSISTING_PAGES: frozenset({IngestionStage.BUILDING_CHUNKS, IngestionStage.FAILED}),
    IngestionStage.BUILDING_CHUNKS: frozenset({IngestionStage.EMBEDDING, IngestionStage.FAILED}),
    IngestionStage.EMBEDDING: frozenset({IngestionStage.INDEXING, IngestionStage.FAILED}),
    IngestionStage.INDEXING: frozenset({IngestionStage.VALIDATING_RESULT, IngestionStage.FAILED}),
    IngestionStage.VALIDATING_RESULT: frozenset({
        IngestionStage.COMPLETED,
        IngestionStage.COMPLETED_WITH_WARNINGS,
        IngestionStage.FAILED,
    }),
    IngestionStage.COMPLETED: frozenset(),
    IngestionStage.COMPLETED_WITH_WARNINGS: frozenset(),
    IngestionStage.FAILED: frozenset(),
    IngestionStage.CANCELLED: frozenset(),
}

CANCELLABLE_STAGES = frozenset({
    IngestionStage.UPLOADED,
    IngestionStage.VALIDATING,
    IngestionStage.READY_TO_INGEST,
    IngestionStage.QUEUED,
})

WRITING_STAGES = frozenset({
    IngestionStage.PERSISTING_PAGES,
    IngestionStage.BUILDING_CHUNKS,
    IngestionStage.EMBEDDING,
    IngestionStage.INDEXING,
    IngestionStage.VALIDATING_RESULT,
})

CLAIMABLE_STAGES = frozenset({IngestionStage.QUEUED})


@dataclass(frozen=True)
class TransitionContext:
    actor_id: str
    attempt_number: int
    reason: str
    occurred_at: datetime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def assert_transition(current: IngestionStage, target: IngestionStage) -> None:
    """Reject invalid, skipped and repeated transitions."""
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidIngestionTransition(
            f"Invalid ingestion transition: {current.value} -> {target.value}"
        )


def can_cancel(stage: IngestionStage) -> bool:
    return stage in CANCELLABLE_STAGES


def is_terminal(stage: IngestionStage) -> bool:
    return not ALLOWED_TRANSITIONS[stage]
