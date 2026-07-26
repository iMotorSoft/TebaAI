"""Server-authoritative state for pre-retrieval query confirmation."""

from __future__ import annotations

import asyncio
import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


InterpretationStatus = Literal[
    "awaiting_confirmation",
    "analyzing",
    "completed",
    "superseded",
    "error",
]


class InterpretationStateError(ValueError):
    """Raised when an interpretation cannot be used by the current caller."""


@dataclass
class InterpretationRecord:
    interpretation_id: str
    user_id: str
    conversation_id: str
    original_query: str
    structured: dict[str, Any]
    named_topic: dict[str, Any] | None
    interpretation_warnings: list[str]
    display_interpretation: str
    query_understanding: dict[str, Any]
    created_at: float
    expires_at: float
    status: InterpretationStatus = "awaiting_confirmation"
    result: dict[str, Any] | None = None
    failure: str | None = None
    completed: asyncio.Event = field(default_factory=asyncio.Event)


class InterpretationStore:
    """Bounded in-process registry used by the single-worker TebaAI runtime."""

    def __init__(self, *, ttl_seconds: int = 3600, max_records: int = 1000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_records = max_records
        self._records: dict[str, InterpretationRecord] = {}
        self._lock = asyncio.Lock()

    def _purge(self, now: float) -> None:
        expired = [
            key
            for key, record in self._records.items()
            if record.expires_at <= now and record.status != "analyzing"
        ]
        for key in expired:
            self._records.pop(key, None)
        if len(self._records) < self.max_records:
            return
        oldest = sorted(
            (
                record
                for record in self._records.values()
                if record.status != "analyzing"
            ),
            key=lambda record: record.created_at,
        )
        for record in oldest[: max(1, len(self._records) - self.max_records + 1)]:
            self._records.pop(record.interpretation_id, None)

    async def create(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        original_query: str,
        structured: dict[str, Any],
        named_topic: dict[str, Any] | None,
        interpretation_warnings: list[str],
        display_interpretation: str,
        query_understanding: dict[str, Any],
    ) -> InterpretationRecord:
        now = time.time()
        record = InterpretationRecord(
            interpretation_id=str(uuid.uuid4()),
            user_id=user_id,
            conversation_id=conversation_id or str(uuid.uuid4()),
            original_query=original_query,
            structured=copy.deepcopy(structured),
            named_topic=copy.deepcopy(named_topic),
            interpretation_warnings=list(interpretation_warnings),
            display_interpretation=display_interpretation,
            query_understanding=copy.deepcopy(query_understanding),
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        async with self._lock:
            self._purge(now)
            self._records[record.interpretation_id] = record
        return record

    def _validated(
        self,
        interpretation_id: str,
        *,
        user_id: str,
        conversation_id: str | None,
    ) -> InterpretationRecord:
        record = self._records.get(interpretation_id)
        if record is None:
            raise InterpretationStateError("interpretation_not_found")
        if record.user_id != user_id:
            raise InterpretationStateError("interpretation_not_found")
        if conversation_id and record.conversation_id != conversation_id:
            raise InterpretationStateError("interpretation_conversation_mismatch")
        if record.expires_at <= time.time():
            raise InterpretationStateError("interpretation_expired")
        return record

    async def supersede(
        self,
        interpretation_id: str,
        *,
        user_id: str,
        conversation_id: str | None,
    ) -> None:
        async with self._lock:
            record = self._validated(
                interpretation_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if record.status == "analyzing":
                raise InterpretationStateError("interpretation_already_analyzing")
            if record.status == "awaiting_confirmation":
                record.status = "superseded"

    async def begin_analysis(
        self,
        interpretation_id: str,
        *,
        user_id: str,
        conversation_id: str | None,
    ) -> tuple[InterpretationRecord, bool]:
        async with self._lock:
            record = self._validated(
                interpretation_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if record.status == "superseded":
                raise InterpretationStateError("interpretation_superseded")
            if record.status == "error":
                raise InterpretationStateError(record.failure or "interpretation_analysis_failed")
            if record.status == "completed":
                return record, False
            if record.status == "analyzing":
                return record, False
            record.status = "analyzing"
            return record, True

    async def wait_for_result(self, record: InterpretationRecord) -> dict[str, Any]:
        await record.completed.wait()
        if record.status == "completed" and record.result is not None:
            return copy.deepcopy(record.result)
        raise InterpretationStateError(record.failure or "interpretation_analysis_failed")

    async def finish(
        self,
        record: InterpretationRecord,
        result: dict[str, Any],
    ) -> None:
        async with self._lock:
            record.result = copy.deepcopy(result)
            record.status = "completed"
            record.completed.set()

    async def fail(self, record: InterpretationRecord, reason: str) -> None:
        async with self._lock:
            record.failure = reason
            record.status = "error"
            record.completed.set()

    def clear(self) -> None:
        """Test helper."""
        self._records.clear()


INTERPRETATION_STORE = InterpretationStore()
