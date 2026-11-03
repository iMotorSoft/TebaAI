"""Recalculate the approved external source identity, read-only."""
from __future__ import annotations

import certlib as c


def main() -> None:
    path = c.EXTERNAL_SOURCE
    exists = path.is_file()
    size = path.stat().st_size if exists else None
    sha = c.sha256_file(path) if exists else None
    pages = c.pdf_page_count(path) if exists else None
    payload = {
        "measured_at": c.now(),
        "path": str(path),
        "exists": exists,
        "sha256": sha,
        "size_bytes": size,
        "pages": pages,
        "expected_sha256": c.APPROVED_SHA256,
        "expected_size_bytes": c.APPROVED_SIZE,
        "expected_pages": c.APPROVED_PAGES,
        "sha256_matches": sha == c.APPROVED_SHA256,
        "size_matches": size == c.APPROVED_SIZE,
        "pages_match": pages == c.APPROVED_PAGES,
        "was_modified_by_gate": False,
        "read_mode": "sha256 + PyMuPDF page count only; no write, chmod or rename",
    }
    payload["APPROVED_SOURCE_IDENTITY"] = (
        "PASS"
        if payload["exists"]
        and payload["sha256_matches"]
        and payload["size_matches"]
        and payload["pages_match"]
        else "FAIL"
    )
    c.write_json("approved-source-verification.json", payload)
    print(
        f"external exists={exists} sha_match={payload['sha256_matches']} "
        f"size_match={payload['size_matches']} pages={pages} -> "
        f"{payload['APPROVED_SOURCE_IDENTITY']}"
    )


if __name__ == "__main__":
    main()
