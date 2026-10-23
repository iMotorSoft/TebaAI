"""Parallel generation foundation: identity, active pointer, visibility, CAS.

These tests use the local DEV PostgreSQL. They create an isolated synthetic
logical document (own scope, own collection, own documents) and remove it
afterwards. They never touch the real C document content, never re-embed and
never write to Milvus.

The suite proves the foundation contract:

* a generation has an explicit identity and an explicit status;
* exactly one generation per logical document is ACTIVE;
* the active pointer is the only authority for normal readers;
* a candidate generation is invisible to text search, hybrid search, the page
  viewer and citations, even when it completed after the active generation;
* an atomic compare-and-swap activates a candidate and rolls back;
* a stale expectation is rejected instead of silently winning;
* administrative code can address a generation explicitly.
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

import globalVar as g
from modules.library import generation as generation_module
from modules.library.generation import (
    GENERATION_ACTIVE,
    GENERATION_BUILDING,
    GENERATION_CANDIDATE,
    GENERATION_FAILED,
    GENERATION_INACTIVE,
    OPERATION_CUTOVER,
    OPERATION_ROLLBACK,
    GenerationConflictError,
    GenerationPreconditionError,
    activate_generation,
    get_generation_by_document,
    list_generations,
    resolve_active_document_ids,
    resolve_generation_document_id,
)
from modules.library.source_repository import get_page_publication
from modules.library.text_search import search_chunks_text

SCOPE_CODE = "gen_foundation_v2_test"
COLLECTION_CODE = "gen_foundation_v2_test"
OLD_MARKER = "OLDGENERATIONEVIDENCE"
NEW_MARKER = "NEWGENERATIONEVIDENCE"
CURRENT_C_DOCUMENT = "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"
CURRENT_C_RUN = "6c1a19b8-b60b-52de-b709-5496f4c6e937"


def _require_dev_database() -> None:
    assert g.TEBAAI_ENV == "development" and not g.is_tebaai_production()
    assert g.POSTGRES_HOST in {"127.0.0.1", "localhost"}
    assert g.POSTGRES_DB == "tebaai"


@asynccontextmanager
async def _connection():
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row

    _require_dev_database()
    conn = await AsyncConnection.connect(
        g.POSTGRES_DSN, row_factory=dict_row, connect_timeout=5
    )
    try:
        yield conn
    finally:
        await conn.close()


async def _fetchone(conn, sql: str, params: dict[str, Any] | None = None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def _fetchall(conn, sql: str, params: dict[str, Any] | None = None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def _run(conn, sql: str, params: dict[str, Any] | None = None) -> int:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.rowcount


@dataclass
class SyntheticFixture:
    scope_id: UUID
    collection_id: UUID
    logical_id: UUID
    old_document_id: UUID
    new_document_id: UUID
    old_generation_id: UUID
    new_generation_id: UUID
    old_run_id: UUID
    new_run_id: UUID


async def _create_synthetic(conn) -> SyntheticFixture:
    """Create one logical document with an OLD (active) and a NEW (candidate) generation."""
    tenant = await _fetchone(
        conn,
        """
        SELECT ks.organization_id, ks.workspace_id, ks.project_id
        FROM knowledge_scopes ks WHERE ks.knowledge_scope_code='breslov_primary'
        """,
    )
    assert tenant, "the primary scope is required as tenant template"

    await _run(
        conn,
        """
        INSERT INTO knowledge_scopes(
            organization_id, workspace_id, project_id, knowledge_scope_code, name,
            description, scope_type, language_policy, status)
        VALUES (%(organization_id)s, %(workspace_id)s, %(project_id)s, %(scope)s,
                'Generation foundation V2 synthetic scope',
                'isolated synthetic scope for generation foundation tests',
                'bibliographic_corpus', 'es', 'active')
        """,
        {**tenant, "scope": SCOPE_CODE},
    )
    scope_id = (await _fetchone(
        conn, "SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s", (SCOPE_CODE,)
    ))["id"]

    await _run(
        conn,
        """
        INSERT INTO library_collections_legacy(id, code, name, description, default_language, is_active)
        VALUES (gen_random_uuid(), %s, 'Generation foundation V2 synthetic collection',
                'isolated synthetic collection', 'es', true)
        """,
        (COLLECTION_CODE,),
    )
    collection_id = (await _fetchone(
        conn, "SELECT id FROM library_collections_legacy WHERE code=%s", (COLLECTION_CODE,)
    ))["id"]

    logical = await generation_module.ensure_logical_document(
        conn,
        collection_id=collection_id,
        knowledge_scope_id=scope_id,
        organization_id=tenant["organization_id"],
        workspace_id=tenant["workspace_id"],
        project_id=tenant["project_id"],
        title="Generation foundation V2 synthetic document",
        source_sha256="f" * 64,
        source_filename="synthetic.pdf",
    )
    logical_id = logical["id"]

    generations: dict[str, dict[str, Any]] = {}
    for label, marker, status in (
        ("old", OLD_MARKER, GENERATION_ACTIVE),
        ("new", NEW_MARKER, GENERATION_CANDIDATE),
    ):
        document_id = uuid4()
        text_id = uuid4()
        run_id = uuid4()
        await _run(
            conn,
            """
            INSERT INTO library_documents(
                id, collection_id, title, language, source_type, source_filename,
                source_size_bytes, source_sha256, status, knowledge_scope_id,
                organization_id, workspace_id, project_id)
            VALUES (%s, %s, %s, 'es', 'pdf', 'synthetic.pdf', 1, %s, 'ready', %s,
                    %s, %s, %s)
            """,
            (
                document_id,
                collection_id,
                f"Generation foundation V2 synthetic {label}",
                "f" * 64,
                scope_id,
                tenant["organization_id"],
                tenant["workspace_id"],
                tenant["project_id"],
            ),
        )
        await _run(
            conn,
            """
            INSERT INTO library_ingestion_runs_v2(
                run_id, document_id, pipeline_version, scope_code, status, finished_at)
            VALUES (%s, %s, 'synthetic_v1', %s, 'completed', now())
            """,
            (run_id, document_id, SCOPE_CODE),
        )
        await _run(
            conn,
            """
            INSERT INTO library_document_texts(
                id, document_id, text_format, content, content_sha256, content_length,
                extraction_method, text_role, page_markers_enabled, page_count, knowledge_scope_id)
            VALUES (%s, %s, 'markdown', %s, %s, %s, 'synthetic', 'canonical', true, 1, %s)
            """,
            (
                text_id,
                document_id,
                marker,
                hashlib.sha256(marker.encode()).hexdigest(),
                len(marker),
                scope_id,
            ),
        )
        await _run(
            conn,
            """
            INSERT INTO library_pages_v2(
                page_id, run_id, document_id, page_number, text, char_count,
                extraction_method, confidence, layout_notes)
            VALUES (%s, %s, %s, 1, %s, %s, 'synthetic', 1.0,
                    jsonb_build_object('region_publication',
                        jsonb_build_object('page_status', 'FULL', 'marker', %s::text)))
            """,
            (uuid4(), run_id, document_id, marker, len(marker), marker),
        )
        await _run(
            conn,
            """
            INSERT INTO library_document_chunks(
                id, document_id, document_text_id, collection_id, chunk_index, chunk_uid,
                language, content, content_sha256, content_length, search_text_normalized,
                search_vector_es, search_vector_simple, page_start, page_end, citable,
                knowledge_scope_id, organization_id, workspace_id, project_id)
            VALUES (%s, %s, %s, %s, 0, %s, 'es', %s, %s, %s, %s,
                    to_tsvector('spanish', %s), to_tsvector('simple', %s), 1, 1, true,
                    %s, %s, %s, %s)
            """,
            (
                uuid4(),
                document_id,
                text_id,
                collection_id,
                f"{label}-chunk",
                marker,
                hashlib.sha256(marker.encode()).hexdigest(),
                len(marker),
                marker,
                marker,
                marker,
                scope_id,
                tenant["organization_id"],
                tenant["workspace_id"],
                tenant["project_id"],
            ),
        )
        generation = await generation_module.register_generation(
            conn,
            logical_document_id=logical_id,
            document_id=document_id,
            pipeline_version=f"synthetic_{label}_v1",
            source_sha256="f" * 64,
            status=status,
            run_id=run_id,
        )
        generations[label] = {
            "document_id": document_id,
            "run_id": run_id,
            "generation_id": generation["id"],
        }

    pointer_rows = await _run(
        conn,
        """
        INSERT INTO library_logical_document_active_generations(
            logical_document_id, generation_id, expected_generation_id, operation)
        VALUES (%s, %s, %s, 'BACKFILL')
        """,
        (logical_id, generations["old"]["generation_id"], generations["old"]["generation_id"]),
    )
    assert pointer_rows == 1
    # Migration 043 records the deterministic initial activation as a BACKFILL
    # audit row. The fixture must mirror it, otherwise a later ROLLBACK is
    # rejected because the retained generation has no authoritative activation
    # history even though the pointer says it was active.
    audit_rows = await _run(
        conn,
        """
        INSERT INTO library_generation_activation_audit(
            logical_document_id, from_generation_id, to_generation_id,
            expected_generation_id, operation, result, reason)
        VALUES (%s, NULL, %s, %s, 'BACKFILL', 'APPLIED',
                'synthetic fixture: deterministic backfill')
        """,
        (
            logical_id,
            generations["old"]["generation_id"],
            generations["old"]["generation_id"],
        ),
    )
    assert audit_rows == 1

    return SyntheticFixture(
        scope_id=scope_id,
        collection_id=collection_id,
        logical_id=logical_id,
        old_document_id=generations["old"]["document_id"],
        new_document_id=generations["new"]["document_id"],
        old_generation_id=generations["old"]["generation_id"],
        new_generation_id=generations["new"]["generation_id"],
        old_run_id=generations["old"]["run_id"],
        new_run_id=generations["new"]["run_id"],
    )


async def _destroy_synthetic(conn, fixture: SyntheticFixture) -> None:
    """Remove the synthetic graph in FK-safe order.

    The active pointer and the generations reference the logical document and
    the ingestion runs, and ``library_documents.logical_document_id`` references
    the logical document without cascade. Removing the logical row first raises
    ``library_documents_logical_document_id_fkey`` and leaves the fixture behind,
    which then breaks every later fixture with a duplicate scope key.
    """
    await _run(
        conn,
        "DELETE FROM library_logical_document_active_generations WHERE logical_document_id=%s",
        (fixture.logical_id,),
    )
    await _run(
        conn,
        "DELETE FROM library_generation_activation_audit WHERE logical_document_id=%s",
        (fixture.logical_id,),
    )
    await _run(
        conn,
        "DELETE FROM library_document_generations WHERE logical_document_id=%s",
        (fixture.logical_id,),
    )
    for document_id in (fixture.old_document_id, fixture.new_document_id):
        await _run(
            conn, "DELETE FROM library_document_chunks WHERE document_id=%s", (document_id,)
        )
        await _run(
            conn, "DELETE FROM library_pages_v2 WHERE document_id=%s", (document_id,)
        )
        await _run(
            conn, "DELETE FROM library_document_texts WHERE document_id=%s", (document_id,)
        )
        await _run(conn, "DELETE FROM library_documents WHERE id=%s", (document_id,))
    for document_id in (fixture.old_document_id, fixture.new_document_id):
        await _run(
            conn, "DELETE FROM library_ingestion_runs_v2 WHERE document_id=%s", (document_id,)
        )
    await _run(
        conn, "DELETE FROM library_logical_documents WHERE id=%s", (fixture.logical_id,)
    )
    await _run(conn, "DELETE FROM library_collections_legacy WHERE code=%s", (COLLECTION_CODE,))
    await _run(
        conn, "DELETE FROM knowledge_scopes WHERE knowledge_scope_code=%s", (SCOPE_CODE,)
    )


@pytest.fixture
async def synthetic():
    async with _connection() as conn:
        async with conn.transaction():
            fixture = await _create_synthetic(conn)
        try:
            yield fixture
        finally:
            async with conn.transaction():
                await _destroy_synthetic(conn, fixture)


# ── Schema and backfill ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_foundation_objects_exist():
    async with _connection() as conn:
        found = {
            row["table_name"]
            for row in await _fetchall(
                conn,
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_name IN ('library_logical_documents','library_document_generations',
                                     'library_logical_document_active_generations',
                                     'library_generation_activation_audit')
                """,
            )
        }
        assert found == {
            "library_logical_documents",
            "library_document_generations",
            "library_logical_document_active_generations",
            "library_generation_activation_audit",
        }
        view = await _fetchone(
            conn, "SELECT count(*) AS c FROM pg_views WHERE viewname='library_visible_documents'"
        )
        assert view["c"] == 1


@pytest.mark.asyncio
async def test_current_c_is_backfilled_as_the_active_generation():
    async with _connection() as conn:
        result = await _fetchone(
            conn,
            """
            SELECT g.id AS generation_id, g.status, g.run_id, g.logical_document_id,
                   p.generation_id AS active_generation_id,
                   (SELECT count(*) FROM library_document_chunks c
                     WHERE c.document_id=%(document)s) AS chunks
            FROM library_document_generations g
            JOIN library_logical_document_active_generations p
              ON p.logical_document_id = g.logical_document_id
             AND p.generation_id = g.id
            WHERE g.document_id=%(document)s
            """,
            {"document": CURRENT_C_DOCUMENT},
        )
        assert result is not None
        assert result["status"] == GENERATION_ACTIVE
        assert result["active_generation_id"] == result["generation_id"]
        assert str(result["run_id"]) == CURRENT_C_RUN
        assert result["chunks"] == 942
        visible = await _fetchone(
            conn,
            "SELECT count(*) AS c FROM library_visible_documents WHERE id=%s",
            (CURRENT_C_DOCUMENT,),
        )
        assert visible["c"] == 1


# ── Database level invariants ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_second_active_generation_is_rejected_by_the_database(synthetic):
    async with _connection() as conn:
        with pytest.raises(Exception) as excinfo:
            await _run(
                conn,
                "UPDATE library_document_generations SET status='ACTIVE' WHERE id=%s",
                (synthetic.new_generation_id,),
            )
        assert "uq_library_document_generations_single_active" in str(excinfo.value)
        await conn.rollback()


@pytest.mark.asyncio
async def test_cross_document_pointer_is_rejected_by_the_database(synthetic):
    # The pointer may only reference a generation of its own logical document
    # (composite foreign key). Build a second logical document and try to point
    # it at a generation that belongs to the first one; the whole probe is
    # rolled back, so no synthetic row survives.
    async with _connection() as conn:
        async with conn.transaction():
            other_logical = await _fetchone(
                conn,
                """
                INSERT INTO library_logical_documents(
                    collection_id, knowledge_scope_id, organization_id, workspace_id,
                    project_id, title, source_sha256)
                SELECT collection_id, knowledge_scope_id, organization_id, workspace_id,
                       project_id, 'Generation foundation V2 cross-document probe', %s
                FROM library_logical_documents
                WHERE id=%s
                RETURNING id
                """,
                ("e" * 64, synthetic.logical_id),
            )
            assert other_logical is not None
            with pytest.raises(Exception) as excinfo:
                await _run(
                    conn,
                    """
                    INSERT INTO library_logical_document_active_generations(
                        logical_document_id, generation_id, expected_generation_id, operation)
                    VALUES (%s, %s, %s, 'BACKFILL')
                    """,
                    (
                        other_logical["id"],
                        synthetic.old_generation_id,
                        synthetic.old_generation_id,
                    ),
                )
            assert "library_logical_document_active_generations_generation_fkey" in str(
                excinfo.value
            )


# ── Visibility ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_generation_is_invisible_to_normal_readers(synthetic):
    async with _connection() as conn:
        visible = await resolve_active_document_ids(conn, knowledge_scope_code=SCOPE_CODE)
        assert visible == [str(synthetic.old_document_id)]

        old_hits = await search_chunks_text(
            conn, SCOPE_CODE, OLD_MARKER, top_k=5, mode="phrase"
        )
        assert [hit["document_id"] for hit in old_hits] == [str(synthetic.old_document_id)]

        new_hits = await search_chunks_text(
            conn, SCOPE_CODE, NEW_MARKER, top_k=5, mode="phrase"
        )
        assert new_hits == [], "a candidate generation must not be retrievable"


@pytest.mark.asyncio
async def test_completed_candidate_does_not_steal_the_page_publication(synthetic):
    async with _connection() as conn:
        publication = await get_page_publication(conn, synthetic.old_document_id, 1)
        assert publication is not None
        assert publication["marker"] == OLD_MARKER
        candidate_publication = await get_page_publication(
            conn, synthetic.new_document_id, 1
        )
        assert candidate_publication is None


@pytest.mark.asyncio
async def test_explicit_generation_inspection_reaches_the_candidate(synthetic):
    async with _connection() as conn:
        document_id = await resolve_generation_document_id(
            conn, synthetic.new_generation_id
        )
        assert document_id == str(synthetic.new_document_id)
        hits = await search_chunks_text(
            conn, SCOPE_CODE, NEW_MARKER, top_k=5, mode="phrase",
            document_ids=[document_id],
        )
        assert [hit["document_id"] for hit in hits] == [str(synthetic.new_document_id)]
        evidence = await generation_module.generation_evidence(
            conn, synthetic.new_generation_id
        )
        assert len(evidence["chunks"]) == 1
        assert len(evidence["pages"]) == 1


@pytest.mark.asyncio
async def test_reader_fails_closed_when_the_pointer_is_broken(synthetic):
    async with _connection() as conn:
        # A pointer row can only reference an existing generation of the same
        # logical document, so the reachable "broken pointer" state is a pointer
        # that resolves to a CANDIDATE generation while another generation of the
        # logical document is still ACTIVE. The authority is inconsistent, so
        # every normal reader must fail closed instead of falling back to the
        # ACTIVE generation.
        async with conn.transaction():
            await _run(
                conn,
                """
                UPDATE library_logical_document_active_generations
                SET generation_id=%s
                WHERE logical_document_id=%s
                """,
                (synthetic.new_generation_id, synthetic.logical_id),
            )
        try:
            visible = await resolve_active_document_ids(
                conn, knowledge_scope_code=SCOPE_CODE
            )
            assert visible == []
            hits = await search_chunks_text(
                conn, SCOPE_CODE, OLD_MARKER, top_k=5, mode="phrase"
            )
            assert hits == [], "a broken pointer must not fall back to any generation"
        finally:
            async with conn.transaction():
                await _run(
                    conn,
                    """
                    UPDATE library_logical_document_active_generations
                    SET generation_id=%s WHERE logical_document_id=%s
                    """,
                    (synthetic.old_generation_id, synthetic.logical_id),
                )


# ── Atomic switch ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_atomic_cutover_and_rollback(synthetic):
    async with _connection() as conn:
        async with conn.transaction():
            result = await activate_generation(
                conn,
                logical_document_id=synthetic.logical_id,
                expected_active_generation_id=synthetic.old_generation_id,
                new_generation_id=synthetic.new_generation_id,
                operation=OPERATION_CUTOVER,
            )
        assert result["result"] == "APPLIED"

        async with conn.transaction():
            visible = await resolve_active_document_ids(
                conn, knowledge_scope_code=SCOPE_CODE
            )
        assert visible == [str(synthetic.new_document_id)]

        async with conn.transaction():
            old_hits = await search_chunks_text(
                conn, SCOPE_CODE, OLD_MARKER, top_k=5, mode="phrase"
            )
            new_hits = await search_chunks_text(
                conn, SCOPE_CODE, NEW_MARKER, top_k=5, mode="phrase"
            )
        assert old_hits == []
        assert [hit["document_id"] for hit in new_hits] == [str(synthetic.new_document_id)]

        publication = await get_page_publication(conn, synthetic.new_document_id, 1)
        assert publication is not None
        assert publication["marker"] == NEW_MARKER

        async with conn.transaction():
            rollback = await activate_generation(
                conn,
                logical_document_id=synthetic.logical_id,
                expected_active_generation_id=synthetic.new_generation_id,
                new_generation_id=synthetic.old_generation_id,
                operation=OPERATION_ROLLBACK,
            )
        assert rollback["result"] == "APPLIED"

        async with conn.transaction():
            visible = await resolve_active_document_ids(
                conn, knowledge_scope_code=SCOPE_CODE
            )
        assert visible == [str(synthetic.old_document_id)]

        generations = await list_generations(conn, synthetic.logical_id)
        states = {str(g["id"]): g["status"] for g in generations}
        assert states[str(synthetic.old_generation_id)] == GENERATION_ACTIVE
        assert states[str(synthetic.new_generation_id)] == GENERATION_INACTIVE


@pytest.mark.asyncio
async def test_stale_expected_active_generation_is_rejected(synthetic):
    async with _connection() as conn:
        async with conn.transaction():
            await activate_generation(
                conn,
                logical_document_id=synthetic.logical_id,
                expected_active_generation_id=synthetic.old_generation_id,
                new_generation_id=synthetic.new_generation_id,
                operation=OPERATION_CUTOVER,
            )
        with pytest.raises(GenerationConflictError):
            async with conn.transaction():
                await activate_generation(
                    conn,
                    logical_document_id=synthetic.logical_id,
                    expected_active_generation_id=synthetic.old_generation_id,
                    new_generation_id=synthetic.old_generation_id,
                    operation=OPERATION_CUTOVER,
                )
        async with conn.transaction():
            visible = await resolve_active_document_ids(
                conn, knowledge_scope_code=SCOPE_CODE
            )
        assert visible == [str(synthetic.new_document_id)], "the stale writer must not win"


@pytest.mark.asyncio
async def test_only_candidate_generations_can_be_activated(synthetic):
    async with _connection() as conn:
        for status in (GENERATION_BUILDING, GENERATION_FAILED):
            await _run(
                conn,
                "UPDATE library_document_generations SET status=%s WHERE id=%s",
                (status, synthetic.new_generation_id),
            )
            with pytest.raises(GenerationPreconditionError):
                async with conn.transaction():
                    await activate_generation(
                        conn,
                        logical_document_id=synthetic.logical_id,
                        expected_active_generation_id=synthetic.old_generation_id,
                        new_generation_id=synthetic.new_generation_id,
                    )
            await conn.rollback()
        await _run(
            conn,
            "UPDATE library_document_generations SET status=%s WHERE id=%s",
            (GENERATION_CANDIDATE, synthetic.new_generation_id),
        )


@pytest.mark.asyncio
async def test_activation_is_idempotent(synthetic):
    async with _connection() as conn:
        async with conn.transaction():
            first = await activate_generation(
                conn,
                logical_document_id=synthetic.logical_id,
                expected_active_generation_id=synthetic.old_generation_id,
                new_generation_id=synthetic.new_generation_id,
            )
        async with conn.transaction():
            second = await activate_generation(
                conn,
                logical_document_id=synthetic.logical_id,
                expected_active_generation_id=synthetic.old_generation_id,
                new_generation_id=synthetic.new_generation_id,
            )
        assert first["result"] == "APPLIED"
        assert second["result"] == "IDEMPOTENT"
        async with conn.transaction():
            rows = await _fetchone(
                conn,
                """
                SELECT count(*) AS c FROM library_generation_activation_audit
                WHERE logical_document_id=%s AND result='APPLIED'
                  AND operation=%s
                """,
                (synthetic.logical_id, OPERATION_CUTOVER),
            )
        assert rows["c"] == 1


@pytest.mark.asyncio
async def test_switch_is_audited(synthetic):
    async with _connection() as conn:
        async with conn.transaction():
            await activate_generation(
                conn,
                logical_document_id=synthetic.logical_id,
                expected_active_generation_id=synthetic.old_generation_id,
                new_generation_id=synthetic.new_generation_id,
                operation=OPERATION_CUTOVER,
            )
        audit = await generation_module.list_activation_audit(conn, synthetic.logical_id)
        applied = [row for row in audit if row["result"] == "APPLIED"]
        assert applied
        last = applied[-1]
        assert str(last["from_generation_id"]) == str(synthetic.old_generation_id)
        assert str(last["to_generation_id"]) == str(synthetic.new_generation_id)
        assert last["operation"] == OPERATION_CUTOVER


# ── Retention and cleanup protection ────────────────────────────────────────


@pytest.mark.asyncio
async def test_active_and_retained_generations_are_cleanup_protected(synthetic):
    async with _connection() as conn:
        protected = await generation_module.cleanup_protected_generations(
            conn, synthetic.old_document_id
        )
        assert any(row["status"] == GENERATION_ACTIVE for row in protected)
        with pytest.raises(Exception):
            await _run(
                conn,
                "DELETE FROM library_document_generations WHERE id=%s",
                (synthetic.old_generation_id,),
            )
        await conn.rollback()


@pytest.mark.asyncio
async def test_candidate_cleanup_does_not_touch_the_active_generation(synthetic):
    async with _connection() as conn:
        async with conn.transaction():
            await _run(
                conn,
                "UPDATE library_document_generations SET retention_hold=false WHERE id=%s",
                (synthetic.new_generation_id,),
            )
            await _run(
                conn,
                "DELETE FROM library_document_generations WHERE id=%s",
                (synthetic.new_generation_id,),
            )
        async with conn.transaction():
            visible = await resolve_active_document_ids(
                conn, knowledge_scope_code=SCOPE_CODE
            )
        assert visible == [str(synthetic.old_document_id)]
        generation = await get_generation_by_document(conn, synthetic.old_document_id)
        assert generation is not None
        assert generation["status"] == GENERATION_ACTIVE
