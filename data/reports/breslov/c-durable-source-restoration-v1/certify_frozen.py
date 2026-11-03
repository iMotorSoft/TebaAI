"""Post-freeze certification: hashes, metadata, bytes, endpoint and C state.

Read-only. Fails loudly if any frozen value changed after freeze.py ran.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

import fitz
import psycopg

import globalVar as config
from modules.library.durable_source import source_path

OUT = Path(__file__).resolve().parent
EXTERNAL = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
EXPECTED_SIZE = 4550267
EXPECTED_PAGES = 284
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
C_LOGICAL = UUID("db200a31-b547-5668-d968-06d0ec36ad95")
BASE_URL = os.environ.get("TEBAAI_GATE_BASE_URL", "http://127.0.0.1:7008")
URL = f"{BASE_URL}/library/documents/{C_DOCUMENT}/source"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_hashes() -> dict[str, str]:
    rows = {}
    for line in (OUT / "frozen-hashes.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, name = line.split("  ", 1)
        rows[name] = digest
    return rows


def login() -> str | None:
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD")
    if not email or not password:
        return None
    body = json.dumps({"email": email, "password": password}).encode()
    req = request.Request(f"{BASE_URL}/auth/login", data=body,
                          headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=30) as response:
        return json.load(response).get("access_token")


def fetch(token: str | None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = request.Request(URL, headers=headers)
    try:
        with request.urlopen(req, timeout=60) as response:
            body = response.read()
            return {"status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "pages": fitz.open(stream=body, filetype="pdf").page_count}
    except error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read(200).decode("utf-8", "replace")}


async def live_state() -> dict:
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, status, source_path, source_sha256, source_size_bytes,
                       source_mime_type, source_filename, logical_document_id, updated_at
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
            await cur.execute(
                "SELECT id::text AS id, status FROM library_document_generations "
                "WHERE logical_document_id=%s ORDER BY id",
                (C_LOGICAL,),
            )
            generations = await cur.fetchall()
            await cur.execute(
                "SELECT count(*) AS n FROM library_document_chunks WHERE document_id=%s",
                (C_DOCUMENT,),
            )
            chunks = (await cur.fetchone())["n"]
            await cur.execute(
                "SELECT md5(COALESCE(string_agg(to_jsonb(c)::text, '' ORDER BY c.id), '')) AS digest "
                "FROM library_document_chunks c WHERE c.document_id=%s",
                (C_DOCUMENT,),
            )
            chunk_digest = (await cur.fetchone())["digest"]
    return {"document": document, "active_pointer": pointer, "generations": generations,
            "chunks": chunks, "chunk_digest": chunk_digest}


def milvus_count() -> dict:
    try:
        from pymilvus import MilvusClient
        client = MilvusClient(uri=f"http://{config.MILVUS_HOST}:{config.MILVUS_PORT}")
        rows = client.query(
            collection_name=config.MILVUS_COLLECTION_BRESLOV,
            filter=f'document_id == "{C_DOCUMENT}"',
            output_fields=["chunk_id"], limit=16384,
        )
        return {"status": "OK", "entities_for_c": len(rows),
                "chunk_id_digest": hashlib.md5(
                    "".join(sorted(str(r["chunk_id"]) for r in rows)).encode()).hexdigest()}
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    frozen = json.loads((OUT / "frozen-manifest.json").read_text())
    expected_hashes = parse_hashes()
    checked = []
    mismatches = []
    for name, expected in expected_hashes.items():
        kind, _, relative = name.partition("/")
        if kind == "report":
            path = OUT / relative
        elif kind == "durable":
            path = source_path(C_DOCUMENT)
        elif kind == "external":
            path = EXTERNAL
        else:
            mismatches.append({"name": name, "reason": "unknown frozen namespace"})
            continue
        actual = sha256_file(path) if path.is_file() else None
        entry = {"name": name, "expected": expected, "actual": actual,
                 "unchanged": actual == expected}
        checked.append(entry)
        if not entry["unchanged"]:
            mismatches.append(entry)

    durable = source_path(C_DOCUMENT)
    info = durable.stat()
    state = asyncio.run(live_state())
    frozen_meta = frozen["source_metadata"]["document"]
    metadata_unchanged = all(
        str(state["document"][key]) == str(frozen_meta[key])
        for key in ("id", "source_path", "source_sha256", "source_size_bytes",
                    "source_mime_type", "logical_document_id")
    )
    token = login()
    authenticated = fetch(token)
    unauthenticated = fetch(None)

    body = {
        "certified_at": datetime.now(timezone.utc).isoformat(),
        "frozen_at": frozen["frozen_at"],
        "hash_entries_checked": len(checked),
        "hash_mismatches": mismatches,
        "frozen_hashes_unchanged": not mismatches,
        "durable_file": {
            "path": str(durable),
            "sha256": sha256_file(durable),
            "size_bytes": info.st_size,
            "mtime_ns": info.st_mtime_ns,
            "inode": info.st_ino,
            "pages": fitz.open(durable).page_count,
            "mtime_matches_freeze": info.st_mtime_ns == frozen["durable_file"]["mtime_ns"],
            "inode_matches_freeze": info.st_ino == frozen["durable_file"]["inode"],
        },
        "external_source_sha256": sha256_file(EXTERNAL),
        "source_metadata": state["document"],
        "source_metadata_matches_freeze": metadata_unchanged,
        "active_pointer": state["active_pointer"],
        "active_pointer_matches_freeze": None,
        "generations": state["generations"],
        "chunks": state["chunks"],
        "chunk_digest": state["chunk_digest"],
        "milvus": milvus_count(),
        "authenticated": authenticated,
        "unauthenticated": unauthenticated,
        "authenticated_ok": (
            authenticated.get("status") == 200
            and authenticated.get("sha256") == EXPECTED_SHA
            and authenticated.get("pages") == EXPECTED_PAGES
        ),
        "unauthenticated_blocked": unauthenticated.get("status") in (401, 403),
    }
    body["active_pointer_matches_freeze"] = (
        state["active_pointer"]["generation_id"]
        == frozen["source_metadata"]["active_pointer"]["generation_id"]
    )
    body["frozen_certification_pass"] = (
        body["frozen_hashes_unchanged"]
        and body["durable_file"]["sha256"] == EXPECTED_SHA
        and body["durable_file"]["pages"] == EXPECTED_PAGES
        and body["external_source_sha256"] == EXPECTED_SHA
        and metadata_unchanged
        and body["active_pointer_matches_freeze"]
        and body["authenticated_ok"]
        and body["unauthenticated_blocked"]
        and body["chunks"] == 942
        and (body["milvus"].get("entities_for_c") == 942)
    )
    (OUT / "final-frozen-hash-check.json").write_text(
        json.dumps(body, indent=2, default=str, allow_nan=False) + "\n"
    )
    print(json.dumps({
        "frozen_hashes_unchanged": body["frozen_hashes_unchanged"],
        "authenticated": authenticated.get("status"),
        "unauth": unauthenticated.get("status"),
        "pass": body["frozen_certification_pass"],
    }))
    if not body["frozen_certification_pass"]:
        raise SystemExit("FROZEN_CERTIFICATION_FAILED")


if __name__ == "__main__":
    main()
