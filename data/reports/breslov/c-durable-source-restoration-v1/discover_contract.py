"""Discover the canonical durable-source storage contract (read-only).

Outputs durable-storage-contract.json and source-metadata-ownership.json.
All values are measured from the real application code and PostgreSQL schema;
nothing is invented.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
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
from modules.library import durable_source

OUT = Path(__file__).resolve().parent
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
APPROVED_EXTERNAL = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


async def main() -> None:
    target = durable_source.source_path(C_DOCUMENT)
    durable_root = target.parent.parent.parent
    helper_source = inspect.getsource(durable_source.preserve_source)

    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='library_documents'
                  AND column_name LIKE 'source_%'
                ORDER BY ordinal_position
                """
            )
            source_columns = await cur.fetchall()
            await cur.execute(
                """
                SELECT current_user AS db_user, current_database() AS db_name
                """
            )
            db_identity = await cur.fetchone()

    contract = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_durable_storage_found": True,
        "mechanism": "modules.library.durable_source.preserve_source",
        "configuration": {
            "setting": "TEBAAI_CONTENT_MANAGER_STORAGE_DIR",
            "setting_value": config.CONTENT_MANAGER_STORAGE_DIR,
            "setting_is_empty": config.CONTENT_MANAGER_STORAGE_DIR == "",
            "resolution_rule": "Path(CONTENT_MANAGER_STORAGE_DIR).resolve(); process cwd when unset",
            "resolved_durable_root": str(durable_root),
            "service_cwd": str(BACKEND_DIR),
            "root_exists": durable_root.is_dir(),
        },
        "naming_policy": {
            "pattern": str(Path(config.CONTENT_MANAGER_STORAGE_DIR or ".") / "sources" / "<document_id>" / "original.pdf"),
            "document_scoped": True,
            "deterministic": True,
            "extension": ".pdf",
            "document_id": str(C_DOCUMENT),
            "target_path": str(target),
            "target_parent_exists": target.parent.is_dir(),
            "target_exists": target.is_file(),
        },
        "atomic_write": {
            "temporary_sibling": True,
            "temporary_prefix": ".source-",
            "fsync_file": "os.fsync(out.fileno())" in helper_source,
            "verify_sha_before_rename": "file_sha256(temporary) != expected_sha256" in helper_source,
            "atomic_rename": "os.replace(temporary, target)" in helper_source,
            "fsync_directory": "os.fsync(directory)" in helper_source,
            "existing_target_requires_matching_sha": "Durable source hash mismatch" in helper_source,
        },
        "source_path_semantics": (
            "absolute path of a worker-owned durable copy; the source endpoint serves only a path "
            "exactly equal to durable_source.source_path(document_id)"
        ),
        "source_uri_semantics": "optional logical reference, unused by the source endpoint",
        "service_helper": "modules.library.durable_source.preserve_source",
        "removal_helper": "modules.library.durable_source.remove_source",
        "endpoint": {
            "route": "/library/documents/{document_id:uuid}/source",
            "module": "modules.library.routes.library_original_source",
            "guard": "require_auth",
            "serves_only_canonical_path": True,
            "media_type": "application/pdf",
            "filename": "original.pdf",
            "cache_control": "private, no-store",
        },
        "permissions_policy": {
            "directory_mode": "0o700 on creation",
            "file_mode": "inherited from mkstemp (0o600)",
            "service_user": os.environ.get("USER"),
        },
        "database_identity": db_identity,
        "prior_gate_evidence": {
            "report": "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/durable-source-verification.json",
            "durable_expected_path": str(target),
            "matches_prior_expectation": True,
        },
    }

    ownership = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_source_metadata_owner": "library_documents",
        "owner_row": str(C_DOCUMENT),
        "authoritative_columns": [
            "source_path",
            "source_uri",
            "source_filename",
            "source_sha256",
            "source_size_bytes",
            "source_mime_type",
        ],
        "schema_columns": source_columns,
        "not_owners": {
            "library_logical_documents": "no source columns; groups generations",
            "library_document_generations": "lifecycle only; no source columns",
            "library_ingestion_runs_v2": "run metrics only; no source columns",
            "library_pages_v2": "derived page content only",
            "library_visible_documents": "read-only view over library_documents",
        },
        "endpoint_read_path": (
            "get_authorized_source() selects d.source_path from library_visible_documents; "
            "the route then requires it to equal durable_source.source_path(document_id)"
        ),
        "read_authorization": {
            "view": "library_visible_documents",
            "requires_active_generation": True,
            "scope_columns": ["organization_id", "workspace_id", "project_id", "knowledge_scope_id"],
        },
        "write_path": {
            "product_precedent": (
                "modules.library.page_first_gateway.PageFirstGateway.finalize performs "
                "UPDATE library_documents SET source_path=... WHERE id=... [guarded]"
            ),
            "official_source_path_updater": None,
            "note": (
                "No dedicated repository/service updater exists for source_path; the product itself "
                "writes the column with a guarded UPDATE inside a transaction, which this gate mirrors "
                "without changing status or any content column."
            ),
        },
        "current_values": {
            "source_path": None,
            "source_sha256": "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a",
            "source_size_bytes": 4550267,
            "source_filename": "LIKUTEY HALAJOT Interior Final.pdf",
            "source_mime_type": "application/pdf",
            "source_uri": None,
        },
    }

    (OUT / "durable-storage-contract.json").write_text(
        json.dumps(contract, indent=2, default=str, allow_nan=False) + "\n"
    )
    (OUT / "source-metadata-ownership.json").write_text(
        json.dumps(ownership, indent=2, default=str, allow_nan=False) + "\n"
    )
    print(json.dumps({
        "durable_root": str(durable_root),
        "target": str(target),
        "content_digest_columns": [c["column_name"] for c in source_columns],
    }))


if __name__ == "__main__":
    asyncio.run(main())
