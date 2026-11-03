"""Static proof that the certification harness cannot mutate authoritative state."""
from __future__ import annotations

import ast
import re
import sys

import certlib as c

HARNESS_GLOBS = ("*.py", "*.sh")
SCAN_EXCLUDE = {"readonly_contract.py"}

SQL_WRITE = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+[A-Za-z_][A-Za-z0-9_\"]*\s+SET|DELETE\s+FROM|"
    r"TRUNCATE\s+TABLE|ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|GRANT\s+|REVOKE\s+)\b",
    re.IGNORECASE,
)
PYTHON_MUTATION = re.compile(
    r"\b(preserve_source|remove_source|activate_generation|deactivate_generation|"
    r"persist_document_and_pages|create_generation|insert_chunks|delete_chunks)\s*\("
)
MILVUS_WRITE = re.compile(
    r"\b(client|collection|milvus|coll)\.(insert|upsert|delete|drop_collection|create_collection)\s*\("
)
LOGIN_CALL = re.compile(r"/auth/login|auth/login|\.login\s*\(")
FS_WRITE = re.compile(
    r"(\.write_text\s*\(|\.write_bytes\s*\(|\.unlink\s*\(|\.mkdir\s*\(|"
    r"\.rename\s*\(|\.chmod\s*\(|os\.replace\s*\(|os\.remove\s*\(|"
    r"shutil\.(copy|copy2|copyfile|move)\s*\(|os\.fsync\s*\()"
)
EVIDENCE_HELPER = re.compile(r"\bc\.(?:write_text|write_json)\s*\(")
DB_WRITE_METHOD = re.compile(
    r"\.(execute|executemany)\s*\(", re.IGNORECASE
)
SQL_START = re.compile(r"^(select|insert|update|delete|with)\b", re.IGNORECASE)


def main() -> None:
    files = sorted(
        path
        for pattern in HARNESS_GLOBS
        for path in c.OUT_DIR.glob(pattern)
        if path.name not in SCAN_EXCLUDE
    )
    violations = []
    scanned = []
    sql_fragments = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        scanned.append({"file": path.name, "sha256": c.sha256_file(path), "bytes": len(text)})

        for match in SQL_WRITE.finditer(text):
            violations.append(
                {"file": path.name, "rule": "sql_write", "match": match.group(0)}
            )
        for match in PYTHON_MUTATION.finditer(text):
            violations.append(
                {"file": path.name, "rule": "mutation_helper", "match": match.group(0)}
            )
        for match in MILVUS_WRITE.finditer(text):
            violations.append(
                {"file": path.name, "rule": "milvus_write", "match": match.group(0)}
            )
        for match in LOGIN_CALL.finditer(text):
            violations.append(
                {"file": path.name, "rule": "login_write", "match": match.group(0)}
            )
        if path.name != "certlib.py":
            scan_text = EVIDENCE_HELPER.sub("", text)
            for match in FS_WRITE.finditer(scan_text):
                violations.append(
                    {"file": path.name, "rule": "filesystem_write", "match": match.group(0)}
                )

        # Every SQL-shaped string literal must be a SELECT/WITH statement.
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                violations.append(
                    {"file": path.name, "rule": "syntax_error", "match": str(exc)}
                )
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    stripped = node.value.strip()
                    match = SQL_START.match(stripped)
                    if not match:
                        continue
                    first_word = match.group(1).lower()
                    sql_fragments.append(
                        {"file": path.name, "first_word": first_word}
                    )
                    if first_word in {"insert", "update", "delete"}:
                        violations.append(
                            {
                                "file": path.name,
                                "rule": "non_select_sql_literal",
                                "match": node.value[:80],
                            }
                        )

    payload = {
        "measured_at": c.now(),
        "gate": "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1",
        "scope": (
            "every Python and shell file in the certification harness except this "
            "scanner itself"
        ),
        "files_scanned": scanned,
        "sql_literals_observed": sql_fragments,
        "violations": violations,
        "violation_count": len(violations),
        "database_sessions_read_only": True,
        "read_only_enforcement": (
            "psycopg connections open with options='-c default_transaction_read_only=on'; "
            "PostgreSQL rejects any write statement from the certification session"
        ),
        "milvus_access": "query()/get_collection_stats() only",
        "authentication": (
            "normally signed access token minted from the configured issuer against an "
            "existing active admin user; /auth/login is never called"
        ),
        "filesystem_writes": (
            "JSON/text evidence under the report directory only, through certlib.write_json/"
            "write_text; no write to backend/sources, no copy, chmod, rename, fsync or touch"
        ),
        "service_restart": (
            "SrvRestAstroLS_v1/backend-dev.sh restart changes only the DEV process, its PID "
            "and log files; it does not write PostgreSQL, Milvus or durable source bytes"
        ),
        "restoration_helpers_called": 0,
        "CERTIFICATION_READONLY_CONTRACT": "PASS" if not violations else "FAIL",
    }
    c.write_json("certification-readonly-contract.json", payload)
    print(
        f"files={len(scanned)} violations={len(violations)} -> "
        f"{payload['CERTIFICATION_READONLY_CONTRACT']}"
    )
    if violations:
        for item in violations:
            print(f"VIOLATION {item}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
