"""Negative control: the restoration helper must reject a mismatched source.

Uses an isolated temporary durable root via monkeypatching, so the real C
durable source is never touched or corrupted.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

import fitz

from modules.library import durable_source

OUT = Path(__file__).resolve().parent
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
SYNTHETIC_DOCUMENT = UUID("00000000-0000-4000-8000-0000000000c1")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="c-source-negative-", dir="/tmp/opencode"))
    fake_approved = scratch / "synthetic-approved.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "synthetic negative-control document")
        document.save(fake_approved)
    fake_sha = hashlib.sha256(fake_approved.read_bytes()).hexdigest()

    original_setting = durable_source.CONTENT_MANAGER_STORAGE_DIR
    durable_source.CONTENT_MANAGER_STORAGE_DIR = str(scratch / "managed-root")
    try:
        target = durable_source.source_path(SYNTHETIC_DOCUMENT)
        rejected = False
        error_message = None
        try:
            durable_source.preserve_source(fake_approved, SYNTHETIC_DOCUMENT, EXPECTED_SHA)
        except ValueError as exc:
            rejected = True
            error_message = str(exc)
        target_created = target.exists()
        leftovers = sorted(p.name for p in target.parent.glob(".source-*")) if target.parent.is_dir() else []
    finally:
        durable_source.CONTENT_MANAGER_STORAGE_DIR = original_setting

    body = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "method": "isolated temporary durable root; synthetic PDF; approved-sha required",
        "synthetic_file": str(fake_approved),
        "synthetic_sha256": fake_sha,
        "required_sha256": EXPECTED_SHA,
        "sha_differs": fake_sha != EXPECTED_SHA,
        "helper": "modules.library.durable_source.preserve_source",
        "rejected": rejected,
        "error_message": error_message,
        "target_created": target_created,
        "temporary_leftovers": leftovers,
        "mismatched_source_accepted": not rejected,
        "real_c_source_touched": False,
        "cleanup": "temporary scratch tree left outside the repository; contains no C bytes",
    }
    (OUT / "wrong-source-negative-control.json").write_text(
        json.dumps(body, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps({"rejected": rejected, "mismatched_source_accepted": not rejected}))
    if not rejected:
        raise SystemExit("MISMATCHED_SOURCE_ACCEPTED")


if __name__ == "__main__":
    main()
