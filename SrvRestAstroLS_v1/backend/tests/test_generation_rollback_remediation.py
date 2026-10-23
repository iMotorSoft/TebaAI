"""Offline rollback policy tests; real switch primitive, isolated persistence adapter."""
from copy import deepcopy
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from modules.library import generation as g


class MemoryStore:
    def __init__(self):
        self.pointer = {"generation_id": "OLD", "expected_generation_id": "OLD"}
        self.rows = {
            name: {"id": name, "document_id": name, "logical_document_id": "L",
                   "status": status, "source_sha256": "source", "retention_hold": hold}
            for name, status, hold in [("OLD", "ACTIVE", True), ("NEW", "CANDIDATE", False),
                                       ("G0", "INACTIVE", True), ("B", "CANDIDATE", False)]
        }
        self.audit = [{"logical": "L", "from": None, "to": "OLD", "expected": None,
                       "operation": "BACKFILL", "result": "APPLIED"}]
        self.writes = []

    async def fetch_one(self, conn, sql, p):
        if "SELECT id FROM library_logical_documents" in sql:
            return {"id": "L"}
        if "FROM library_logical_document_active_generations" in sql:
            return dict(self.pointer)
        if "SELECT * FROM library_document_generations" in sql:
            row = self.rows.get(p["id"])
            return dict(row) if row and row["logical_document_id"] == p["logical"] else None
        if "FROM library_generation_activation_audit" in sql:
            prior = any(a["logical"] == p["logical"] and a["to"] == p["id"]
                        and a["result"] == "APPLIED" for a in self.audit)
            edge = any(a["logical"] == p["logical"] and a["from"] == p["id"]
                       and a["to"] == p["current"] and a["result"] == "APPLIED"
                       for a in self.audit)
            return {"eligible": prior and edge}
        if "SELECT source_sha256 FROM library_logical_documents" in sql:
            return {"source_sha256": "source"}
        raise AssertionError(sql)

    async def execute(self, conn, sql, p):
        self.writes.append(sql)
        if "SET status='INACTIVE'" in sql:
            self.rows[p["id"]].update(status="INACTIVE", retention_hold=True)
        elif "SET status='ACTIVE'" in sql:
            self.rows[p["id"]]["status"] = "ACTIVE"
        elif "INSERT INTO library_logical_document_active_generations" in sql:
            self.pointer = {"generation_id": p["generation"], "expected_generation_id": p["expected"]}
        elif "INSERT INTO library_generation_activation_audit" in sql:
            self.audit.append({**p, "result": "APPLIED"})
        else:
            raise AssertionError(sql)

    async def fetch_all(self, conn, sql, p):
        assert "AND (status='ACTIVE' OR retention_hold)" in sql
        return [dict(r) for r in self.rows.values() if r["document_id"] == p["document"]
                and (r["status"] == "ACTIVE" or r["retention_hold"])]

    async def switch(self, target="NEW", expected="OLD", operation="CUTOVER"):
        return await g.activate_generation(None, logical_document_id="L",
                                           expected_active_generation_id=expected,
                                           new_generation_id=target, operation=operation)

    def snapshot(self):
        return deepcopy((self.pointer, self.rows, self.audit, self.writes))


@pytest.fixture
def store(monkeypatch):
    s = MemoryStore()
    monkeypatch.setattr(g, "fetch_one", s.fetch_one)
    monkeypatch.setattr(g, "execute", s.execute)
    monkeypatch.setattr(g, "fetch_all", s.fetch_all)
    return s


@pytest.mark.asyncio
async def test_cutover_rollback_audit_and_cleanup(store):
    assert (await store.switch())["result"] == "APPLIED"
    assert store.pointer["generation_id"] == "NEW"
    assert store.rows["OLD"]["status"] == "INACTIVE"
    assert store.rows["NEW"]["status"] == "ACTIVE"
    assert await g.cleanup_protected_generations(None, "OLD")
    await assert_generic_cleanup_rejected(store.rows["OLD"])
    assert store.rows["OLD"]["retention_hold"]
    assert (await store.switch("OLD", "NEW", "ROLLBACK"))["result"] == "APPLIED"
    assert store.pointer["generation_id"] == "OLD"
    assert store.rows["NEW"]["status"] == "INACTIVE"
    assert store.rows["OLD"]["status"] == "ACTIVE"
    assert await g.cleanup_protected_generations(None, "NEW")
    await assert_generic_cleanup_rejected(store.rows["NEW"])
    assert [(a["operation"], a["from"], a["to"], a["expected"], a["result"])
            for a in store.audit[1:]] == [
                ("CUTOVER", "OLD", "NEW", "OLD", "APPLIED"),
                ("ROLLBACK", "NEW", "OLD", "NEW", "APPLIED")]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["CUTOVER", "ROLLBACK"])
@pytest.mark.parametrize("status", ["BUILDING", "FAILED"])
async def test_invalid_status(store, operation, status):
    store.rows["NEW"]["status"] = status
    before = store.snapshot()
    with pytest.raises(g.GenerationPreconditionError):
        await store.switch(operation=operation)
    assert store.snapshot() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["CUTOVER", "ROLLBACK"])
async def test_cross_document(store, operation):
    store.rows["NEW"]["logical_document_id"] = "OTHER"
    before = store.snapshot()
    with pytest.raises(g.GenerationPreconditionError):
        await store.switch(operation=operation)
    assert store.snapshot() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["arbitrary", "never_active", "unretained", "historical", "no_edge", "rejected_history", "wrong_source"])
async def test_rollback_eligibility_fail_closed(store, defect):
    await store.switch()
    if defect in {"arbitrary", "historical"}:
        if defect == "historical":
            store.audit.append({"logical": "L", "from": None, "to": "G0", "result": "APPLIED"})
        target = "G0"
    else:
        target = "OLD"
        if defect == "never_active":
            store.audit = store.audit[1:]
        elif defect == "unretained":
            store.rows["OLD"]["retention_hold"] = False
        elif defect == "no_edge":
            store.audit = store.audit[:1]
        elif defect == "rejected_history":
            store.audit[0]["result"] = "REJECTED"
        elif defect == "wrong_source":
            store.rows["OLD"]["source_sha256"] = "different"
    before = store.snapshot()
    with pytest.raises(g.GenerationPreconditionError):
        await store.switch(target, "NEW", "ROLLBACK")
    assert store.snapshot() == before


@pytest.mark.asyncio
async def test_inactive_is_not_cutover_candidate(store):
    await store.switch()
    before = store.snapshot()
    with pytest.raises(g.GenerationPreconditionError):
        await store.switch("OLD", "NEW", "CUTOVER")
    assert store.snapshot() == before


@pytest.mark.asyncio
async def test_candidate_is_not_rollback_target(store):
    with pytest.raises(g.GenerationPreconditionError):
        await store.switch(operation="ROLLBACK")
    assert not store.writes


@pytest.mark.asyncio
async def test_stale_cutover_and_stale_rollback(store):
    await store.switch()
    before = store.snapshot()
    with pytest.raises(g.GenerationConflictError):
        await store.switch("B", "OLD")
    assert store.snapshot() == before
    await store.switch("OLD", "NEW", "ROLLBACK")
    before = store.snapshot()
    with pytest.raises(g.GenerationConflictError):
        await store.switch("OLD", "NEW", "ROLLBACK")
    assert store.snapshot() == before


@pytest.mark.asyncio
async def test_idempotency_safe(store):
    await store.switch()
    before = store.snapshot()
    assert (await store.switch())["result"] == "IDEMPOTENT"  # existing cutover retry contract
    assert store.snapshot() == before
    await store.switch("OLD", "NEW", "ROLLBACK")
    before = store.snapshot()
    assert (await store.switch("OLD", "OLD", "ROLLBACK"))["result"] == "IDEMPOTENT"
    assert store.snapshot() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["UNKNOWN", "BACKFILL", "REGISTER"])
async def test_no_policy_bypass(store, operation):
    with pytest.raises(g.GenerationPreconditionError):
        await store.switch(operation=operation)
    assert not store.writes


async def assert_generic_cleanup_rejected(row):
    from modules.library.content_manager_cleanup import ManifestCleanupService
    from modules.library.page_first_gateway import E2EIsolationError
    from globalVar import CONTENT_MANAGER_E2E_SCOPE, CONTENT_MANAGER_E2E_COLLECTION

    def forbidden_index(*args):
        raise AssertionError("Cleanup must reject before any vector access")

    service = ManifestCleanupService(None, index_factory=forbidden_index)
    service._load = AsyncMock(return_value={
        "scope_code": CONTENT_MANAGER_E2E_SCOPE,
        "collection_code": CONTENT_MANAGER_E2E_COLLECTION,
        "document_status": "test_candidate",  # prove retention, not ready-state guard
        "generation_status": row["status"],
        "generation_retention_hold": row["retention_hold"],
    })
    with pytest.raises(E2EIsolationError, match="retained for rollback"):
        await service.cleanup(uuid4(), 1)


@pytest.mark.asyncio
async def test_postgres_rollback_contract():
    """Real SQL/audit with a unique synthetic logical document; entire tx rolled back.

    No pages/chunks/vectors are needed by the existing activation primitive.
    CANDIDATE is its existing completeness admission contract; not redefined here.
    """
    from test_generation_foundation import _connection

    async with _connection() as conn:
        async with conn.transaction(force_rollback=True):
            assert (await g.fetch_one(conn, "SELECT current_database() AS db", {}))["db"] == "tebaai"
            logical, collection = str(uuid4()), str(uuid4())
            await g.execute(conn, """
                INSERT INTO library_collections_legacy(id, code, name, default_language, is_active)
                VALUES (%(id)s, %(code)s, 'Rollback remediation synthetic', 'es', true)
            """, {"id": collection, "code": collection})
            await g.execute(conn, """
                INSERT INTO library_logical_documents(id, collection_id, title, source_sha256)
                VALUES (%(id)s, %(collection)s, 'Rollback remediation synthetic', 'synthetic')
            """, {"id": logical, "collection": collection})
            ids = {}
            for name, status in [("OLD", "CANDIDATE"), ("NEW", "CANDIDATE"),
                                 ("G0", "INACTIVE"), ("B", "CANDIDATE")]:
                document = str(uuid4())
                await g.execute(conn, """
                    INSERT INTO library_documents(id, collection_id, title, language,
                        source_type, source_filename, source_size_bytes, source_sha256, status)
                    VALUES (%(id)s, %(collection)s, 'Rollback remediation synthetic', 'es',
                        'pdf', 'synthetic.pdf', 1, 'synthetic', 'test_candidate')
                """, {"id": document, "collection": collection})
                row = await g.register_generation(
                    conn, logical_document_id=logical, document_id=document,
                    pipeline_version=name, source_sha256="synthetic", status=status)
                ids[name] = str(row["id"])
            async def switch(name, expected, operation="CUTOVER"):
                return await g.activate_generation(
                    conn, logical_document_id=logical,
                    expected_active_generation_id=ids[expected] if expected else None,
                    new_generation_id=ids[name], operation=operation)
            async def reject(name, expected, operation="ROLLBACK", error=g.GenerationPreconditionError):
                before = await g.list_generations(conn, logical)
                audit_before = await g.list_activation_audit(conn, logical)
                with pytest.raises(error):
                    await switch(name, expected, operation)
                assert await g.list_generations(conn, logical) == before
                assert await g.list_activation_audit(conn, logical) == audit_before

            await switch("OLD", None)  # authoritative initial activation, not timestamp seed
            assert (await switch("NEW", "OLD"))["result"] == "APPLIED"
            assert await g.resolve_active_generation_id(conn, logical) == ids["NEW"]
            old = await g.get_generation(conn, ids["OLD"])
            assert old["status"] == "INACTIVE" and old["retention_hold"]
            await assert_generic_cleanup_rejected(old)
            await reject("G0", "NEW")
            await g.set_retention_hold(conn, ids["G0"], hold=True)
            await reject("G0", "NEW")  # retained but never previously ACTIVE
            await g.set_retention_hold(conn, ids["OLD"], hold=False)
            await reject("OLD", "NEW")
            await g.set_retention_hold(conn, ids["OLD"], hold=True)
            for status in ("BUILDING", "FAILED"):
                await g.set_generation_status(conn, ids["B"], status)
                for operation in ("CUTOVER", "ROLLBACK"):
                    await reject("B", "NEW", operation)
            await g.set_generation_status(conn, ids["B"], "CANDIDATE")
            await reject("B", "OLD", "CUTOVER", g.GenerationConflictError)
            assert (await switch("OLD", "NEW", "ROLLBACK"))["result"] == "APPLIED"
            assert await g.resolve_active_generation_id(conn, logical) == ids["OLD"]
            new = await g.get_generation(conn, ids["NEW"])
            assert new["status"] == "INACTIVE" and new["retention_hold"]
            await assert_generic_cleanup_rejected(new)
            await reject("OLD", "NEW", "ROLLBACK", g.GenerationConflictError)
            assert (await switch("OLD", "OLD", "ROLLBACK"))["result"] == "IDEMPOTENT"
            audit = await g.list_activation_audit(conn, logical)
            assert len(audit) == 3
            # Transaction timestamps can tie; verify edges, not timestamp ordering.
            by_edge = {(str(a["from_generation_id"]), str(a["to_generation_id"])): a for a in audit}
            for origin, target, op in [("OLD", "NEW", "CUTOVER"), ("NEW", "OLD", "ROLLBACK")]:
                a = by_edge[ids[origin], ids[target]]
                assert a["operation"] == op and a["result"] == "APPLIED"
                assert str(a["expected_generation_id"]) == ids[origin]
                assert a["created_at"] is not None
            # G0 becomes a real historical ACTIVE but is not the immediate predecessor.
            await g.set_generation_status(conn, ids["G0"], "CANDIDATE")
            await switch("G0", "OLD")
            await switch("B", "G0")
            await reject("OLD", "B")
            # Only G0 (immediate predecessor), not retained historical OLD, is eligible.
            assert (await switch("G0", "B", "ROLLBACK"))["result"] == "APPLIED"
            # Cross-document lookup must reject a generation absent from this logical id.
            with pytest.raises(g.GenerationPreconditionError, match="does not belong"):
                await g.activate_generation(conn, logical_document_id=logical,
                    expected_active_generation_id=ids["G0"], new_generation_id=str(uuid4()),
                    operation="ROLLBACK")
