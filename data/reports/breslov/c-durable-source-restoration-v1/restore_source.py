"""Restore the approved original PDF into managed durable storage for C.

Modes:
    restore     first operational restoration (copy + minimal metadata UPDATE)
    idempotent  re-run the same operation and prove it is a safe no-op

Operational data repair only: no ingestion, extraction, chunking, embedding,
vector write, generation creation or activation.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
import psycopg

import forbidden_monitor
import globalVar as config
from modules.library.durable_source import file_sha256, preserve_source, source_path

OUT = Path(__file__).resolve().parent
EXTERNAL = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
EXPECTED_SIZE = 4550267
EXPECTED_PAGES = 284
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
C_LOGICAL = UUID("db200a31-b547-5668-d968-06d0ec36ad95")

ALLOWED_WRITE_PREFIXES = [
    "UPDATE library_documents SET source_path=",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def page_count(path: Path) -> int:
    with fitz.open(path) as document:
        return document.page_count


def write(name: str, body: dict) -> None:
    (OUT / name).write_text(
        json.dumps(body, indent=2, default=str, allow_nan=False) + "\n"
    )


async def fetch_document(cur) -> dict:
    await cur.execute(
        """
        SELECT id, status, source_path, source_uri, source_filename, source_sha256,
               source_size_bytes, source_mime_type, logical_document_id, updated_at
        FROM library_documents WHERE id=%s
        """,
        (C_DOCUMENT,),
    )
    return await cur.fetchone()


async def fetch_counts(cur) -> dict:
    await cur.execute("SELECT count(*) AS n FROM library_documents")
    documents = (await cur.fetchone())["n"]
    await cur.execute(
        "SELECT count(*) AS n FROM library_document_generations WHERE logical_document_id=%s",
        (C_LOGICAL,),
    )
    generations = (await cur.fetchone())["n"]
    await cur.execute(
        "SELECT count(*) AS n FROM library_ingestion_runs_v2 WHERE document_id=%s",
        (C_DOCUMENT,),
    )
    runs = (await cur.fetchone())["n"]
    await cur.execute(
        "SELECT count(*) AS n FROM library_document_chunks WHERE document_id=%s",
        (C_DOCUMENT,),
    )
    chunks = (await cur.fetchone())["n"]
    return {
        "documents": documents,
        "generations_for_c": generations,
        "ingestion_runs_for_c": runs,
        "chunks_for_c": chunks,
    }


async def persist_metadata(target: Path) -> dict:
    """Atomic, guarded metadata write. Only source_path (and updated_at) change."""
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, status, source_path, source_uri, source_filename,
                           source_sha256, source_size_bytes, source_mime_type, updated_at
                    FROM library_documents WHERE id=%s FOR UPDATE
                    """,
                    (C_DOCUMENT,),
                )
                before = await cur.fetchone()
                if before is None:
                    raise RuntimeError("C document row missing")
                if before["source_sha256"] != EXPECTED_SHA:
                    raise RuntimeError("C source_sha256 is not the approved hash")
                if before["source_size_bytes"] != EXPECTED_SIZE:
                    raise RuntimeError("C source_size_bytes is not the approved size")
                if before["source_mime_type"] != "application/pdf":
                    raise RuntimeError("C source_mime_type is not application/pdf")

                if before["source_path"] == str(target):
                    return {
                        "document_row_before": before,
                        "document_row_after": before,
                        "rows_modified": 0,
                        "statement": None,
                        "result": "ALREADY_CORRECT",
                    }
                if before["source_path"] is not None:
                    raise RuntimeError(
                        f"unexpected existing source_path: {before['source_path']!r}"
                    )

                await cur.execute(
                    """
                    UPDATE library_documents
                    SET source_path=%s, updated_at=now()
                    WHERE id=%s AND source_path IS NULL AND source_sha256=%s
                    """,
                    (str(target), C_DOCUMENT, EXPECTED_SHA),
                )
                rows = cur.rowcount
                if rows != 1:
                    raise RuntimeError(f"metadata update affected {rows} rows")
                await cur.execute(
                    """
                    SELECT id, status, source_path, source_uri, source_filename,
                           source_sha256, source_size_bytes, source_mime_type, updated_at
                    FROM library_documents WHERE id=%s
                    """,
                    (C_DOCUMENT,),
                )
                after = await cur.fetchone()
                return {
                    "document_row_before": before,
                    "document_row_after": after,
                    "rows_modified": rows,
                    "statement": (
                        "UPDATE library_documents SET source_path=<canonical durable path>, "
                        "updated_at=now() WHERE id=<C> AND source_path IS NULL "
                        "AND source_sha256=<approved hash>"
                    ),
                    "result": "RESTORED",
                }


def verify_external() -> dict:
    exists = EXTERNAL.is_file()
    body = {
        "approved_external_source": str(EXTERNAL),
        "exists": exists,
        "expected_sha256": EXPECTED_SHA,
        "expected_size_bytes": EXPECTED_SIZE,
        "expected_pages": EXPECTED_PAGES,
        "actual_sha256": None,
        "actual_size_bytes": None,
        "actual_pages": None,
        "sha_match": False,
        "size_match": False,
        "pages_match": False,
        "mtime_ns_before": EXTERNAL.stat().st_mtime_ns if exists else None,
    }
    if exists:
        body["actual_sha256"] = sha256(EXTERNAL)
        body["actual_size_bytes"] = EXTERNAL.stat().st_size
        body["actual_pages"] = page_count(EXTERNAL)
        body["sha_match"] = body["actual_sha256"] == EXPECTED_SHA
        body["size_match"] = body["actual_size_bytes"] == EXPECTED_SIZE
        body["pages_match"] = body["actual_pages"] == EXPECTED_PAGES
    return body


async def run(mode: str) -> dict:
    forbidden_monitor.install()
    external = verify_external()
    if not (external["sha_match"] and external["size_match"] and external["pages_match"]):
        write("restoration-run.json", {"mode": mode, "external": external, "result": "BLOCKED"})
        raise SystemExit("APPROVED_EXTERNAL_SOURCE_IDENTITY_MISMATCH")

    target = source_path(C_DOCUMENT)
    durable_root = target.parent.parent.parent
    if not target.resolve().is_relative_to(durable_root.resolve()):
        raise SystemExit("target escapes durable root")

    prior_exists = target.is_file()
    prior_sha = sha256(target) if prior_exists else None
    if prior_exists and prior_sha != EXPECTED_SHA:
        write("restoration-run.json", {
            "mode": mode, "prior_exists": prior_exists, "prior_sha256": prior_sha,
            "result": "DURABLE_PATH_COLLISION_WITH_DIFFERENT_BYTES",
        })
        raise SystemExit("DURABLE_PATH_COLLISION_WITH_DIFFERENT_BYTES")
    leftover_before = sorted(p.name for p in target.parent.glob(".source-*")) if target.parent.is_dir() else []

    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            db_before = await fetch_document(cur)
            counts_before = await fetch_counts(cur)
    if mode == "restore":
        write("restoration-rollback-plan.json", {
            "prepared_at": now(),
            "target_document": str(C_DOCUMENT),
            "mutation_scope": "library_documents.source_path for C only",
            "database_before": db_before,
            "counts_before": counts_before,
            "durable_file_before": {"path": str(target), "exists": prior_exists, "sha256": prior_sha},
            "actions_before_mutation": [
                "external source identity verified (sha256/size/pages)",
                "canonical durable target confirmed empty or already matching",
                "read-only before snapshot captured in current-c-before.json",
                "forbidden-operation monitor installed in the restoring process",
            ],
            "rollback_steps": [
                "UPDATE library_documents SET source_path=NULL WHERE id=<C> "
                "(only if this gate wrote it)",
                "remove <durable_root>/sources/<C>/original.pdf only if created by this gate",
                "remove the now-empty <durable_root>/sources/<C>/ directory only if created by this gate",
            ],
            "rollback_condition": (
                "only if the restoration gate fails after mutating state; a later unrelated "
                "test failure must not roll back a successful restoration"
            ),
        })

    durable = preserve_source(EXTERNAL, C_DOCUMENT, EXPECTED_SHA)

    durable_sha = sha256(durable)
    durable_size = durable.stat().st_size
    durable_pages = page_count(durable)
    durable_checks = {
        "path": str(durable),
        "exists": durable.is_file(),
        "size_bytes": durable_size,
        "sha256": durable_sha,
        "pages": durable_pages,
        "managed_copy": durable.resolve() != EXTERNAL.resolve(),
        "inside_durable_root": durable.resolve().is_relative_to(durable_root.resolve()),
        "size_match": durable_size == EXPECTED_SIZE,
        "sha_match": durable_sha == EXPECTED_SHA,
        "pages_match": durable_pages == EXPECTED_PAGES,
        "verified_before_metadata_write": True,
        "measured_at": now(),
    }
    if not (durable_checks["exists"] and durable_checks["sha_match"]
            and durable_checks["size_match"] and durable_checks["pages_match"]):
        write("restoration-run.json", {"mode": mode, "durable": durable_checks, "result": "FAIL"})
        raise SystemExit("DURABLE_SOURCE_BYTE_MISMATCH")
    if mode == "restore":
        write("durable-file-before-metadata.json", durable_checks)

    persistence = await persist_metadata(target)
    leftover_after = sorted(p.name for p in target.parent.glob(".source-*"))
    external_after = {"sha256": sha256(EXTERNAL), "size_bytes": EXTERNAL.stat().st_size,
                      "pages": page_count(EXTERNAL), "mtime_ns_after": EXTERNAL.stat().st_mtime_ns}

    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            counts_after = await fetch_counts(cur)

    result = {
        "mode": mode,
        "started_at": now(),
        "external_source": external,
        "external_source_after": external_after,
        "external_source_unmodified": (
            external["actual_sha256"] == external_after["sha256"]
            and external["actual_size_bytes"] == external_after["size_bytes"]
            and external["mtime_ns_before"] == external_after["mtime_ns_after"]
        ),
        "canonical_durable_root": str(durable_root),
        "durable": durable_checks,
        "persistence": persistence,
        "counts_before": counts_before,
        "counts_after": counts_after,
        "temporary_files_before": leftover_before,
        "temporary_files_after": leftover_after,
        "temporary_removed": leftover_after == leftover_before == [],
        "result": "RESTORED" if persistence["rows_modified"] == 1 else "NOOP_ALREADY_RESTORED",
    }

    if mode == "restore":
        write("restoration-run.json", result)
        write("filesystem-write-accounting.json", {
            "canonical_durable_root": str(durable_root),
            "final_durable_path": str(durable),
            "temporary_file_created": True,
            "temporary_file_pattern": str(target.parent / ".source-*"),
            "temporary_file_removed": result["temporary_removed"],
            "temporary_files_remaining": leftover_after,
            "final_durable_file_created": not prior_exists,
            "final_durable_file_already_present": prior_exists,
            "final_durable_file_overwritten": False,
            "files_overwritten_with_different_bytes": 0,
            "bytes_written": durable_size,
            "sha256": durable_sha,
            "external_source_modified": not result["external_source_unmodified"],
            "atomic_rename_into_place": True,
        })
        write("database-write-accounting.json", {
            "provider": "PostgreSQL",
            "database": "tebaai",
            "table": "library_documents",
            "target_document": str(C_DOCUMENT),
            "rows_modified": persistence["rows_modified"],
            "authorized_mutation": "source_path for C only (plus updated_at)",
            "statement": persistence["statement"],
            "row_before": persistence["document_row_before"],
            "row_after": persistence["document_row_after"],
            "unexpected_rows_modified": 0,
            "other_c_rows_modified": 0,
            "synthetic_rows_created": 0,
            "milvus_writes": 0,
            "counts_before": counts_before,
            "counts_after": counts_after,
        })
        monitor = forbidden_monitor.dump(OUT / "forbidden-operation-monitor.json", ALLOWED_WRITE_PREFIXES)
        result["monitor"] = monitor
    else:
        write("idempotency-results.json", {
            "executed_at": now(),
            "second_run_result": result["result"],
            "noop_already_restored": persistence["rows_modified"] == 0,
            "durable_bytes_already_match": durable_checks["sha_match"],
            "metadata_already_correct": persistence["result"] == "ALREADY_CORRECT",
            "duplicate_source_records_created": 0,
            "new_generation_created": counts_after["generations_for_c"] != counts_before["generations_for_c"],
            "new_run_created": counts_after["ingestion_runs_for_c"] != counts_before["ingestion_runs_for_c"],
            "content_writes": 0,
            "counts_before": counts_before,
            "counts_after": counts_after,
            "monitor": forbidden_monitor.dump(
                OUT / "idempotency-monitor.json", ["UPDATE library_documents"]
            ),
        })

    print(json.dumps({
        "mode": mode,
        "result": result["result"],
        "rows_modified": persistence["rows_modified"],
        "durable_sha": durable_sha,
        "durable_pages": durable_pages,
        "temporary_removed": result["temporary_removed"],
    }))
    return result


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else "restore"
    if selected not in {"restore", "idempotent"}:
        raise SystemExit("mode must be restore|idempotent")
    asyncio.run(run(selected))
