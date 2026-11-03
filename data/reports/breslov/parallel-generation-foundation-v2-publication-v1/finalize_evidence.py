"""Finalize failed-gate evidence without changing preexisting files or Git index."""
import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")
def load(name):
    return json.loads((OUT / name).read_text())

reason = "ROLLBACK_REJECTS_PREVIOUSLY_ACTIVE_GENERATION"
not_run = {"status": "NOT_RUN", "reason": "Stopped on reproduced rollback defect; no live-service validation performed"}
gate = {"gate": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1", "result": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1_FAIL", "reason": reason, "COMMIT": "NO", "PUSH": "NO", "FOUNDATION_V2_PUBLISHED": "NO", "READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2": "NO", "READY_FOR_C_REINGEST_EXECUTION": "NO", "C_REINGEST_EXECUTED": "NO"}
save("gate.json", gate)
save("foundation-v2-dependency-closure.json", {"status": "INCOMPLETE_NOT_APPROVED", "MISSING_REQUIRED_DEPENDENCIES": None, "reason": reason, "note": "Runtime imports generation.py and migration/view dependencies identified, but complete closure was not certified after discovery of defect."})
save("foundation-revalidation-results.json", {"rollback": "FAIL_OFFLINE_REPRODUCTION", "cutover": "APPLIED_OFFLINE_ONLY", "live_foundation_revalidation": "NOT_RUN", "focused_cleanup_unit_tests": {"passed": 7, "failed": 0}})
for name in ["reader-visibility-results.json", "viewer-regression-results.json", "cas-results.json", "cleanup-protection-results.json", "current-c-before.json", "current-c-after.json", "current-c-regression-results.json", "secret-scan.json", "post-push-authoritative-file-check.json", "fresh-authoritative-tree-check.json"]:
    save(name, not_run)
save("backend-results.json", {"full_backend": "NOT_RUN", "focused": {"command": "uv run pytest tests/test_content_manager_cleanup.py -q", "passed": 7, "failed": 0}, "reason": reason})
save("baseline-failure-comparison.json", {"status": "NOT_RUN", "historical_claim_failures": 20, "known_node_ids_available": False, "new_failures": None})
(OUT / "tests-backend-full.txt").write_text("NOT RUN: publication stopped on reproduced rollback defect. No full-backend result or baseline-equivalence claim.\n")
save("foundation-v2-stage-allowlist.json", {"approved": False, "paths": [], "reason": reason})
staged = subprocess.check_output(["git", "diff", "--cached", "--name-status"], cwd=ROOT).decode()
save("staged-files.json", {"name_status": staged, "index_changed_by_gate": False, "paths_staged_by_gate": []})
changed = []
for entry in load("publication-candidate-manifest.json")["files"]:
    p = ROOT / entry["path"]
    if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != entry["sha256"]:
        changed.append(entry["path"])
preexisting_changed = []
for entry in load("worktree-before.json")["files"]:
    p = ROOT / entry["path"]
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != entry["sha256"]:
        preexisting_changed.append(entry["path"])
save("final-validation.json", {**gate, "diagnostic_snapshot_hashes_unchanged": not changed, "changed_snapshot_paths": changed, "validated_publication_candidate": False, "preexisting_worktree_preserved": not preexisting_changed, "changed_preexisting_paths": preexisting_changed, "staged_inventory_empty": not staged.strip(), "full_backend": "NOT_RUN", "current_c_live_state": "NOT_VERIFIED", "services_accessed": False, "synthetic_database_rows_created": 0, "synthetic_vectors_created": 0, "C_EXTRACTION_EXECUTED": "NO", "C_EMBEDDINGS_REGENERATED": "NO", "C_VECTORS_REBUILT": "NO", "git_diff_check": "PASS", "secret_scan": "NOT_RUN"})
print(json.dumps({"snapshot_changed": changed, "preexisting_changed": preexisting_changed, "index_empty": not staged.strip()}, indent=2))
