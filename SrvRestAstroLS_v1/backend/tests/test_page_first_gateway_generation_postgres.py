"""Real gateway registration against immediate DEV FKs; synthetic, rolled back.

No extraction, embedding or Milvus calls. Declared regional fixture is an input
contract, not an extraction-quality claim. All SQL/binding and failure injection
is fixed here, shared by pre-freeze and final certification.
"""
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
import hashlib
import shutil

import pytest
from psycopg import AsyncConnection
from psycopg.errors import NotNullViolation
from psycopg.rows import dict_row

import globalVar as config
from modules.library import generation
from modules.library.content_manager_repository import ContentTenantContext
from modules.library.page_first_gateway import PostgresMilvusPageFirstGateway, E2EIsolationError, _uuid
from modules.library.page_first_pipeline import PageFirstIngestionRequest, document_from_certificates, ReconciliationResult
from tests.test_region_publication import certified_fixture

CURRENT_C = "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"
CURRENT_LOGICAL_C = "db200a31-b547-5668-d968-06d0ec36ad95"


class InjectedBeforeGeneration(RuntimeError):
    pass


class ObservedCursor:
    def __init__(self, cursor, pool):
        self.cursor, self.pool = cursor, pool

    async def __aenter__(self):
        await self.cursor.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.cursor.__aexit__(*args)

    async def execute(self, sql, params=None):
        statement = " ".join(sql.split())
        if statement.startswith("INSERT INTO library_document_generations"):
            # Verify parents using a real DB read BEFORE executing production SQL.
            logical, document, run = params[:3]
            row = await (await self.pool.conn.execute("""
                SELECT EXISTS(SELECT 1 FROM library_documents
                    WHERE id=%s AND logical_document_id=%s) AS link,
                       EXISTS(SELECT 1 FROM library_ingestion_runs_v2
                    WHERE run_id=%s AND document_id=%s) AS run
            """, (document, logical, run, document))).fetchone()
            assert row == {"link": True, "run": True}
            self.pool.parents_checked += 1
            if self.pool.failure == "before":
                raise InjectedBeforeGeneration("controlled after all parents, before generation")
            if self.pool.failure == "at":
                # Real INSERT rejection, not FK bypass: NOT NULL pipeline violation.
                params = (*params[:5], None, *params[6:])
        return await self.cursor.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class ObservedConnection:
    def __init__(self, pool):
        self.pool = pool

    def cursor(self, **kwargs):
        return ObservedCursor(self.pool.conn.cursor(**kwargs), self.pool)

    def transaction(self):
        return self.pool.conn.transaction()

    async def execute(self, *args, **kwargs):
        return await self.pool.conn.execute(*args, **kwargs)


class SingleConnectionPool:
    """Real nested transaction/savepoint, outer fixture always rolled back."""
    def __init__(self, conn, failure=None):
        self.conn, self.failure, self.parents_checked = conn, failure, 0

    @asynccontextmanager
    async def connection(self):
        yield ObservedConnection(self)


async def c_snapshot(conn):
    result = {}
    for table, column, identity in (
        ("library_documents", "id", CURRENT_C),
        ("library_ingestion_runs_v2", "document_id", CURRENT_C),
        ("library_logical_documents", "id", CURRENT_LOGICAL_C),
        ("library_document_generations", "logical_document_id", CURRENT_LOGICAL_C),
        ("library_logical_document_active_generations", "logical_document_id", CURRENT_LOGICAL_C),
        ("library_generation_activation_audit", "logical_document_id", CURRENT_LOGICAL_C),
    ):
        rows = await (await conn.execute(f"SELECT to_jsonb(t)::text AS row FROM {table} t WHERE {column}=%s ORDER BY to_jsonb(t)::text", (identity,))).fetchall()
        result[table] = hashlib.sha256(str(rows).encode()).hexdigest()
    return result


async def counts(conn, scope):
    row = await (await conn.execute("""
        SELECT (SELECT count(*) FROM library_documents WHERE knowledge_scope_id=%s) AS docs,
               (SELECT count(*) FROM library_logical_documents WHERE knowledge_scope_id=%s) AS logicals,
               (SELECT count(*) FROM library_document_generations g JOIN library_logical_documents l
                    ON l.id=g.logical_document_id WHERE l.knowledge_scope_id=%s) AS generations,
               (SELECT count(*) FROM library_ingestion_runs_v2 r JOIN library_documents d
                    ON d.id=r.document_id WHERE d.knowledge_scope_id=%s) AS runs,
               (SELECT count(*) FROM library_logical_document_active_generations p JOIN library_logical_documents l
                    ON l.id=p.logical_document_id WHERE l.knowledge_scope_id=%s) AS pointers
    """, (scope,) * 5)).fetchone()
    return row


async def run_synthetic(tmp_path: Path, failure=None):
    assert config.TEBAAI_ENV == "development" and not config.is_tebaai_production()
    assert config.POSTGRES_HOST in {"127.0.0.1", "localhost"} and config.POSTGRES_DB == "tebaai"
    conn = await AsyncConnection.connect(config.POSTGRES_DSN, row_factory=dict_row, autocommit=True, connect_timeout=5)
    scope, job, upload = uuid4(), uuid4(), uuid4()
    output = {"failure_control": failure, "scope_id": str(scope), "job_id": str(job), "upload_id": str(upload)}
    try:
        before = await c_snapshot(conn)
        async with conn.transaction(force_rollback=True):
            template = await (await conn.execute("SELECT organization_id,workspace_id,project_id FROM knowledge_scopes WHERE knowledge_scope_code='breslov_primary'")).fetchone()
            actor = (await (await conn.execute("SELECT id FROM users ORDER BY id LIMIT 1")).fetchone())["id"]
            assert template
            await conn.execute("""INSERT INTO knowledge_scopes(id,organization_id,workspace_id,project_id,
                knowledge_scope_code,name,scope_type,language_policy,status)
                VALUES(%s,%s,%s,%s,%s,'Gateway FK synthetic','bibliographic_corpus','es','active')""",
                (scope, template["organization_id"], template["workspace_id"], template["project_id"], str(scope)))
            source = tmp_path / f"synthetic-{scope}.txt"
            source.write_text(f"synthetic registration input {scope}")
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            await conn.execute("""INSERT INTO content_manager_uploads(id,filename,original_filename,size_bytes,sha256,
                organization_id,workspace_id,project_id,knowledge_scope_id,actor_user_id)
                VALUES(%s,'synthetic.txt','synthetic.txt',1,%s,%s,%s,%s,%s,%s)""",
                (upload, sha, template["organization_id"], template["workspace_id"], template["project_id"], scope, actor))
            await conn.execute("""INSERT INTO content_manager_jobs(id,upload_id,title,idempotency_key,
                organization_id,workspace_id,project_id,knowledge_scope_id,actor_user_id)
                VALUES(%s,%s,'Gateway FK synthetic',%s,%s,%s,%s,%s,%s)""",
                (job, upload, str(job), template["organization_id"], template["workspace_id"], template["project_id"], scope, actor))
            request = PageFirstIngestionRequest(upload, job, 1, source, sha, "Gateway FK synthetic", "es", None,
                "auto", "gateway_order_synthetic_v1", "not_called", "not_called",
                ContentTenantContext(**template, knowledge_scope_id=scope), actor, str(scope), "not_called")
            certificate = certified_fixture(("Synthetic gateway ordering input",), ("ACCEPTED",))
            certificate = replace(certificate,
                provenance=replace(certificate.provenance, source_sha256=sha),
                certificates=tuple(replace(c, document_sha=sha) for c in certificate.certificates))
            extracted = document_from_certificates((certificate,), "es")
            document = _uuid(scope, f"{sha}:{request.pipeline_version}")
            assert str(document) != CURRENT_C and str(scope) != CURRENT_LOGICAL_C
            output["document_id"] = str(document)
            pool = SingleConnectionPool(conn, failure)
            gateway = PostgresMilvusPageFirstGateway(pool)
            if failure:
                with pytest.raises(InjectedBeforeGeneration if failure == "before" else NotNullViolation):
                    await gateway.persist_document_and_pages(request, extracted)
                assert pool.parents_checked == 1
                assert await counts(conn, scope) == dict(docs=0, logicals=0, generations=0, runs=0, pointers=0)
                output["failure_rollback_counts"] = await counts(conn, scope)
                # Retry SAME attempt after failed savepoint: safe, no artifacts.
                pool.failure = None
            persisted = await gateway.persist_document_and_pages(request, extracted)
            created = await generation.get_generation_by_document(conn, document)
            assert created and created["status"] == "BUILDING"
            assert str(created["run_id"]) == str(persisted.ingestion_run_id)
            assert await generation.resolve_active_generation_id(conn, created["logical_document_id"]) is None
            output.update(generation_id=str(created["id"]), logical_document_id=str(created["logical_document_id"]),
                          run_id=str(created["run_id"]), initial_status=created["status"], run_fk="PASS", document_logical_fk="PASS")
            first_counts = await counts(conn, scope)
            assert first_counts == dict(docs=1, logicals=1, generations=1, runs=1, pointers=0)
            # Existing safety policy rejects re-ownership, not a resume contract.
            with pytest.raises(E2EIsolationError, match="already exists"):
                await gateway.persist_document_and_pages(request, extracted)
            assert await counts(conn, scope) == first_counts
            output["retry"] = {"same_attempt": "REJECTED_SAFELY_EXISTING_CONTRACT", "duplicate_logicals": 0,
                               "duplicate_generations": 0, "duplicate_runs": 0, "invalid_pointers": 0}
            # A new pipeline is the supported next physical-generation identity.
            next_request = replace(request, pipeline_version="gateway_order_synthetic_v2")
            second = await gateway.persist_document_and_pages(next_request, extracted)
            next_gen = await generation.get_generation_by_document(conn, second.document_id)
            assert next_gen["id"] != created["id"]
            assert next_gen["logical_document_id"] == created["logical_document_id"]
            assert next_gen["status"] == "BUILDING"
            assert await counts(conn, scope) == dict(docs=2, logicals=1, generations=2, runs=2, pointers=0)
            assert not await generation.resolve_active_document_ids(conn, document_ids=[str(document), str(second.document_id)])
            # Run unchanged production completion with source storage isolated in
            # the fixture directory (source durability is not this gate's claim).
            def isolated_source(path, document_id, expected_sha):
                assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha
                destination = tmp_path / f"durable-{document_id}.txt"
                shutil.copyfile(path, destination)
                return destination

            reconciliation = ReconciliationResult(request.job_id, request.attempt_number,
                second.document_id, 0, 0, 0, 0, (), (), (), ())
            with patch("modules.library.page_first_gateway.preserve_source", isolated_source):
                await gateway.finalize(next_request, second, reconciliation, extracted)
            completed = await generation.get_generation_by_document(conn, second.document_id)
            assert completed["status"] == "CANDIDATE"
            completed_run = await (await conn.execute("SELECT status FROM library_ingestion_runs_v2 WHERE run_id=%s", (second.ingestion_run_id,))).fetchone()
            assert completed_run["status"] == "completed"
            assert not await generation.resolve_active_document_ids(conn, document_ids=[str(document), str(second.document_id)])
            assert (await counts(conn, scope))["pointers"] == 0
            output["completion"] = {"run_status": "completed", "generation_status": "CANDIDATE", "normal_authority": False}
            output["next_generation"] = {"same_logical": True, "distinct_generation": True, "active_visibility_theft": False}
            output["parents_checked_before_generation"] = pool.parents_checked
            output["fk_errors"] = 0
            output["binding_errors"] = 0
        after = await c_snapshot(conn)
        assert before == after
        output["current_c_unchanged"] = True
        output["current_c_before"] = before
        output["current_c_after"] = after
        output["cleanup"] = await counts(conn, scope)
        assert output["cleanup"] == dict(docs=0, logicals=0, generations=0, runs=0, pointers=0)
        assert not await (await conn.execute("SELECT id FROM knowledge_scopes WHERE id=%s", (scope,))).fetchone()
        output["result"] = "PASS"
        return output
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "before", "at"])
async def test_real_gateway_fk_retry_failure_cleanup(tmp_path, failure):
    await run_synthetic(tmp_path, failure)
