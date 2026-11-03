"""Verify the approved external PDF identity (read-only)."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import fitz

OUT = Path(__file__).resolve().parent
APPROVED = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
EXPECTED_SIZE = 4550267
EXPECTED_PAGES = 284


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    exists = APPROVED.is_file()
    body = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "approved_external_source": str(APPROVED),
        "expected_sha256": EXPECTED_SHA,
        "expected_size_bytes": EXPECTED_SIZE,
        "expected_pages": EXPECTED_PAGES,
        "exists": exists,
        "actual_sha256": None,
        "actual_size_bytes": None,
        "actual_pages": None,
        "sha_match": False,
        "size_match": False,
        "pages_match": False,
        "source_sha_match": "NO",
        "source_size_match": "NO",
        "source_page_count_match": "NO",
        "identity": "FAIL",
        "read_only_check": "external source is only opened for reading; never written, moved or renamed",
        "external_mtime_ns": APPROVED.stat().st_mtime_ns if exists else None,
    }
    if exists:
        body["actual_sha256"] = sha256(APPROVED)
        body["actual_size_bytes"] = APPROVED.stat().st_size
        with fitz.open(APPROVED) as document:
            body["actual_pages"] = document.page_count
        body["sha_match"] = body["actual_sha256"] == EXPECTED_SHA
        body["size_match"] = body["actual_size_bytes"] == EXPECTED_SIZE
        body["pages_match"] = body["actual_pages"] == EXPECTED_PAGES
        body["source_sha_match"] = "YES" if body["sha_match"] else "NO"
        body["source_size_match"] = "YES" if body["size_match"] else "NO"
        body["source_page_count_match"] = "YES" if body["pages_match"] else "NO"
        body["identity"] = (
            "PASS" if body["sha_match"] and body["size_match"] and body["pages_match"] else "FAIL"
        )
    body["writable_by_process_user"] = os.access(APPROVED, os.W_OK) if exists else None
    (OUT / "approved-source-verification.json").write_text(
        json.dumps(body, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps({k: body[k] for k in ("identity", "actual_sha256", "actual_size_bytes", "actual_pages")}))
    if body["identity"] != "PASS":
        raise SystemExit("APPROVED_EXTERNAL_SOURCE_IDENTITY_MISMATCH")


if __name__ == "__main__":
    main()
