"""Aggregate the final validation and emit gate.json + final-validation.json."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
REPORT_DIR = "data/reports/breslov/c-durable-source-restoration-v1/"
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
EXPECTED_SIZE = 4550267
EXPECTED_PAGES = 284


def load(name: str) -> dict:
    path = OUT / name
    return json.loads(path.read_text()) if path.is_file() else {}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def current_paths() -> list[str]:
    paths = []
    for line in git("status", "--porcelain").splitlines():
        if not line.strip():
            continue
        paths.append(line[3:])
    return paths


def main() -> None:
    approved = load("approved-source-verification.json")
    contract = load("durable-storage-contract.json")
    durable = load("durable-file-before-metadata.json")
    writes = load("database-write-accounting.json")
    fs_writes = load("filesystem-write-accounting.json")
    auth = load("authenticated-source-response.json")
    served = load("served-source-hash.json")
    unauth = load("unauthenticated-source-response.json")
    fresh = load("durability-fresh-process.json")
    path_safety = load("path-safety.json")
    permissions = load("permissions.json")
    idempotency = load("idempotency-results.json")
    negative = load("wrong-source-negative-control.json")
    immutability = load("current-c-immutability-comparison.json")
    retrieval = load("retrieval-smoke.json")
    viewer = load("viewer-source-results.json")
    frozen = load("final-frozen-hash-check.json")
    json_validation = load("json-validation.json")
    secrets = load("secret-scan.json")
    monitor = load("forbidden-operation-monitor.json")
    run = load("restoration-run.json")
    worktree_before = load("worktree-before.json")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT,
                                capture_output=True, text=True)
    (OUT / "git-diff-check.txt").write_text(
        f"$ git diff --check\nexit_code={diff_check.returncode}\n"
        f"{diff_check.stdout}{diff_check.stderr}"
    )

    preexisting = set(worktree_before.get("preexisting_product_code_modified_before_gate", []))
    for item in worktree_before.get("classified", []):
        if item.get("state") == "untracked" and item["path"].startswith("SrvRestAstroLS_v1/"):
            preexisting.add(item["path"])
    gate_touched_product = [
        path for path in current_paths()
        if path.startswith("SrvRestAstroLS_v1/")
        and path not in preexisting
        and not path.startswith("SrvRestAstroLS_v1/backend/sources/")
    ]
    durable_files_in_git_status = [
        path for path in current_paths()
        if path.startswith("SrvRestAstroLS_v1/backend/sources/")
    ]
    durable_ignored = subprocess.run(
        ["git", "check-ignore", "-v",
         "SrvRestAstroLS_v1/backend/sources/ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa/original.pdf"],
        cwd=ROOT, capture_output=True, text=True,
    )

    conditions = {
        "approved_external_source_exists": approved.get("exists") is True,
        "external_sha256_matches_approved": approved.get("actual_sha256") == EXPECTED_SHA,
        "external_size_matches": approved.get("actual_size_bytes") == EXPECTED_SIZE,
        "external_pages_match": approved.get("actual_pages") == EXPECTED_PAGES,
        "canonical_durable_storage_found": contract.get("canonical_durable_storage_found") is True,
        "managed_durable_copy_created_or_found": (
            durable.get("managed_copy") is True and durable.get("exists") is True
        ),
        "durable_source_is_not_external_downloads": (
            path_safety.get("durable_source_is_managed_copy") is True
        ),
        "durable_sha256_matches_approved": durable.get("sha256") == EXPECTED_SHA,
        "durable_size_matches_approved": durable.get("size_bytes") == EXPECTED_SIZE,
        "durable_pages_match": durable.get("pages") == EXPECTED_PAGES,
        "source_metadata_persisted_using_existing_model": (
            writes.get("rows_modified") == 1
            and str(writes.get("row_after", {}).get("source_path", "")).endswith(
                "/sources/ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa/original.pdf"
            )
        ),
        "source_reference_resolves": auth.get("db_source_path_equals_canonical") is True,
        "authenticated_source_endpoint_200": auth.get("authenticated_status_200") is True,
        "served_sha256_matches_approved": served.get("served_sha256_matches_approved") is True,
        "served_pdf_valid": auth.get("served_pdf_valid") is True,
        "served_page_count_284": auth.get("served_pages") == EXPECTED_PAGES,
        "unauthenticated_access_blocked": unauth.get("blocked") is True,
        "public_source_leak_no": unauth.get("public_source_leak") is False,
        "fresh_process_durability_pass": fresh.get("source_survives_fresh_process") is True,
        "path_safety_pass": path_safety.get("pass") is True,
        "permissions_acceptable": permissions.get("acceptable") is True,
        "idempotency_pass": idempotency.get("noop_already_restored") is True,
        "mismatched_source_rejected": negative.get("mismatched_source_accepted") is False,
        "product_code_changes_zero": len(gate_touched_product) == 0,
        "reingest_no": monitor.get("counters", {}).get("ingest_calls") == 0,
        "extraction_no": monitor.get("counters", {}).get("extract_calls") == 0,
        "chunk_generation_no": monitor.get("counters", {}).get("chunk_generation_calls") == 0,
        "embedding_generation_no": monitor.get("counters", {}).get("embedding_calls") == 0,
        "vector_rebuild_no": (
            monitor.get("counters", {}).get("vector_insert_delete_calls") == 0
            and immutability.get("vectors_before") == immutability.get("vectors_after") == 942
        ),
        "new_generation_no": immutability.get("new_generation") == "NO",
        "new_run_no": immutability.get("new_run") == "NO",
        "active_generation_unchanged": immutability.get("active_generation_before")
        == immutability.get("active_generation_after"),
        "active_pointer_unchanged": immutability.get("active_pointer_changed") is False,
        "generation_statuses_unchanged": immutability.get("generation_statuses_changed") is False,
        "chunks_before_942": immutability.get("chunks_before") == 942,
        "chunks_after_942": immutability.get("chunks_after") == 942,
        "vectors_before_942": immutability.get("vectors_before") == 942,
        "vectors_after_942": immutability.get("vectors_after") == 942,
        "content_digest_unchanged": immutability.get("content_digest_changed") is False,
        "unexpected_postgresql_writes_zero": (
            writes.get("unexpected_rows_modified") == 0
            and monitor.get("zero_unexpected_sql_writes") is True
        ),
        "milvus_writes_zero": writes.get("milvus_writes") == 0,
        "synthetic_leftovers_zero": writes.get("synthetic_rows_created") == 0,
        "external_source_unmodified": run.get("external_source_unmodified") is True,
        "retrieval_unchanged": retrieval.get("same_content_evidence") is True,
        "viewer_generation_unchanged": viewer.get("active_pointer_unchanged") is True,
        "all_json_valid": json_validation.get("all_valid") is True,
        "git_diff_check_pass": diff_check.returncode == 0,
        "secret_scan_pass": secrets.get("pass") is True,
        "frozen_hashes_unchanged": frozen.get("frozen_hashes_unchanged") is True,
        "frozen_certification_pass": frozen.get("frozen_certification_pass") is True,
        "files_overwritten_with_different_bytes_zero": (
            fs_writes.get("files_overwritten_with_different_bytes") == 0
        ),
    }

    failed = [name for name, ok in conditions.items() if not ok]
    status = "PASS" if not failed else "FAIL"
    result = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "gate": "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_V1",
        "status": status,
        "conditions": conditions,
        "failed_conditions": failed,
        "product_code_files_modified_by_gate": gate_touched_product,
        "product_code_files_modified_by_gate_count": len(gate_touched_product),
        "preexisting_product_code_modified_before_gate_count": len(preexisting),
        "durable_pdf_untracked_in_git_status": durable_files_in_git_status,
        "durable_pdf_gitignored": durable_ignored.returncode == 0,
        "durable_pdf_gitignore_rule": durable_ignored.stdout.strip(),
        "durable_pdf_committed": False,
        "commit": "NO",
        "push": "NO",
        "postgresql_rows_modified": writes.get("rows_modified"),
        "allowed_postgresql_mutations": "source metadata for C only",
        "unexpected_postgresql_rows_modified": writes.get("unexpected_rows_modified"),
        "milvus_writes": writes.get("milvus_writes"),
        "files_created": [fs_writes.get("final_durable_path")],
        "files_overwritten": [],
        "external_approved_source_modified": not run.get("external_source_unmodified", False),
        "current_c": {
            "document_id": immutability.get("document_id"),
            "logical_document_id": immutability.get("logical_document_id"),
            "active_generation_before": immutability.get("active_generation_before"),
            "active_generation_after": immutability.get("active_generation_after"),
            "chunks_before": immutability.get("chunks_before"),
            "chunks_after": immutability.get("chunks_after"),
            "vectors_before": immutability.get("vectors_before"),
            "vectors_after": immutability.get("vectors_after"),
            "content_digest_changed": immutability.get("content_digest_changed"),
        },
    }
    (OUT / "final-validation.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    (OUT / "gate.json").write_text(json.dumps({
        "gate": result["gate"],
        "status": status,
        "validated_at": result["validated_at"],
        "failed_conditions": failed,
        "conditions_evaluated": len(conditions),
        "current_c_preserved": conditions["content_digest_unchanged"]
        and conditions["active_pointer_unchanged"],
        "durable_source_ready": status == "PASS",
        "ready_for_foundation_v2_publication_v1r2": status == "PASS",
        "foundation_v2_published": "NO",
        "ready_for_c_parallel_generation_safety_v2": "NO",
        "ready_for_c_reingest_execution": "NO",
        "c_reingest_executed": "NO",
        "commit": "NO",
        "push": "NO",
        "evidence_directory": REPORT_DIR,
    }, indent=2) + "\n")
    print(json.dumps({"status": status, "failed": failed,
                      "product_code_modified_by_gate": len(gate_touched_product),
                      "durable_untracked": durable_files_in_git_status}))


if __name__ == "__main__":
    main()
