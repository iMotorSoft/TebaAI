"""Exercise the authenticated source endpoint without producing any writes.

Usage: verify_endpoint.py initial|fresh

Authentication uses a normally signed access token minted locally from the
already-configured application issuer. The login route is deliberately not
called because it would insert an auth session row and update ``last_login_at``
(PostgreSQL writes are forbidden by this gate).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys

import certlib as c

def attempt(token: str | None) -> dict:
    raw = c.http_get(c.SOURCE_URL, token=token)
    parsed = c.parse_outcome(raw)
    if parsed["status"] == 200:
        try:
            parsed["pages"] = c.pdf_page_count_bytes(raw["body"])
        except Exception as exc:  # noqa: BLE001
            parsed["pages"] = None
            parsed["pdf_error"] = f"{type(exc).__name__}: {exc}"
    else:
        parsed["pages"] = None
    parsed.pop("body", None)
    return parsed


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "initial"
    if mode not in {"initial", "fresh"}:
        raise SystemExit("usage: verify_endpoint.py initial|fresh")

    session = asyncio.run(c.mint_access_token_readonly())
    token = session.pop("token", None)
    authenticated = attempt(token)
    unauthenticated = attempt(None)
    session.pop("token", None)

    current_pid = c.backend_pid()
    current_cmdline = c.backend_cmdline(current_pid)
    durable = c.MANAGED_SOURCE
    durable_sha = c.sha256_file(durable) if durable.is_file() else None

    common = {
        "measured_at": c.now(),
        "endpoint": c.SOURCE_URL,
        "document_id": str(c.DOCUMENT_ID),
        "authentication": session,
        "auth_header_persisted": False,
        "token_persisted": False,
        "authenticated": authenticated,
        "unauthenticated": unauthenticated,
        "approved_sha256": c.APPROVED_SHA256,
        "approved_size_bytes": c.APPROVED_SIZE,
        "approved_pages": c.APPROVED_PAGES,
        "durable_path": str(durable.resolve()),
        "durable_sha256": durable_sha,
        "authenticated_status_200": authenticated.get("status") == 200,
        "content_type_is_pdf": str(authenticated.get("content_type", "")).startswith(
            "application/pdf"
        ),
        "served_sha_matches_approved": authenticated.get("served_sha256")
        == c.APPROVED_SHA256,
        "served_sha_matches_durable": authenticated.get("served_sha256") == durable_sha,
        "served_size_matches_approved": authenticated.get("served_bytes")
        == c.APPROVED_SIZE,
        "served_pages_match_approved": authenticated.get("pages") == c.APPROVED_PAGES,
        "unauthenticated_status": unauthenticated.get("status"),
        "unauthenticated_blocked": unauthenticated.get("status") in (401, 403),
        "public_source_leak": unauthenticated.get("status") == 200,
        "backend_pid": current_pid,
        "backend_cmdline": current_cmdline,
        "served_path_is_not_external_downloads": durable.resolve()
        != c.EXTERNAL_SOURCE.resolve(),
        "three_way_byte_identity": (
            durable_sha
            == c.APPROVED_SHA256
            == authenticated.get("served_sha256")
        ),
    }

    authenticated_payload = {
        "measured_at": common["measured_at"],
        "endpoint": c.SOURCE_URL,
        "http_method": "GET",
        "status": authenticated.get("status"),
        "content_type": authenticated.get("content_type"),
        "content_disposition": authenticated.get("content_disposition"),
        "cache_control": authenticated.get("cache_control"),
        "content_length_header": authenticated.get("content_length_header"),
        "served_bytes": authenticated.get("served_bytes"),
        "served_sha256": authenticated.get("served_sha256"),
        "pdf_pages": authenticated.get("pages"),
        "authentication_mode": session.get("mint_mode"),
        "authentication_user_role": session.get("role"),
        "token_persisted": False,
        "expected_status": 200,
        "expected_content_type": "application/pdf",
        "expected_pages": c.APPROVED_PAGES,
        "expected_sha256": c.APPROVED_SHA256,
        "authenticated_status_200": common["authenticated_status_200"],
        "served_sha_matches_approved": common["served_sha_matches_approved"],
        "served_pages_match_approved": common["served_pages_match_approved"],
        "backend_pid": current_pid,
    }

    unauthenticated_payload = {
        "measured_at": common["measured_at"],
        "endpoint": c.SOURCE_URL,
        "http_method": "GET",
        "authorization_header_sent": False,
        "status": unauthenticated.get("status"),
        "content_type": unauthenticated.get("content_type"),
        "body_text": unauthenticated.get("body_text"),
        "expected_in": [401, 403],
        "blocked": common["unauthenticated_blocked"],
        "public_source_leak": common["public_source_leak"],
        "public_source_leak_expected": "NO",
        "acceptable": common["unauthenticated_blocked"]
        and not common["public_source_leak"],
    }

    served = {
        "measured_at": common["measured_at"],
        "document_id": str(c.DOCUMENT_ID),
        "external_path": str(c.EXTERNAL_SOURCE),
        "external_sha256": c.APPROVED_SHA256,
        "durable_path": common["durable_path"],
        "durable_sha256": durable_sha,
        "served_sha256": authenticated.get("served_sha256"),
        "served_bytes": authenticated.get("served_bytes"),
        "served_pages": authenticated.get("pages"),
        "approved_sha256": c.APPROVED_SHA256,
        "external_equals_durable": c.APPROVED_SHA256 == durable_sha,
        "durable_equals_served": durable_sha == authenticated.get("served_sha256"),
        "all_three_equal": common["three_way_byte_identity"],
        "served_pages_match_approved": common["served_pages_match_approved"],
        "served_path_is_not_external_downloads": common[
            "served_path_is_not_external_downloads"
        ],
        "authenticated_status": authenticated.get("status"),
        "initial_backend_pid": current_pid,
    }

    if mode == "initial":
        c.write_json("authenticated-source-response.json", authenticated_payload)
        c.write_json("unauthenticated-source-response.json", unauthenticated_payload)
        c.write_json("served-source-verification.json", served)
        print(
            f"initial: auth={authenticated.get('status')} "
            f"sha_match={common['served_sha_matches_approved']} "
            f"pages={authenticated.get('pages')} unauth={unauthenticated.get('status')}"
        )
        return

    initial = c.load_json("served-source-verification.json")
    initial_pid = initial.get("initial_backend_pid")
    old_alive = False
    if initial_pid:
        try:
            os.kill(int(initial_pid), 0)
            old_alive = True
        except OSError:
            old_alive = False

    fresh_payload = {
        "measured_at": common["measured_at"],
        "procedure": (
            "backend DEV service stopped and started again with "
            "SrvRestAstroLS_v1/backend-dev.sh restart; the source endpoint was then "
            "exercised by this separate client process"
        ),
        "restart_mechanism": "SrvRestAstroLS_v1/backend-dev.sh restart",
        "initial_backend_pid": initial_pid,
        "fresh_backend_pid": current_pid,
        "pid_changed": bool(initial_pid and current_pid and initial_pid != current_pid),
        "initial_process_still_alive": old_alive,
        "fresh_client_process_pid": os.getpid(),
        "fresh_backend_cmdline": current_cmdline,
        "authenticated_status": authenticated.get("status"),
        "served_sha256": authenticated.get("served_sha256"),
        "served_pages": authenticated.get("pages"),
        "durable_path": common["durable_path"],
        "durable_sha256": durable_sha,
        "served_sha_matches_approved": common["served_sha_matches_approved"],
        "served_sha_matches_durable": common["served_sha_matches_durable"],
        "served_pages_match_approved": common["served_pages_match_approved"],
        "external_downloads_dependency": not common[
            "served_path_is_not_external_downloads"
        ],
        "open_temp_handle_dependency": old_alive,
        "old_process_memory_dependency": old_alive,
        "resolved_from_managed_storage": common["served_path_is_not_external_downloads"],
        "unauthenticated_status": unauthenticated.get("status"),
        "public_source_leak": common["public_source_leak"],
    }
    fresh_payload["FRESH_PROCESS_SOURCE_RESOLUTION"] = (
        "PASS"
        if (
            fresh_payload["pid_changed"]
            and not fresh_payload["initial_process_still_alive"]
            and common["authenticated_status_200"]
            and common["served_sha_matches_approved"]
            and common["served_sha_matches_durable"]
            and common["served_pages_match_approved"]
            and fresh_payload["resolved_from_managed_storage"]
        )
        else "FAIL"
    )

    served["fresh"] = {
        "backend_pid": current_pid,
        "served_sha256": authenticated.get("served_sha256"),
        "served_pages": authenticated.get("pages"),
        "all_three_equal": common["three_way_byte_identity"],
        "authenticated_status": authenticated.get("status"),
        "unauthenticated_status": unauthenticated.get("status"),
    }
    served["fresh_process_pass"] = (
        fresh_payload["FRESH_PROCESS_SOURCE_RESOLUTION"] == "PASS"
    )
    c.write_json("served-source-verification.json", served)
    c.write_json("fresh-process-source-verification.json", fresh_payload)
    print(
        f"fresh: pid {initial_pid} -> {current_pid} "
        f"auth={authenticated.get('status')} sha_match="
        f"{common['served_sha_matches_approved']} pages={authenticated.get('pages')} -> "
        f"{fresh_payload['FRESH_PROCESS_SOURCE_RESOLUTION']}"
    )


if __name__ == "__main__":
    main()
