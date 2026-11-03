"""Read-only inspection of the authoritative source metadata for C."""
from __future__ import annotations

import asyncio
from pathlib import Path

import certlib as c


async def snapshot() -> dict:
    async with await c.connect_readonly() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, logical_document_id, status, source_path, source_uri,
                       source_filename, source_sha256, source_size_bytes,
                       source_mime_type, updated_at
                FROM library_documents WHERE id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            return await cur.fetchone()


def main() -> None:
    row = asyncio.run(snapshot())
    managed = c.MANAGED_SOURCE.resolve()
    external = c.EXTERNAL_SOURCE.resolve()
    source_path = Path(row["source_path"]).resolve() if row["source_path"] else None
    payload = {
        "measured_at": c.now(),
        "document_id": str(c.DOCUMENT_ID),
        "logical_document_id": str(c.LOGICAL_DOCUMENT_ID),
        "db_row": row,
        "db_source_path": row["source_path"],
        "resolved_db_source_path": str(source_path) if source_path else None,
        "managed_path": str(managed),
        "external_path": str(external),
        "source_path_exists": bool(row["source_path"]),
        "source_path_points_to_managed_copy": source_path == managed,
        "source_path_points_to_downloads": (
            str(source_path).startswith(str(Path("/media/issajar/DEVELOP/Download")))
            if source_path
            else False
        ),
        "source_path_points_to_managed_source_dir": (
            str(source_path).startswith(str((c.BACKEND_DIR / "sources").resolve()))
            if source_path
            else False
        ),
        "db_source_sha256": row["source_sha256"],
        "db_source_size_bytes": row["source_size_bytes"],
        "db_source_sha256_matches_approved": row["source_sha256"] == c.APPROVED_SHA256,
        "db_source_size_matches_approved": row["source_size_bytes"] == c.APPROVED_SIZE,
        "db_source_mime_type": row["source_mime_type"],
        "db_source_filename": row["source_filename"],
        "updated_at": row["updated_at"],
        "source_metadata_changed_by_gate": False,
        "read_mode": "single SELECT on a read-only PostgreSQL session",
    }
    payload["SOURCE_METADATA_OWNERSHIP"] = (
        "PASS"
        if payload["source_path_exists"]
        and payload["source_path_points_to_managed_copy"]
        and not payload["source_path_points_to_downloads"]
        and payload["db_source_sha256_matches_approved"]
        and payload["db_source_size_matches_approved"]
        else "FAIL"
    )
    c.write_json("source-metadata-verification.json", payload)
    print(
        f"source_path={row['source_path']} managed={payload['source_path_points_to_managed_copy']} "
        f"downloads={payload['source_path_points_to_downloads']} -> "
        f"{payload['SOURCE_METADATA_OWNERSHIP']}"
    )


if __name__ == "__main__":
    main()
