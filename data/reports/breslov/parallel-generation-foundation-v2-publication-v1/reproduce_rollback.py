"""Offline reproduction using the unchanged local activation implementation.

Only persistence helpers are replaced with an in-memory SQL adapter. No service
connections, real documents, migrations, extraction or embedding calls occur.
Run from backend with its Python and PYTHONPATH=.
"""
import asyncio
import json
from unittest.mock import patch

from modules.library import generation as g


async def main():
    state = {"pointer": "OLD", "statuses": {"OLD": "ACTIVE", "NEW": "CANDIDATE"}}
    writes = []

    async def fetch_one(conn, sql, params):
        if "SELECT id FROM library_logical_documents" in sql:
            return {"id": "LOGICAL"}
        if "SELECT generation_id FROM library_logical_document_active_generations" in sql:
            return {"generation_id": state["pointer"]}
        if "SELECT * FROM library_document_generations" in sql:
            return {"id": params["id"], "status": state["statuses"][params["id"]], "source_sha256": "approved-source"}
        if "SELECT source_sha256 FROM library_logical_documents" in sql:
            return {"source_sha256": "approved-source"}
        raise AssertionError(f"Unmodelled read: {sql}")

    async def execute(conn, sql, params):
        writes.append(sql.strip())
        if "SET status='INACTIVE'" in sql:
            state["statuses"][params["id"]] = "INACTIVE"
        elif "SET status='ACTIVE'" in sql:
            state["statuses"][params["id"]] = "ACTIVE"
        elif "INSERT INTO library_logical_document_active_generations" in sql:
            state["pointer"] = params["generation"]
        elif "INSERT INTO library_generation_activation_audit" not in sql:
            raise AssertionError(f"Unmodelled write: {sql}")

    result = {"method": "OFFLINE_REAL_FUNCTION_WITH_IN_MEMORY_PERSISTENCE", "services_accessed": False}
    with patch.object(g, "fetch_one", fetch_one), patch.object(g, "execute", execute):
        cutover = await g.activate_generation(None, logical_document_id="LOGICAL", expected_active_generation_id="OLD", new_generation_id="NEW", operation=g.OPERATION_CUTOVER)
        result["cutover"] = cutover
        result["after_cutover"] = {"pointer": state["pointer"], "statuses": dict(state["statuses"])}
        writes_before = len(writes)
        try:
            rollback = await g.activate_generation(None, logical_document_id="LOGICAL", expected_active_generation_id="NEW", new_generation_id="OLD", operation=g.OPERATION_ROLLBACK)
            result["rollback"] = rollback
        except g.GenerationPreconditionError as exc:
            result["rollback"] = {"result": "REJECTED", "exception": type(exc).__name__, "message": str(exc)}
        result["rollback_writes"] = len(writes) - writes_before
        result["rollback_contract"] = "PASS" if state["pointer"] == "OLD" else "FAIL"
    print(json.dumps(result, indent=2))
    return 1 if result["rollback_contract"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
