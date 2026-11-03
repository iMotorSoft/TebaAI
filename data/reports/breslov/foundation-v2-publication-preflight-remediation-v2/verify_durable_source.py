"""Measure the approved external source and the product durable source for C.

Read-only: PostgreSQL is queried, the durable path is inspected, and the
authenticated source route is exercised. Nothing is copied, repaired or written.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from urllib import error, request
from uuid import UUID

import fitz
import psycopg

import globalVar as config
from modules.library.durable_source import file_sha256, source_path

OUT = Path(__file__).resolve().parent
EXTERNAL = Path(
    "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
)
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
EXPECTED_SIZE = 4_550_267
EXPECTED_PAGES = 284
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
C_LOGICAL = UUID("db200a31-b547-5668-d968-06d0ec36ad95")
BASE_URL = os.environ.get("TEBAAI_PREFLIGHT_BASE_URL", "http://127.0.0.1:7008")


def http_status(url: str, token: str | None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read(128)
            return {"status": response.status, "bytes_read": len(body)}
    except error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read(200).decode("utf-8", "replace")}
    except error.URLError as exc:
        return {"status": None, "error": str(exc)}


def login() -> dict:
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD")
    if not email or not password:
        return {"status": "NOT_RUN", "reason": "E2E credentials absent from the environment"}
    body = json.dumps({"email": email, "password": password}).encode()
    req = request.Request(
        f"{BASE_URL}/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.load(response)
            return {
                "status": response.status,
                "token_present": bool(data.get("access_token")),
                "access_token": data.get("access_token"),
            }
    except error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read(200).decode("utf-8", "replace")}
    except error.URLError as exc:
        return {"status": None, "error": str(exc)}


async def database_state() -> dict:
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, title, source_filename, source_size_bytes, source_sha256,
                       source_path, status, logical_document_id
                FROM library_documents WHERE id=%s
                """,
                (C_DOCUMENT,),
            )
            row = await cur.fetchone()
            await cur.execute(
                "SELECT count(*) AS total, count(source_path) AS with_path FROM library_documents"
            )
            totals = await cur.fetchone()
    return {"document": row, "catalog": totals}


def main() -> None:
    result: dict = {
        "approved_external_source": str(EXTERNAL),
        "expected_sha256": EXPECTED_SHA,
        "expected_size_bytes": EXPECTED_SIZE,
        "expected_pages": EXPECTED_PAGES,
        "measurement": "independent, current run",
    }

    result["external_exists"] = EXTERNAL.is_file()
    if result["external_exists"]:
        result["actual_external_sha256"] = file_sha256(EXTERNAL)
        result["actual_external_size_bytes"] = EXTERNAL.stat().st_size
        with fitz.open(EXTERNAL) as doc:
            result["actual_external_pages"] = doc.page_count
    else:
        result["actual_external_sha256"] = None
        result["actual_external_size_bytes"] = None
        result["actual_external_pages"] = None

    durable = source_path(C_DOCUMENT)
    result["durable_expected_path"] = str(durable)
    result["durable_source_present"] = durable.is_file()
    result["durable_stored_bytes_sha256"] = file_sha256(durable) if durable.is_file() else None
    result["durable_stored_bytes_size"] = durable.stat().st_size if durable.is_file() else None

    state = asyncio.run(database_state())
    result["database"] = state
    document = state["document"] or {}
    result["database_source_path"] = document.get("source_path")
    result["database_source_sha256"] = document.get("source_sha256")
    result["database_source_size_bytes"] = document.get("source_size_bytes")
    result["durable_reference_resolves"] = bool(
        document.get("source_path") and Path(document["source_path"]).resolve() == durable.resolve()
    )
    result["durable_bytes_match_approved"] = bool(
        result["durable_stored_bytes_sha256"]
        and result["durable_stored_bytes_sha256"] == EXPECTED_SHA
    )
    result["approved_external_sha_match"] = (
        result["actual_external_sha256"] == EXPECTED_SHA
    )

    unauth = http_status(
        f"{BASE_URL}/library/documents/{C_DOCUMENT}/source", token=None
    )
    result["unauthenticated_request"] = unauth
    session = login()
    token = session.pop("access_token", None)
    result["authenticated_session"] = session
    if token:
        result["authenticated_request"] = http_status(
            f"{BASE_URL}/library/documents/{C_DOCUMENT}/source", token=token
        )
        result["authenticated_access"] = (
            "PASS"
            if result["authenticated_request"].get("status") == 200
            and result["durable_source_present"]
            else "FAIL"
        )
    else:
        result["authenticated_request"] = {"status": "NOT_RUN"}
        result["authenticated_access"] = "NOT_RUN"
    result["unauthenticated_blocked"] = unauth.get("status") in (401, 403)

    result["decision"] = {
        "APPROVED_EXTERNAL_SHA_MATCH": "YES" if result["approved_external_sha_match"] else "NO",
        "DURABLE_SOURCE_PRESENT": "YES" if result["durable_source_present"] else "NO",
        "DURABLE_SOURCE_RESOLVABLE": "YES" if result["durable_reference_resolves"] else "NO",
        "DURABLE_BYTES_MATCH_APPROVED": "YES" if result["durable_bytes_match_approved"] else "NO",
        "AUTHENTICATED_ACCESS": result["authenticated_access"],
        "UNAUTHENTICATED_BLOCKED": "YES" if result["unauthenticated_blocked"] else "NO",
    }
    result["durable_source_ok"] = all(
        value in ("YES", "PASS")
        for value in result["decision"].values()
    )

    (OUT / "durable-source-verification.json").write_text(
        json.dumps(result, indent=2, default=str, allow_nan=False) + "\n"
    )
    print(json.dumps(result["decision"], indent=2))


if __name__ == "__main__":
    main()
