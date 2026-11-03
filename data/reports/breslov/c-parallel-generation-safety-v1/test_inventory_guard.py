"""Static safety gates for the two read-only service-connected report probes."""
import ast
from pathlib import Path


SCRIPT = Path(__file__).with_name("inventory_readonly.py")


def test_inventory_runner_has_no_ingestion_lifecycle_or_mutator_imports():
    tree = ast.parse(SCRIPT.read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert all(not (name or "").startswith(("modules.library", "infrastructure.postgres.pool")) for name in imports)
    source = SCRIPT.read_text()
    assert "TARGET_C_DOCUMENT_ID = 'ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa'" in source
    assert "assert did == TARGET_C_DOCUMENT_ID" in source
    assert "default_transaction_read_only=on" in source
    assert "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in source
    assert "assert sql.lstrip().upper().startswith('SELECT ')" in source
    assert "g.TEBAAI_ENV == 'development'" in source
    assert "g.POSTGRES_HOST in {'127.0.0.1', 'localhost'}" in source
    assert "g.MILVUS_HOST in {'127.0.0.1', 'localhost'}" in source
    assert "assert not any((OUT /" in source  # don't overwrite sealed inventories


def test_milvus_calls_are_exact_read_only_allowlist():
    tree = ast.parse(SCRIPT.read_text())
    calls = {node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "client"}
    assert calls == {"list_collections", "describe_collection", "get_load_state",
                     "get_collection_stats", "query_iterator", "close"}


def test_postgres_execute_cannot_bypass_select_wrapper():
    tree = ast.parse(SCRIPT.read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name)
             and node.func.value.id == "conn" and node.func.attr == "execute"]
    assert len(calls) == 2
    args = [node.args[0] for node in calls]
    assert any(isinstance(arg, ast.Name) and arg.id == "sql" for arg in args)
    constants = [arg.value for arg in args if isinstance(arg, ast.Constant)]
    assert constants == ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"]


def test_supplemental_schema_probe_is_read_only_and_local_dev():
    source = SCRIPT.with_name("indexes_readonly.py").read_text()
    tree = ast.parse(source)
    assert "default_transaction_read_only=on" in source
    assert 'g.TEBAAI_ENV == "development"' in source
    assert 'g.POSTGRES_HOST in {"127.0.0.1", "localhost"}' in source
    sql = next(n.value.value for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "SQL" for t in n.targets))
    assert sql.startswith("SELECT ") and "FROM pg_indexes" in sql
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
             and n.func.value.id == "conn"}
    assert calls == {"execute", "rollback"}
    assert "modules.library" not in source
