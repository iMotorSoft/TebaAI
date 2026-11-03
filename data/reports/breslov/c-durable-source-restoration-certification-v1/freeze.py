"""Freeze the read-only harness and expected outcomes before the first run.

No certification observation happens in this script. It only records hashes of
the already-written harness, the pre-existing Git/worktree state, the approved
source bytes and the expected outcomes.
"""
from __future__ import annotations

import hashlib
import json

import certlib as c

GATE = "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1"

CATEGORY = {
    "certlib.py": "harness",
    "git_state.py": "harness",
    "readonly_contract.py": "harness",
    "capture_fs.py": "harness",
    "verify_approved_source.py": "harness",
    "verify_durable_file.py": "harness",
    "run_tests.py": "harness",
    "frozen_hash_check.py": "expectations",
    "capture_state.py": "query",
    "verify_source_metadata.py": "query",
    "verify_endpoint.py": "endpoint",
    "viewer_source_smoke.py": "endpoint",
    "compare_state.py": "aggregation",
    "aggregate.py": "report",
    "final_checks.py": "aggregation",
    "json_validate.py": "harness",
    "secret_scan.py": "harness",
    "git_diff_check.py": "harness",
    "freeze.py": "expectations",
    "run_certification.sh": "harness",
}

FROZEN_ARTIFACTS = {
    "baseline-git-state.json": "expectations",
    "worktree-before.json": "expectations",
    "certification-readonly-contract.json": "harness",
}


def main() -> None:
    baseline = c.load_json("baseline-git-state.json")
    contract = c.load_json("certification-readonly-contract.json")
    if not baseline.get("authoritative_base_ok"):
        raise SystemExit("BLOCKED: authoritative Git base moved or diverged")
    if contract.get("CERTIFICATION_READONLY_CONTRACT") != "PASS":
        raise SystemExit("INVALID: harness contract is not read-only")

    for name in CATEGORY:
        if not (c.OUT_DIR / name).is_file():
            raise SystemExit(f"missing harness file: {name}")
    for name in FROZEN_ARTIFACTS:
        if not (c.OUT_DIR / name).is_file():
            raise SystemExit(f"missing frozen artifact: {name}")

    external_sha = c.sha256_file(c.EXTERNAL_SOURCE)
    durable_sha = c.sha256_file(c.MANAGED_SOURCE)
    if external_sha != c.APPROVED_SHA256 or durable_sha != c.APPROVED_SHA256:
        raise SystemExit("approved/durable SHA does not match the frozen expectation")
    external_pages = c.pdf_page_count(c.EXTERNAL_SOURCE)
    durable_pages = c.pdf_page_count(c.MANAGED_SOURCE)
    if external_pages != c.APPROVED_PAGES or durable_pages != c.APPROVED_PAGES:
        raise SystemExit("approved/durable page count does not match expectation")

    baseline_results = json.loads(c.BASELINE_RESULTS.read_text(encoding="utf-8"))
    baseline_failing = baseline_results.get("failing_node_ids", [])
    baseline_digest = hashlib.sha256(
        json.dumps(sorted(baseline_failing), separators=(",", ":")).encode()
    ).hexdigest()

    frozen_at = c.now()
    harness_files = [
        {
            "name": name,
            "category": category,
            "sha256": c.sha256_file(c.OUT_DIR / name),
        }
        for name, category in sorted(CATEGORY.items())
    ]
    frozen_artifacts = [
        {
            "name": name,
            "category": category,
            "sha256": c.sha256_file(c.OUT_DIR / name),
        }
        for name, category in sorted(FROZEN_ARTIFACTS.items())
    ]
    durable_info = c.file_stat(c.MANAGED_SOURCE)
    external_info = c.file_stat(c.EXTERNAL_SOURCE)

    manifest = {
        "frozen_at": frozen_at,
        "gate": GATE,
        "mode": "READ-ONLY / CERTIFICATION-ONLY / ZERO-WRITE",
        "repo": str(c.REPO_ROOT),
        "branch": baseline.get("branch"),
        "head": baseline.get("head"),
        "tracking_head": baseline.get("tracking_head"),
        "ls_remote_head": baseline.get("ls_remote_head"),
        "document_id": str(c.DOCUMENT_ID),
        "logical_document_id": str(c.LOGICAL_DOCUMENT_ID),
        "external_file": {
            "path": str(c.EXTERNAL_SOURCE),
            "sha256": external_info["sha256"],
            "size_bytes": external_info["size_bytes"],
            "pages": external_pages,
        },
        "durable_file": {
            "path": str(c.MANAGED_SOURCE),
            "sha256": durable_info["sha256"],
            "size_bytes": durable_info["size_bytes"],
            "pages": durable_pages,
            "mtime_ns": durable_info["mtime_ns"],
            "inode": durable_info["inode"],
        },
        "baseline_tests": {
            "path": str(c.BASELINE_RESULTS.relative_to(c.REPO_ROOT)),
            "sha256": c.sha256_file(c.BASELINE_RESULTS),
            "PASS": baseline_results.get("PASS"),
            "FAIL": baseline_results.get("FAIL"),
            "ERROR": baseline_results.get("ERROR"),
            "failing_node_ids_digest": baseline_digest,
            "failing_node_ids_count": len(baseline_failing),
        },
        "expected_outcomes": {
            "document_id": str(c.DOCUMENT_ID),
            "logical_document_id": str(c.LOGICAL_DOCUMENT_ID),
            "approved_sha256": c.APPROVED_SHA256,
            "approved_size_bytes": c.APPROVED_SIZE,
            "approved_pages": c.APPROVED_PAGES,
            "durable_sha256": c.APPROVED_SHA256,
            "durable_size_bytes": c.APPROVED_SIZE,
            "durable_pages": c.APPROVED_PAGES,
            "managed_path": str(c.MANAGED_SOURCE.resolve()),
            "external_path": str(c.EXTERNAL_SOURCE.resolve()),
            "active_generation": c.ACTIVE_GENERATION,
            "run_id": c.KNOWN_RUN_ID,
            "chunks": c.EXPECTED_CHUNKS,
            "vectors": c.EXPECTED_VECTORS,
            "authenticated_status": 200,
            "authenticated_content_type": "application/pdf",
            "unauthenticated_status_in": [401, 403],
            "public_source_leak": "NO",
            "fresh_process_resolution": "PASS",
            "postgresql_writes": 0,
            "milvus_writes": 0,
            "durable_filesystem_writes": 0,
            "new_generations": 0,
            "new_runs": 0,
            "active_pointer_changes": 0,
            "generation_status_changes": 0,
            "new_backend_fail_node_ids": 0,
            "new_backend_error_node_ids": 0,
            "report_contradictions": 0,
        },
        "harness_files": harness_files,
        "frozen_artifacts": frozen_artifacts,
        "auxiliary_hashes": {
            "baseline/backend-results.json": c.sha256_file(c.BASELINE_RESULTS),
            "durable/original.pdf": durable_info["sha256"],
            "external/approved.pdf": external_info["sha256"],
        },
        "post_freeze_rule": (
            "After this freeze: no harness change, no SQL/query change, no expected-result "
            "change, no aggregation/report change, no endpoint-check change. Any change makes "
            "the gate INVALID; no re-freeze or supersession is allowed inside this gate."
        ),
    }
    c.write_json("frozen-manifest.json", manifest)

    hashes = {
        f"report/{item['name']}": item["sha256"]
        for item in harness_files + frozen_artifacts
    }
    hashes["report/frozen-manifest.json"] = c.sha256_file(
        c.OUT_DIR / "frozen-manifest.json"
    )
    hashes["baseline/backend-results.json"] = c.sha256_file(c.BASELINE_RESULTS)
    hashes["durable/original.pdf"] = durable_info["sha256"]
    hashes["external/approved.pdf"] = external_info["sha256"]
    c.write_text(
        "frozen-hashes.txt",
        "# frozen hashes - do not edit after freeze\n"
        + "\n".join(f"{digest}  {name}" for name, digest in sorted(hashes.items()))
        + "\n",
    )
    c.write_json(
        "frozen-at.json",
        {
            "frozen_at": frozen_at,
            "rule": manifest["post_freeze_rule"],
            "frozen_entries": len(hashes),
            "harness_entries": len(harness_files),
            "artifact_entries": len(frozen_artifacts),
        },
    )
    print(
        json.dumps(
            {
                "frozen_at": frozen_at,
                "entries": len(hashes),
                "durable_sha": durable_info["sha256"],
                "base": baseline.get("head"),
            }
        )
    )


if __name__ == "__main__":
    main()
