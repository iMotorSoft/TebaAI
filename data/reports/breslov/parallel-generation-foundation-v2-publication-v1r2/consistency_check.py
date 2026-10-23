#!/usr/bin/env python3
"""Validate every report JSON and cross-file evidence consistency."""
from __future__ import annotations
import json, pathlib

OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


json_files = sorted(p for p in OUT.glob("*.json"))
valid, invalid = [], []
for path in json_files:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        valid.append(path.name)
    except Exception as exc:
        invalid.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
json_validation = {
    "gate": GATE, "json_files": len(json_files), "valid": valid,
    "invalid": invalid, "INVALID_JSON": len(invalid),
    "PASS": not invalid,
}
(OUT / "json-validation.json").write_text(json.dumps(json_validation, indent=2) + "\n", encoding="utf-8")

checks = {}
try:
    candidate = load("foundation-v2-candidate-paths.json")
    closure = load("foundation-v2-dependency-closure.json")
    gap = load("foundation-v2-versioning-gap.json")
    baseline = load("baseline-git-state.json")
    before = load("current-c-before.json")
    durable = load("durable-source-regression.json")
    migration = load("migration-043-results.json")
    backfill = load("existing-data-backfill-results.json")
    preflight = load("publication-harness-preflight.json")
    negative = load("rollback-negative-controls.json")
    prerequisites = load("prerequisite-certifications.json")
    latest = load("latest-completed-audit.json")
    focused = load("focused-results.json")
    backend = load("backend-results.json")
    comparison = load("backend-baseline-comparison.json")
    frozen = load("frozen-manifest.json")
    frozen_check = load("final-frozen-hash-check.json")
    reader_files = ["text-search-results.json", "hybrid-search-results.json",
                    "research-results.json", "relation-qa-results.json",
                    "viewer-results.json", "citation-source-results.json"]
    readers = {name: load(name) for name in reader_files}

    checks["candidate_count_17"] = candidate["candidate_count"] == 17
    checks["missing_required_files_0"] = candidate["missing_required_files"] == 0
    checks["ambiguous_candidate_files_0"] = candidate["ambiguous_count"] == 0
    checks["closure_complete"] = closure["complete"] is True
    checks["closure_missing_0"] = closure["missing_required_files"] == 0
    checks["closure_ambiguous_0"] = closure["ambiguous_candidate_files"] == 0
    checks["versioning_total_17"] = sum(gap["summary"].values()) == 17
    checks["authoritative_base_matches"] = baseline["matches_expected"] is True
    checks["c_before_active_generation"] = (before["active_pointer"] or {}).get("generation_id") == before["expected"]["active_generation"]
    checks["c_before_chunks_942"] = before["chunks"]["count"] == 942
    checks["c_before_vectors_942"] = before["milvus"]["document_vector_count"] == 942
    checks["c_before_embeddings_942"] = before["embeddings"]["count"] == 942
    checks["c_before_source_sha"] = before["source"]["source_sha256"] == before["source"]["approved_sha256"]
    checks["durable_source_regression_none"] = durable["DURABLE_SOURCE_REGRESSION"] == "NO"
    checks["durable_source_pass"] = durable["PASS"] is True
    checks["migration_043_pass"] = migration["PASS"] is True
    checks["backfill_pass"] = backfill["PASS"] is True
    checks["backfill_no_active_without_pointer"] = backfill["backfill"]["active_generations_without_pointer"] == 0
    checks["backfill_no_visible_mismatch"] = backfill["backfill"]["visible_mismatch"] == 0
    checks["preflight_pass"] = preflight["PASS"] is True
    checks["preflight_zero_errors"] = all(v == 0 for v in preflight["counts"].values())
    checks["negative_controls_pass"] = negative["PASS"] is True
    checks["prerequisites_ready"] = prerequisites["READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2"] is True
    checks["latest_completed_audit_pass"] = latest["PASS"] is True
    checks["latest_completed_unresolved_0"] = latest["UNRESOLVED_USER_VISIBLE_LATEST_FALLBACKS"] == 0
    checks["focused_pass"] = focused["PASS"] is True
    checks["focused_63"] = focused["totals"]["tests"] == 63
    checks["backend_no_new_failures"] = comparison["NO_NEW_FAILURES"] is True
    checks["backend_no_new_errors"] = comparison["NO_NEW_ERRORS"] is True
    checks["backend_pass"] = backend["PASS"] is True
    checks["frozen_candidate_count_17"] = frozen["candidate_count"] == 17
    checks["frozen_hash_check_pass"] = frozen_check["PASS"] is True
    checks["frozen_bytes_changed_0"] = frozen_check["FROZEN_BYTES_CHANGED"] == 0
    for name, payload in readers.items():
        checks[f"reader_{name}_pass"] = payload.get("PASS") is True
except Exception as exc:
    checks["consistency_check_exception"] = False
    checks["exception"] = f"{type(exc).__name__}: {exc}"

report = {
    "gate": GATE,
    "checks": checks,
    "failed_checks": [k for k, v in checks.items() if v is not True],
    "JSON_VALID": json_validation["PASS"],
    "EVIDENCE_CONSISTENT": all(v is True for v in checks.values()) and json_validation["PASS"],
    "PASS": all(v is True for v in checks.values()) and json_validation["PASS"],
}
(OUT / "evidence-consistency-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"json_valid": json_validation["PASS"], "checks": len(checks),
                  "failed": report["failed_checks"], "PASS": report["PASS"]}, indent=2))
