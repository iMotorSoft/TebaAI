"""Freeze durable bytes, source metadata, harness and expected outcomes."""
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

import psycopg

import globalVar as config
from modules.library.durable_source import source_path

OUT = Path(__file__).resolve().parent
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
C_LOGICAL = UUID("db200a31-b547-5668-d968-06d0ec36ad95")
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
EXPECTED_SIZE = 4550267
EXPECTED_PAGES = 284

FROZEN_ARTIFACTS = [
    "approved-source-verification.json",
    "baseline-git-state.json",
    "durable-storage-contract.json",
    "source-metadata-ownership.json",
    "current-c-before.json",
    "c-content-immutability-contract.json",
    "forbidden-operation-monitor.json",
    "restoration-rollback-plan.json",
    "durable-file-before-metadata.json",
    "database-write-accounting.json",
    "filesystem-write-accounting.json",
    "path-safety.json",
    "permissions.json",
    "idempotency-results.json",
    "wrong-source-negative-control.json",
    "current-c-after.json",
    "current-c-immutability-comparison.json",
    "retrieval-smoke.json",
    "viewer-source-results.json",
    "restoration-run.json",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


async def db_metadata() -> dict:
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, logical_document_id, status, source_path, source_uri,
                       source_filename, source_sha256, source_size_bytes,
                       source_mime_type, updated_at
                FROM library_documents WHERE id=%s
                """,
                (C_DOCUMENT,),
            )
            document = await cur.fetchone()
            await cur.execute(
                "SELECT generation_id::text AS generation_id, operation FROM "
                "library_logical_document_active_generations WHERE logical_document_id=%s",
                (C_LOGICAL,),
            )
            pointer = await cur.fetchone()
    return {"document": document, "active_pointer": pointer}


def main() -> None:
    durable = source_path(C_DOCUMENT)
    info = durable.stat()
    metadata = asyncio.run(db_metadata())
    frozen_at = datetime.now(timezone.utc).isoformat()

    harness = sorted(p.name for p in OUT.glob("*.py"))
    hashes = {}
    for name in harness + FROZEN_ARTIFACTS:
        path = OUT / name
        if path.is_file():
            hashes[f"report/{name}"] = sha256_file(path)
    hashes["durable/original.pdf"] = sha256_file(durable)
    hashes["external/approved.pdf"] = sha256_file(
        Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
    )

    manifest = {
        "frozen_at": frozen_at,
        "document_id": str(C_DOCUMENT),
        "logical_document_id": str(C_LOGICAL),
        "durable_file": {
            "path": str(durable),
            "sha256": hashes["durable/original.pdf"],
            "size_bytes": info.st_size,
            "pages": EXPECTED_PAGES,
            "mtime_ns": info.st_mtime_ns,
            "inode": info.st_ino,
        },
        "source_metadata": metadata,
        "harness_scripts": [f"report/{name}" for name in harness],
        "frozen_artifacts": [f"report/{name}" for name in FROZEN_ARTIFACTS if (OUT / name).is_file()],
        "expected_outcomes": {
            "external_sha256": EXPECTED_SHA,
            "durable_sha256": EXPECTED_SHA,
            "served_sha256": EXPECTED_SHA,
            "size_bytes": EXPECTED_SIZE,
            "pages": EXPECTED_PAGES,
            "chunks": 942,
            "vectors": 942,
            "active_generation": metadata["active_pointer"]["generation_id"],
            "authenticated_status": 200,
            "unauthenticated_status_in": [401, 403],
            "source_path_equals_canonical_durable": True,
            "product_code_changes_by_gate": 0,
        },
        "post_freeze_rule": (
            "no durable-file replacement, no metadata edits, no expected-result changes, "
            "no verification-harness changes; otherwise the gate is INVALID"
        ),
    }
    (OUT / "frozen-manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    (OUT / "frozen-hashes.txt").write_text(
        "# frozen hashes - do not edit after freeze\n"
        + "\n".join(f"{digest}  {name}" for name, digest in sorted(hashes.items()))
        + "\n"
    )
    (OUT / "frozen-at.json").write_text(json.dumps({
        "frozen_at": frozen_at,
        "rule": manifest["post_freeze_rule"],
        "frozen_entries": len(hashes),
    }, indent=2) + "\n")
    print(json.dumps({"frozen_at": frozen_at, "entries": len(hashes),
                      "durable_sha": hashes["durable/original.pdf"]}))


if __name__ == "__main__":
    main()
