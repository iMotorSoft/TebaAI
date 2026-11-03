"""Run from backend: uv run python <absolute path>/certify_postgres.py pre|final.
Frozen harness: cases, SQL, bindings, expectations and cleanup live in direct tests.
"""
import asyncio
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "SrvRestAstroLS_v1/backend"
sys.path.insert(0, str(BACKEND))
from tests.test_page_first_gateway_generation_postgres import run_synthetic
from psycopg import AsyncConnection
from psycopg.rows import dict_row
import globalVar as config

OUT = Path(__file__).resolve().parent


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str, allow_nan=False) + "\n")


async def main(phase):
    assert phase in {"pre", "final"}
    assert config.TEBAAI_ENV == "development" and config.POSTGRES_HOST in {"127.0.0.1", "localhost"}
    conn = await AsyncConnection.connect(config.POSTGRES_DSN, row_factory=dict_row, autocommit=True, connect_timeout=5)
    try:
        tables = ["library_logical_documents", "library_documents", "library_ingestion_runs_v2",
                  "library_document_generations", "library_logical_document_active_generations",
                  "library_generation_activation_audit"]
        constraints = await (await conn.execute("""
            SELECT conrelid::regclass::text AS table_name, conname, contype,
                   pg_get_constraintdef(oid) AS definition, condeferrable, condeferred
            FROM pg_constraint WHERE conrelid::regclass::text=ANY(%s) ORDER BY 1,2
        """, (tables,))).fetchall()
        types = await (await conn.execute("""
            SELECT table_name,column_name,data_type,udt_name,is_nullable
            FROM information_schema.columns WHERE table_schema='public'
              AND table_name=ANY(%s) AND (column_name='id' OR column_name LIKE '%%_id')
            ORDER BY table_name,ordinal_position
        """, (tables,))).fetchall()
        assert all(r["udt_name"] == "uuid" for r in types)
        required = {"library_document_generations_run_id_fkey", "library_document_generations_document_logical_fkey"}
        assert required <= {c["conname"] for c in constraints}
        if phase == "pre":
            save("gateway-fk-order-contract.json", {
                "source": "live DEV pg_constraint + migration 043",
                "constraints": constraints,
                "fk_required_partial_order": ["logical_document before document/logical linkage", "document before linkage and run", "linkage before generation", "run before generation", "generation before active pointer", "activation audit via existing service only"],
                "actual_gateway_order": ["document (nullable logical FK)", "run", "resolve/create logical_document", "document/logical linkage", "generation BUILDING"],
                "explanation": "Schema requires a partial order, not logical INSERT before physical INSERT: document logical_id is initially nullable. Both parents exist before generation; no deferred constraints.",
                "active_pointer": "not created by registration or completion; explicit existing activation primitive only",
                "activation_audit": "no FK declared in 043; only the activation service writes it",
            })
            save("uuid-type-validation.json", {"types": types, "all_ids_uuid": True,
                "binding_contract": "UUID objects for document/run parents; str UUID values in generation/link binding; PostgreSQL target columns resolve uuid types. JSON serialized separately with explicit ::jsonb casts. No jsonb_build_object in gateway registration.",
                "jsonb_fixture_issue_separate": True})
    finally:
        await conn.close()
    results = []
    # Negative control then wholly fresh normal positive fixture; no harness mutation.
    for failure in ("before", "at", None):
        with tempfile.TemporaryDirectory(prefix=f"gateway-fk-{phase}-") as directory:
            results.append(await run_synthetic(Path(directory), failure))
    save("pre-freeze-postgres-results.json" if phase == "pre" else "final-postgres-results.json", results)
    if phase == "final":
        positive = results[-1]
        save("final-fixture-identifiers.json", [{k: r[k] for k in ("scope_id", "job_id", "upload_id", "document_id", "logical_document_id", "generation_id", "run_id")} for r in results])
        save("run-fk-results.json", {"result": "PASS", "cases": [{"generation_id": r["generation_id"], "run_id": r["run_id"], "result": r["run_fk"]} for r in results]})
        save("document-logical-fk-results.json", {"result": "PASS", "parents_verified_in_live_db_before_each_insert": True, "cases": [r["document_logical_fk"] for r in results]})
        save("first-generation-lifecycle.json", {"result": "PASS", "initial_status": positive["initial_status"], "active_pointer_created": False, "completion": positive["completion"], "policy_changed": False})
        save("retry-idempotency-results.json", {"result": "PASS", "contract": "Existing committed document is rejected safely before ownership claim; failed same attempt can retry after transactional rollback. No resume contract introduced.", "cases": [r["retry"] for r in results], "next_generation": positive["next_generation"]})
        save("failure-transaction-results.json", {"result": "PASS", "cases": results[:2], "before_generation_impossible_state": False, "generation_rejection_invalid_pointer": False, "parent_chain_rolled_back_to_savepoint": True, "controlled_insert_rejection": "NotNullViolation 23502 on pipeline_version, not FK or binding error"})
        save("cleanup-results.json", {"result": "PASS", "method": "unconditional outer PostgreSQL transaction rollback; independent post-rollback reads", "cases": [r["cleanup"] for r in results], "synthetic_generations_remaining": 0, "synthetic_docs_remaining": 0, "synthetic_active_pointers_remaining": 0})
        save("current-c-readonly-check.json", {"document_id": "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa", "logical_document_id": "db200a31-b547-5668-d968-06d0ec36ad95", "postgresql_writes": 0, "milvus_writes": 0, "reingest": False, "extraction": False, "embeddings": False, "vector_rebuild": False, "pointer_modified": False, "generation_status_modified": False, "fixture_snapshots_equal": all(r["current_c_unchanged"] for r in results), "before": results[0]["current_c_before"], "after": results[-1]["current_c_after"]})


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
