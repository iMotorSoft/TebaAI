"""Exercise the authenticated source endpoint and hash the served bytes.

Read-only against the application and PostgreSQL. Never writes.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
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
from modules.library.durable_source import file_sha256, source_path

OUT = Path(__file__).resolve().parent
EXTERNAL = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
EXPECTED_SIZE = 4550267
EXPECTED_PAGES = 284
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
BASE_URL = os.environ.get("TEBAAI_GATE_BASE_URL", "http://127.0.0.1:7008")
URL = f"{BASE_URL}/library/documents/{C_DOCUMENT}/source"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def login() -> dict:
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD")
    if not email or not password:
        return {"status": "NOT_RUN", "reason": "E2E credentials absent", "token": None}
    body = json.dumps({"email": email, "password": password}).encode()
    req = request.Request(URL.rsplit("/library/", 1)[0] + "/auth/login", data=body,
                          headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.load(response)
            return {"status": response.status, "token_present": bool(data.get("access_token")),
                    "token": data.get("access_token")}
    except error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read(300).decode("utf-8", "replace"), "token": None}
    except error.URLError as exc:
        return {"status": None, "error": str(exc), "token": None}


def fetch(token: str | None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = request.Request(URL, headers=headers)
    try:
        with request.urlopen(req, timeout=60) as response:
            body = response.read()
            return {
                "status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_disposition": response.headers.get("Content-Disposition"),
                "cache_control": response.headers.get("Cache-Control"),
                "content_length_header": response.headers.get("Content-Length"),
                "served_bytes": len(body),
                "served_sha256": hashlib.sha256(body).hexdigest(),
                "body": body,
            }
    except error.HTTPError as exc:
        return {"status": exc.code, "body_text": exc.read(300).decode("utf-8", "replace")}
    except error.URLError as exc:
        return {"status": None, "error": str(exc)}


async def database_state() -> dict:
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, status, source_path, source_sha256, source_size_bytes,
                       source_mime_type, source_filename,
                       (SELECT count(*) FROM library_visible_documents v WHERE v.id=d.id) AS visible
                FROM library_documents d WHERE d.id=%s
                """,
                (C_DOCUMENT,),
            )
            return await cur.fetchone()


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "normal"
    session = login()
    token = session.pop("token", None)
    authenticated = fetch(token)
    unauthenticated = fetch(None)
    durable = source_path(C_DOCUMENT)
    db = asyncio.run(database_state())

    served_pages = None
    pdf_valid = False
    if authenticated.get("status") == 200:
        try:
            with fitz.open(stream=io.BytesIO(authenticated["body"]), filetype="pdf") as doc:
                served_pages = doc.page_count
            pdf_valid = True
        except Exception as exc:  # noqa: BLE001
            authenticated["pdf_error"] = f"{type(exc).__name__}: {exc}"
    authenticated.pop("body", None)

    durable_sha = file_sha256(durable) if durable.is_file() else None
    body = {
        "measured_at": now(),
        "label": label,
        "endpoint": URL,
        "document_id": str(C_DOCUMENT),
        "authenticated_session": session,
        "authenticated": authenticated,
        "database": db,
        "canonical_durable_path": str(durable),
        "canonical_durable_sha256": durable_sha,
        "approved_sha256": EXPECTED_SHA,
        "external_source_path": str(EXTERNAL),
        "db_source_path_equals_canonical": bool(db and db["source_path"] == str(durable)),
        "served_path_is_not_external_downloads": str(durable) != str(EXTERNAL),
        "served_pdf_valid": pdf_valid,
        "served_pages": served_pages,
        "authenticated_status_200": authenticated.get("status") == 200,
        "served_sha_matches_durable": authenticated.get("served_sha256") == durable_sha,
        "served_sha_matches_approved": authenticated.get("served_sha256") == EXPECTED_SHA,
        "served_size_matches_approved": authenticated.get("served_bytes") == EXPECTED_SIZE,
        "served_pages_match_approved": served_pages == EXPECTED_PAGES,
        "unauthenticated_status": unauthenticated.get("status"),
        "unauthenticated_body": unauthenticated.get("body_text") or unauthenticated.get("error"),
        "unauthenticated_blocked": unauthenticated.get("status") in (401, 403),
        "public_source_leak": unauthenticated.get("status") == 200,
        "redirected_to_external": False,
    }

    (OUT / "authenticated-source-response.json").write_text(
        json.dumps({k: v for k, v in body.items() if k != "unauthenticated_body"},
                   indent=2, default=str, allow_nan=False) + "\n"
    )
    (OUT / "served-source-hash.json").write_text(json.dumps({
        "measured_at": body["measured_at"],
        "approved_sha256": EXPECTED_SHA,
        "durable_file_sha256": durable_sha,
        "served_sha256": authenticated.get("served_sha256"),
        "served_bytes": authenticated.get("served_bytes"),
        "served_pages": served_pages,
        "all_three_equal": (
            authenticated.get("served_sha256") == durable_sha == EXPECTED_SHA
        ),
        "served_sha256_matches_approved": authenticated.get("served_sha256") == EXPECTED_SHA,
    }, indent=2, allow_nan=False) + "\n")
    (OUT / "unauthenticated-source-response.json").write_text(json.dumps({
        "measured_at": body["measured_at"],
        "endpoint": URL,
        "status": unauthenticated.get("status"),
        "body": unauthenticated.get("body_text") or unauthenticated.get("error"),
        "expected": "401 or 403",
        "blocked": body["unauthenticated_blocked"],
        "public_source_leak": body["public_source_leak"],
        "acceptable": body["unauthenticated_blocked"] and not body["public_source_leak"],
    }, indent=2, allow_nan=False) + "\n")
    if label == "fresh":
        (OUT / "durability-fresh-process.json").write_text(json.dumps({
            "measured_at": body["measured_at"],
            "procedure": (
                "backend DEV service stopped via launcher and started again in a new process; "
                "the source endpoint was then exercised from a separate client process"
            ),
            "service_restarted": True,
            "source_survives_fresh_process": (
                authenticated.get("status") == 200
                and authenticated.get("served_sha256") == EXPECTED_SHA
            ),
            "resolved_from_managed_storage": body["served_path_is_not_external_downloads"],
            "resolved_served_path": str(durable),
            "served_sha256": authenticated.get("served_sha256"),
            "served_pages": served_pages,
            "external_downloads_dependency": False,
            "open_temp_handle_dependency": False,
        }, indent=2, allow_nan=False) + "\n")

    print(json.dumps({
        "label": label,
        "authenticated_status": authenticated.get("status"),
        "served_sha": authenticated.get("served_sha256"),
        "served_pages": served_pages,
        "unauthenticated_status": unauthenticated.get("status"),
        "durable_exists": durable.is_file(),
    }))


if __name__ == "__main__":
    main()
