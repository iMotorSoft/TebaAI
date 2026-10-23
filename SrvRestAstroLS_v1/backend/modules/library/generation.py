"""Logical document generations: identity, active pointer and atomic switch.

MODEL A. One logical document (a tenant-scoped, collection-scoped, source-scoped
identity) owns many explicit generations. A generation is the physical carrier of
one evidence set: its document, its ingestion run, its pages, chunks, embeddings,
vectors and citations.

Authoritative rules enforced here:

* The active generation is read from ``library_logical_document_active_generations``.
  It is never inferred from ``created_at``, ``finished_at``, "latest completed run"
  or a numeric id ordering.
* At most one generation per logical document is ACTIVE (database partial unique
  index) and at most one active pointer row exists per logical document
  (primary key).
* The pointer may only reference a generation of the same logical document
  (composite foreign key), so a cross-document activation is rejected by
  PostgreSQL, not only by application code.
* Switching is compare-and-swap: the caller states the generation it believes is
  active, and a stale expectation is rejected instead of silently winning.
* Every switch is audited.

Normal readers never call this module to decide visibility: they join the
``library_visible_documents`` view, which is derived from the active pointer.
Administrative/reconciliation code may address a generation explicitly through
``resolve_generation_document_id`` and friends.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence
from uuid import UUID

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from infrastructure.postgres.transaction import execute, fetch_all, fetch_one, transaction

GENERATION_BUILDING = "BUILDING"
GENERATION_CANDIDATE = "CANDIDATE"
GENERATION_ACTIVE = "ACTIVE"
GENERATION_INACTIVE = "INACTIVE"
GENERATION_FAILED = "FAILED"

GENERATION_STATUSES = (
    GENERATION_BUILDING,
    GENERATION_CANDIDATE,
    GENERATION_ACTIVE,
    GENERATION_INACTIVE,
    GENERATION_FAILED,
)

#: Cutover promotes only a reconciled candidate; rollback has a separate policy.
SWITCHABLE_STATUS = GENERATION_CANDIDATE

OPERATION_CUTOVER = "CUTOVER"
OPERATION_ROLLBACK = "ROLLBACK"
OPERATION_BACKFILL = "BACKFILL"
OPERATION_REGISTER = "REGISTER"

RESULT_APPLIED = "APPLIED"
RESULT_REJECTED = "REJECTED"
RESULT_IDEMPOTENT = "IDEMPOTENT"


class GenerationError(RuntimeError):
    """Base error for generation operations."""


class GenerationPreconditionError(GenerationError):
    """A precondition failed. No switch was performed."""


class GenerationConflictError(GenerationPreconditionError):
    """The caller's expected active generation is stale. No switch was performed."""


def _uuid(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _jsonb(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {})


# ── Logical document ─────────────────────────────────────────────────────────


async def ensure_logical_document(
    conn: AsyncConnection,
    *,
    collection_id: UUID | str,
    title: str,
    source_sha256: str,
    knowledge_scope_id: UUID | str | None = None,
    organization_id: UUID | str | None = None,
    workspace_id: UUID | str | None = None,
    project_id: UUID | str | None = None,
    source_filename: str | None = None,
    source_size_bytes: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the logical document for this identity, creating it when missing.

    The natural key is (knowledge_scope_id, collection_id, source_sha256): one
    logical document per approved source inside a tenant scope and collection.
    """
    existing = await fetch_one(
        conn,
        """
        SELECT * FROM library_logical_documents
        WHERE collection_id=%(collection_id)s
          AND source_sha256=%(sha)s
          AND knowledge_scope_id IS NOT DISTINCT FROM %(scope_id)s
        """,
        {
            "collection_id": str(collection_id),
            "sha": source_sha256,
            "scope_id": _uuid(knowledge_scope_id),
        },
    )
    if existing:
        return dict(existing)
    row = await fetch_one(
        conn,
        """
        INSERT INTO library_logical_documents(
            id, collection_id, knowledge_scope_id, organization_id, workspace_id, project_id,
            title, source_sha256, source_filename, source_size_bytes, metadata
        )
        VALUES (gen_random_uuid(), %(collection_id)s, %(scope_id)s, %(organization_id)s,
                %(workspace_id)s, %(project_id)s, %(title)s, %(sha)s, %(filename)s,
                %(size_bytes)s, %(metadata)s::jsonb)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        {
            "collection_id": str(collection_id),
            "scope_id": _uuid(knowledge_scope_id),
            "organization_id": _uuid(organization_id),
            "workspace_id": _uuid(workspace_id),
            "project_id": _uuid(project_id),
            "title": title,
            "sha": source_sha256,
            "filename": source_filename,
            "size_bytes": source_size_bytes,
            "metadata": _jsonb(metadata),
        },
    )
    if row:
        return dict(row)
    # A concurrent creator won the race; re-read the winner.
    winner = await fetch_one(
        conn,
        """
        SELECT * FROM library_logical_documents
        WHERE collection_id=%(collection_id)s
          AND source_sha256=%(sha)s
          AND knowledge_scope_id IS NOT DISTINCT FROM %(scope_id)s
        """,
        {
            "collection_id": str(collection_id),
            "sha": source_sha256,
            "scope_id": _uuid(knowledge_scope_id),
        },
    )
    if not winner:
        raise GenerationError("Logical document could not be resolved")
    return dict(winner)


# ── Generation identity ──────────────────────────────────────────────────────


async def register_generation(
    conn: AsyncConnection,
    *,
    logical_document_id: UUID | str,
    document_id: UUID | str,
    pipeline_version: str,
    source_sha256: str,
    status: str = GENERATION_BUILDING,
    run_id: UUID | str | None = None,
    job_id: UUID | str | None = None,
    attempt_number: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register a generation for a physical document and bind the document."""
    if status not in GENERATION_STATUSES:
        raise GenerationPreconditionError(f"Unknown generation status '{status}'")
    await execute(
        conn,
        "UPDATE library_documents SET logical_document_id=%(logical)s WHERE id=%(document)s",
        {"logical": str(logical_document_id), "document": str(document_id)},
    )
    row = await fetch_one(
        conn,
        """
        INSERT INTO library_document_generations(
            id, logical_document_id, document_id, run_id, job_id, attempt_number,
            pipeline_version, status, source_sha256, metadata
        )
        VALUES (gen_random_uuid(), %(logical)s, %(document)s, %(run)s, %(job)s, %(attempt)s,
                %(pipeline)s, %(status)s, %(sha)s, %(metadata)s::jsonb)
        ON CONFLICT (document_id) DO NOTHING
        RETURNING *
        """,
        {
            "logical": str(logical_document_id),
            "document": str(document_id),
            "run": _uuid(run_id),
            "job": _uuid(job_id),
            "attempt": attempt_number,
            "pipeline": pipeline_version,
            "status": status,
            "sha": source_sha256,
            "metadata": _jsonb(metadata),
        },
    )
    if row:
        return dict(row)
    existing = await fetch_one(
        conn,
        "SELECT * FROM library_document_generations WHERE document_id=%(document)s",
        {"document": str(document_id)},
    )
    if not existing:
        raise GenerationError("Generation could not be registered")
    return dict(existing)


async def get_generation(
    conn: AsyncConnection, generation_id: UUID | str
) -> dict[str, Any] | None:
    row = await fetch_one(
        conn,
        "SELECT * FROM library_document_generations WHERE id=%(id)s",
        {"id": str(generation_id)},
    )
    return dict(row) if row else None


async def get_generation_by_document(
    conn: AsyncConnection, document_id: UUID | str
) -> dict[str, Any] | None:
    row = await fetch_one(
        conn,
        "SELECT * FROM library_document_generations WHERE document_id=%(document)s",
        {"document": str(document_id)},
    )
    return dict(row) if row else None


async def list_generations(
    conn: AsyncConnection, logical_document_id: UUID | str
) -> list[dict[str, Any]]:
    rows = await fetch_all(
        conn,
        """
        SELECT g.*, p.generation_id AS active_generation_id
        FROM library_document_generations g
        LEFT JOIN library_logical_document_active_generations p
          ON p.logical_document_id = g.logical_document_id
        WHERE g.logical_document_id=%(logical)s
        ORDER BY g.created_at, g.id
        """,
        {"logical": str(logical_document_id)},
    )
    return [dict(row) for row in rows]


async def set_generation_status(
    conn: AsyncConnection,
    generation_id: UUID | str,
    status: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Move a generation between non-active states (never performs a switch)."""
    if status not in GENERATION_STATUSES:
        raise GenerationPreconditionError(f"Unknown generation status '{status}'")
    if status == GENERATION_ACTIVE:
        raise GenerationPreconditionError(
            "Use activate_generation for the active pointer; direct activation is refused"
        )
    row = await fetch_one(
        conn,
        """
        UPDATE library_document_generations
        SET status=%(status)s,
            deactivated_at=CASE WHEN %(status)s='INACTIVE' THEN now() ELSE deactivated_at END,
            metadata=COALESCE(metadata,'{}'::jsonb) || %(metadata)s::jsonb
        WHERE id=%(id)s AND status <> 'ACTIVE'
        RETURNING *
        """,
        {
            "id": str(generation_id),
            "status": status,
            "metadata": _jsonb(metadata),
        },
    )
    if not row:
        raise GenerationPreconditionError("Generation is active or unknown")
    return dict(row)


async def set_retention_hold(
    conn: AsyncConnection, generation_id: UUID | str, *, hold: bool
) -> dict[str, Any]:
    """Mark a generation as retained (for example as a rollback generation)."""
    row = await fetch_one(
        conn,
        """
        UPDATE library_document_generations
        SET retention_hold=%(hold)s
        WHERE id=%(id)s AND status <> 'ACTIVE'
        RETURNING *
        """,
        {"id": str(generation_id), "hold": hold},
    )
    if not row:
        raise GenerationPreconditionError("Generation is active or unknown")
    return dict(row)


# ── Visibility resolution ────────────────────────────────────────────────────


async def resolve_active_document_ids(
    conn: AsyncConnection,
    *,
    knowledge_scope_code: str | None = None,
    knowledge_scope_id: UUID | str | None = None,
    document_ids: Iterable[UUID | str] | None = None,
) -> list[str]:
    """Return the physical documents that carry the ACTIVE generation.

    This is the single authoritative resolution used by vector search. An empty
    result means "nothing is active" and callers must fail closed instead of
    falling back to any available generation.
    """
    params: dict[str, Any] = {}
    clauses: list[str] = []
    if knowledge_scope_code:
        clauses.append("ks.knowledge_scope_code = %(scope_code)s")
        params["scope_code"] = knowledge_scope_code
    if knowledge_scope_id:
        clauses.append("d.knowledge_scope_id = %(scope_id)s")
        params["scope_id"] = str(knowledge_scope_id)
    if document_ids is not None:
        ids = [str(item) for item in document_ids]
        if not ids:
            return []
        clauses.append("d.id = ANY(%(document_ids)s::uuid[])")
        params["document_ids"] = ids
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    rows = await fetch_all(
        conn,
        f"""
        SELECT d.id
        FROM library_visible_documents d
        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
        WHERE TRUE{where}
        ORDER BY d.id
        """,
        params,
    )
    return [str(row["id"]) for row in rows]


async def resolve_active_document_id(
    conn: AsyncConnection, document_id: UUID | str
) -> str | None:
    """Return the document id when it currently carries the ACTIVE generation."""
    row = await fetch_one(
        conn,
        "SELECT id FROM library_visible_documents WHERE id=%(id)s",
        {"id": str(document_id)},
    )
    return str(row["id"]) if row else None


async def resolve_generation_document_id(
    conn: AsyncConnection, generation_id: UUID | str
) -> str | None:
    """Explicit, administrative generation addressing (never used by normal readers)."""
    row = await fetch_one(
        conn,
        "SELECT document_id FROM library_document_generations WHERE id=%(id)s",
        {"id": str(generation_id)},
    )
    return str(row["document_id"]) if row else None


async def resolve_active_generation_id(
    conn: AsyncConnection, logical_document_id: UUID | str
) -> str | None:
    row = await fetch_one(
        conn,
        """
        SELECT generation_id FROM library_logical_document_active_generations
        WHERE logical_document_id=%(logical)s
        """,
        {"logical": str(logical_document_id)},
    )
    return str(row["generation_id"]) if row else None


async def resolve_document_logical_id(
    conn: AsyncConnection, document_id: UUID | str
) -> str | None:
    row = await fetch_one(
        conn,
        "SELECT logical_document_id FROM library_documents WHERE id=%(id)s",
        {"id": str(document_id)},
    )
    if not row or not row["logical_document_id"]:
        return None
    return str(row["logical_document_id"])


# ── Atomic compare-and-swap switch ──────────────────────────────────────────


async def _record_audit(
    pool: AsyncConnectionPool,
    *,
    logical_document_id: str,
    from_generation_id: str | None,
    to_generation_id: str | None,
    expected_generation_id: str | None,
    operation: str,
    result: str,
    reason: str | None,
    actor_id: str | None,
) -> None:
    async with pool.connection() as audit_conn:
        await execute(
            audit_conn,
            """
            INSERT INTO library_generation_activation_audit(
                logical_document_id, from_generation_id, to_generation_id,
                expected_generation_id, operation, result, reason, actor_id
            )
            VALUES (%(logical)s, %(from)s, %(to)s, %(expected)s, %(operation)s,
                    %(result)s, %(reason)s, %(actor)s)
            """,
            {
                "logical": logical_document_id,
                "from": from_generation_id,
                "to": to_generation_id,
                "expected": expected_generation_id,
                "operation": operation,
                "result": result,
                "reason": reason,
                "actor": actor_id,
            },
        )


async def activate_generation(
    conn: AsyncConnection,
    *,
    logical_document_id: UUID | str,
    expected_active_generation_id: UUID | str | None,
    new_generation_id: UUID | str,
    operation: str = OPERATION_CUTOVER,
    actor_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Compare-and-swap the active generation inside the caller's transaction.

    Preconditions (all of them, otherwise nothing is written):

    * the logical document exists;
    * the new generation belongs to that logical document;
    * CUTOVER targets CANDIDATE; ROLLBACK targets retained INACTIVE with
      authoritative prior activation and the immediate predecessor switch edge;
    * the new generation is not the current active generation;
    * the current active generation equals ``expected_active_generation_id``.

    The caller owns the transaction so a switch can be committed together with
    the rest of the operation (for example the document publication).
    """
    if operation not in (OPERATION_CUTOVER, OPERATION_ROLLBACK):
        raise GenerationPreconditionError("Activation requires CUTOVER or ROLLBACK")
    logical = str(logical_document_id)
    new_id = str(new_generation_id)
    expected = _uuid(expected_active_generation_id)

    locked = await fetch_one(
        conn,
        "SELECT id FROM library_logical_documents WHERE id=%(logical)s FOR UPDATE",
        {"logical": logical},
    )
    if not locked:
        raise GenerationPreconditionError("Logical document does not exist")

    pointer = await fetch_one(
        conn,
        """
        SELECT generation_id, expected_generation_id
        FROM library_logical_document_active_generations
        WHERE logical_document_id=%(logical)s FOR UPDATE
        """,
        {"logical": logical},
    )
    current = str(pointer["generation_id"]) if pointer else None

    # Preserve existing CUTOVER retry semantics. ROLLBACK must check CAS even
    # when the requested target is already active (a stale rollback is rejected).
    if operation == OPERATION_ROLLBACK and current != expected:
        raise GenerationConflictError(
            "Stale expected active generation: the active generation changed"
        )
    if current == new_id:
        return {
            "result": RESULT_IDEMPOTENT,
            "logical_document_id": logical,
            "from_generation_id": current,
            "to_generation_id": new_id,
            "expected_generation_id": expected,
            "operation": operation,
        }

    if expected is not None and current != expected:
        raise GenerationConflictError(
            "Stale expected active generation: the active generation changed"
        )
    if expected is None and current is not None:
        raise GenerationPreconditionError(
            "An expected active generation is required while a generation is active"
        )

    target = await fetch_one(
        conn,
        """
        SELECT * FROM library_document_generations
        WHERE id=%(id)s AND logical_document_id=%(logical)s FOR UPDATE
        """,
        {"id": new_id, "logical": logical},
    )
    if not target:
        raise GenerationPreconditionError(
            "The target generation does not belong to this logical document"
        )
    required_status = (
        GENERATION_INACTIVE if operation == OPERATION_ROLLBACK else SWITCHABLE_STATUS
    )
    if str(target["status"]) != required_status:
        raise GenerationPreconditionError(
            f"{operation} requires a {required_status} generation; got {target['status']}"
        )
    if operation == OPERATION_ROLLBACK:
        if (
            not target["retention_hold"]
            or not pointer
            or _uuid(pointer["expected_generation_id"]) != new_id
        ):
            raise GenerationPreconditionError(
                "Rollback requires the retained immediate previous active generation"
            )
        history = await fetch_one(
            conn,
            """
            SELECT EXISTS (
                SELECT 1 FROM library_generation_activation_audit
                WHERE logical_document_id=%(logical)s AND to_generation_id=%(id)s
                  AND result='APPLIED'
            ) AND EXISTS (
                SELECT 1 FROM library_generation_activation_audit
                WHERE logical_document_id=%(logical)s AND from_generation_id=%(id)s
                  AND to_generation_id=%(current)s AND result='APPLIED'
                  AND operation IN ('CUTOVER', 'ROLLBACK')
            ) AS eligible
            """,
            {"logical": logical, "id": new_id, "current": current},
        )
        if not history or not history["eligible"]:
            raise GenerationPreconditionError(
                "Rollback requires successful prior activation and switch history"
            )
    if target["source_sha256"] != (
        await fetch_one(
            conn,
            "SELECT source_sha256 FROM library_logical_documents WHERE id=%(logical)s",
            {"logical": logical},
        )
    )["source_sha256"]:
        raise GenerationPreconditionError(
            "The target generation does not match the logical source identity"
        )

    if current:
        await execute(
            conn,
            """
            UPDATE library_document_generations
            SET status='INACTIVE', deactivated_at=now(), retention_hold=true
            WHERE id=%(id)s AND status='ACTIVE'
            """,
            {"id": current},
        )
    await execute(
        conn,
        """
        UPDATE library_document_generations
        SET status='ACTIVE', activated_at=now(), deactivated_at=NULL
        WHERE id=%(id)s
        """,
        {"id": new_id},
    )
    await execute(
        conn,
        """
        INSERT INTO library_logical_document_active_generations(
            logical_document_id, generation_id, expected_generation_id, operation,
            activated_at, activated_by, metadata
        )
        VALUES (%(logical)s, %(generation)s, %(expected)s, %(operation)s, now(),
                %(actor)s, '{}'::jsonb)
        ON CONFLICT (logical_document_id) DO UPDATE
        SET generation_id=EXCLUDED.generation_id,
            expected_generation_id=EXCLUDED.expected_generation_id,
            operation=EXCLUDED.operation,
            activated_at=now(),
            activated_by=EXCLUDED.activated_by
        """,
        {
            "logical": logical,
            "generation": new_id,
            "expected": expected,
            "operation": operation,
            "actor": _uuid(actor_id),
        },
    )
    await execute(
        conn,
        """
        INSERT INTO library_generation_activation_audit(
            logical_document_id, from_generation_id, to_generation_id,
            expected_generation_id, operation, result, reason, actor_id
        )
        VALUES (%(logical)s, %(from)s, %(to)s, %(expected)s, %(operation)s,
                'APPLIED', %(reason)s, %(actor)s)
        """,
        {
            "logical": logical,
            "from": current,
            "to": new_id,
            "expected": expected,
            "operation": operation,
            "reason": "compare-and-swap activation",
            "actor": _uuid(actor_id),
        },
    )
    return {
        "result": RESULT_APPLIED,
        "logical_document_id": logical,
        "from_generation_id": current,
        "to_generation_id": new_id,
        "expected_generation_id": expected,
        "operation": operation,
    }


async def switch_generation(
    pool: AsyncConnectionPool,
    *,
    logical_document_id: UUID | str,
    expected_active_generation_id: UUID | str | None,
    new_generation_id: UUID | str,
    operation: str = OPERATION_CUTOVER,
    actor_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Own the transaction of an atomic switch and audit rejected attempts."""
    try:
        async with transaction(pool) as conn:
            return await activate_generation(
                conn,
                logical_document_id=logical_document_id,
                expected_active_generation_id=expected_active_generation_id,
                new_generation_id=new_generation_id,
                operation=operation,
                actor_id=actor_id,
            )
    except GenerationConflictError as exc:
        pointer = await _read_pointer(pool, logical_document_id)
        await _record_audit(
            pool,
            logical_document_id=str(logical_document_id),
            from_generation_id=pointer,
            to_generation_id=str(new_generation_id),
            expected_generation_id=_uuid(expected_active_generation_id),
            operation=operation,
            result=RESULT_REJECTED,
            reason=str(exc),
            actor_id=_uuid(actor_id),
        )
        raise
    except GenerationPreconditionError as exc:
        pointer = await _read_pointer(pool, logical_document_id)
        await _record_audit(
            pool,
            logical_document_id=str(logical_document_id),
            from_generation_id=pointer,
            to_generation_id=str(new_generation_id),
            expected_generation_id=_uuid(expected_active_generation_id),
            operation=operation,
            result=RESULT_REJECTED,
            reason=str(exc),
            actor_id=_uuid(actor_id),
        )
        raise


async def _read_pointer(
    pool: AsyncConnectionPool, logical_document_id: UUID | str
) -> str | None:
    async with pool.connection() as conn:
        row = await fetch_one(
            conn,
            """
            SELECT generation_id FROM library_logical_document_active_generations
            WHERE logical_document_id=%(logical)s
            """,
            {"logical": str(logical_document_id)},
        )
    return str(row["generation_id"]) if row else None


async def list_activation_audit(
    conn: AsyncConnection, logical_document_id: UUID | str
) -> list[dict[str, Any]]:
    rows = await fetch_all(
        conn,
        """
        SELECT * FROM library_generation_activation_audit
        WHERE logical_document_id=%(logical)s
        ORDER BY created_at, id
        """,
        {"logical": str(logical_document_id)},
    )
    return [dict(row) for row in rows]


# ── Administrative / reconciliation inspection ───────────────────────────────


async def generation_evidence(
    conn: AsyncConnection, generation_id: UUID | str
) -> dict[str, Any]:
    """Explicit generation-scoped evidence inventory (administrative use only)."""
    generation = await get_generation(conn, generation_id)
    if not generation:
        raise GenerationPreconditionError("Unknown generation")
    document_id = str(generation["document_id"])
    pages = await fetch_all(
        conn,
        """
        SELECT page_id, run_id, page_number, char_count, extraction_method,
               layout_notes->'region_publication' AS region_publication
        FROM library_pages_v2 WHERE document_id=%(document)s
        ORDER BY page_number
        """,
        {"document": document_id},
    )
    chunks = await fetch_all(
        conn,
        """
        SELECT id, chunk_uid, chunk_index, page_start, page_end, content_sha256,
               content_length, citable
        FROM library_document_chunks WHERE document_id=%(document)s
        ORDER BY chunk_index, id
        """,
        {"document": document_id},
    )
    vectors = await fetch_all(
        conn,
        """
        SELECT e.id, e.milvus_primary_key, e.chunk_id, e.content_sha256,
               e.embedding_dimension, e.embedding_model
        FROM library_chunk_embeddings e
        JOIN library_document_chunks c ON c.id = e.chunk_id
        WHERE c.document_id=%(document)s
        ORDER BY e.id
        """,
        {"document": document_id},
    )
    return {
        "generation": generation,
        "pages": [dict(row) for row in pages],
        "chunks": [dict(row) for row in chunks],
        "vectors": [dict(row) for row in vectors],
    }


async def cleanup_protected_generations(
    conn: AsyncConnection, document_id: UUID | str
) -> list[dict[str, Any]]:
    """Generations that must never be physically deleted for this document."""
    rows = await fetch_all(
        conn,
        """
        SELECT id, status, retention_hold
        FROM library_document_generations
        WHERE document_id=%(document)s
          AND (status='ACTIVE' OR retention_hold)
        ORDER BY id
        """,
        {"document": str(document_id)},
    )
    return [dict(row) for row in rows]


def generation_scope_filter(
    active_document_ids: Sequence[str],
) -> str:
    """Milvus boolean expression fragment restricted to the active documents."""
    if not active_document_ids:
        return ""
    values = ", ".join(f'"{item}"' for item in active_document_ids)
    return f"document_id in [{values}]"
