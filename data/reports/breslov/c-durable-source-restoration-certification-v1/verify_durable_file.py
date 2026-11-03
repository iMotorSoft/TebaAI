"""Verify the already-restored managed durable PDF without touching it."""
from __future__ import annotations

import certlib as c
from modules.library.durable_source import source_path


def main() -> None:
    expected = c.MANAGED_SOURCE.resolve()
    actual = source_path(c.DOCUMENT_ID)
    path = actual.resolve()
    exists = path.is_file()
    size = path.stat().st_size if exists else None
    sha = c.sha256_file(path) if exists else None
    pages = c.pdf_page_count(path) if exists else None
    external_resolved = c.EXTERNAL_SOURCE.resolve()
    payload = {
        "measured_at": c.now(),
        "document_id": str(c.DOCUMENT_ID),
        "path_from_durable_source_helper": str(actual),
        "resolved_path": str(path),
        "expected_managed_path": str(expected),
        "exists": exists,
        "is_managed_tebaai_storage": str(path).startswith(
            str((c.BACKEND_DIR / "sources").resolve())
        ),
        "path_equals_helper_path": path == expected,
        "path_equals_external_downloads": path == external_resolved,
        "is_not_external_downloads": path != external_resolved,
        "sha256": sha,
        "size_bytes": size,
        "pages": pages,
        "expected_sha256": c.APPROVED_SHA256,
        "expected_size_bytes": c.APPROVED_SIZE,
        "expected_pages": c.APPROVED_PAGES,
        "sha256_matches_approved": sha == c.APPROVED_SHA256,
        "size_matches_approved": size == c.APPROVED_SIZE,
        "pages_match_approved": pages == c.APPROVED_PAGES,
        "mutations_performed": [],
        "read_mode": "stat + sha256 + PyMuPDF page count; no copy, touch, chmod, rename or fsync",
    }
    payload["managed_copy_verified"] = bool(
        payload["exists"]
        and payload["is_managed_tebaai_storage"]
        and not payload["path_equals_external_downloads"]
        and payload["sha256_matches_approved"]
        and payload["size_matches_approved"]
        and payload["pages_match_approved"]
    )
    c.write_json("durable-source-file-verification.json", payload)
    print(
        f"durable exists={exists} managed={payload['is_managed_tebaai_storage']} "
        f"sha_match={payload['sha256_matches_approved']} pages={pages} -> "
        f"{payload['managed_copy_verified']}"
    )


if __name__ == "__main__":
    main()
