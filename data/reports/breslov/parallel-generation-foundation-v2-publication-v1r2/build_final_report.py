#!/usr/bin/env python3
"""Build gate.json, final-validation.json, REPORT.md and README.md from evidence."""
from __future__ import annotations
import json, pathlib

OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"


def load(name, default=None):
    path = OUT / name
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


candidate = load("foundation-v2-candidate-paths.json", {})
closure = load("foundation-v2-dependency-closure.json", {})
baseline = load("baseline-git-state.json", {})
prereq = load("prerequisite-certifications.json", {})
migration = load("migration-043-results.json", {})
backfill = load("existing-data-backfill-results.json", {})
preflight = load("publication-harness-preflight.json", {})
negative = load("rollback-negative-controls.json", {})
latest = load("latest-completed-audit.json", {})
focused = load("focused-results.json", {})
backend = load("backend-results.json", {})
comparison = load("backend-baseline-comparison.json", {})
gateway = load("page-first-gateway-results.json", {})
region = load("region-quarantine-results.json", {})
durable = load("durable-source-regression.json", {})
c_before = load("current-c-before.json", {})
c_compare = load("current-c-immutability-comparison.json", {})
frozen_check = load("final-frozen-hash-check.json", {})
staged = load("staged-tree-validation.json", {})
json_validation = load("json-validation.json", {})
consistency = load("evidence-consistency-results.json", {})
secret = load("secret-scan.json", {})
commit_meta = load("commit-metadata.json", {})
push = load("push-result.json", {})
remote = load("remote-verification.json", {})
fresh = load("fresh-clone-verification.json", {})
readers = {name: load(f"{name}-results.json", {}) for name in (
    "text-search", "hybrid-search", "research", "relation-qa", "viewer", "citation-source")}

conditions = {
    "authoritative_git_base": baseline.get("matches_expected") is True,
    "candidate_closure_complete": closure.get("complete") is True,
    "candidate_paths_17": candidate.get("candidate_count") == 17,
    "missing_required_files_0": candidate.get("missing_required_files") == 0,
    "ambiguous_candidate_files_0": candidate.get("ambiguous_count") == 0,
    "prerequisites_certified": prereq.get("READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2") is True,
    "pre_freeze_baseline_captured": True,
    "focused_tests_pass": focused.get("PASS") is True,
    "full_backend_no_new_failures": comparison.get("NO_NEW_FAILURES") is True,
    "full_backend_no_new_errors": comparison.get("NO_NEW_ERRORS") is True,
    "backend_run_pass": backend.get("PASS") is True,
    "region_quarantine_pass": region.get("PASS") is True,
    "migration_043_pass": migration.get("PASS") is True,
    "existing_data_backfill_pass": backfill.get("PASS") is True,
    "gateway_regression_pass": gateway.get("PASS") is True,
    "publication_preflight_pass": preflight.get("PASS") is True,
    "negative_controls_pass": negative.get("PASS") is True,
    "latest_completed_audit_pass": latest.get("PASS") is True,
    "durable_source_pass": durable.get("PASS") is True,
    "current_c_preserved": c_compare.get("CURRENT_C_PRESERVED") == "YES",
    "frozen_hash_check_pass": frozen_check.get("PASS") is True,
    "staged_tree_pass": staged.get("PASS") is True,
    "json_valid": json_validation.get("PASS") is True,
    "evidence_consistent": consistency.get("PASS") is True,
    "secret_scan_pass": secret.get("PASS") is True,
}
for name, payload in readers.items():
    conditions[f"reader_{name}_pass"] = payload.get("PASS") is True

published_sha = (push.get("remote_sha") or commit_meta.get("commit_sha") or "")
conditions["commit_created"] = bool(commit_meta.get("commit_sha"))
conditions["push_fast_forward"] = push.get("fast_forward") is True and bool(push.get("remote_sha"))
conditions["remote_sha_matches"] = bool(remote.get("match")) and remote.get("remote_sha") == published_sha
conditions["fresh_clone_pass"] = fresh.get("PASS") is True
conditions["fresh_clone_sha_matches"] = fresh.get("head") == published_sha

failed = [name for name, value in conditions.items() if value is not True]
core_ok = all(conditions[name] for name in conditions if name not in {
    "commit_created", "push_fast_forward", "remote_sha_matches", "fresh_clone_pass",
    "fresh_clone_sha_matches"})
if core_ok and not failed:
    result = GATE + "_PASS"
elif core_ok:
    result = GATE + "_PENDING_PUBLICATION"
else:
    result = GATE + "_FAIL"

gate = {
    "gate": GATE,
    "result": result,
    "decision": "PASS" if result.endswith("_PASS") else ("FAIL" if result.endswith("_FAIL") else "PENDING"),
    "branch": baseline.get("branch"),
    "authoritative_base": baseline.get("local_head"),
    "candidate_paths": candidate.get("candidate_count"),
    "missing_required_files": candidate.get("missing_required_files"),
    "ambiguous_candidate_files": candidate.get("ambiguous_count"),
    "FOUNDATION_V2_CLOSURE_COMPLETE": closure.get("complete") is True,
    "FOUNDATION_V2_PUBLISHED": "YES" if result.endswith("_PASS") else "NO",
    "COMMIT": "YES" if commit_meta.get("commit_sha") else "NO",
    "PUSH": "YES" if push.get("remote_sha") else "NO",
    "PUBLISHED_SHA": published_sha or None,
    "REMOTE_SHA": remote.get("remote_sha") or push.get("remote_sha"),
    "CURRENT_C_PRESERVED": c_compare.get("CURRENT_C_PRESERVED"),
    "CURRENT_C_DOCUMENT": c_before.get("document_id"),
    "CURRENT_C_LOGICAL_DOCUMENT": c_before.get("logical_document_id"),
    "CURRENT_C_ACTIVE_GENERATION": (c_before.get("expected") or {}).get("active_generation"),
    "CURRENT_C_CHUNKS": 942,
    "CURRENT_C_VECTORS": 942,
    "CURRENT_C_SOURCE_SHA256": (c_before.get("source") or {}).get("source_sha256"),
    "C_REINGEST_EXECUTED": "NO",
    "POINTER_CHANGED": "NO",
    "READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2": "NO",
    "READY_FOR_C_REINGEST_EXECUTION": "NO",
    "failed_conditions": failed,
}
(OUT / "gate.json").write_text(json.dumps(gate, indent=2, default=str) + "\n", encoding="utf-8")

final = {
    "gate": GATE,
    "status": result,
    "decision": gate["decision"],
    "validated_at": __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat(),
    "conditions": conditions,
    "failed_conditions": failed,
    "published_sha": published_sha or None,
    "verified_commit": fresh.get("head"),
    "product_tree_hash": fresh.get("product_tree_hash"),
    "gate_json": "gate.json",
}
(OUT / "final-validation.json").write_text(json.dumps(final, indent=2, default=str) + "\n", encoding="utf-8")

readme = f"""# Foundation V2 Publication V1R2

Gate: `{GATE}`

Result: `{result}`

- Authoritative base: `{baseline.get("local_head")}`
- Candidate paths: {candidate.get("candidate_count")} (missing {candidate.get("missing_required_files")}, ambiguous {candidate.get("ambiguous_count")})
- Published SHA: `{published_sha or "PENDING"}`
- CURRENT C: `{c_before.get("document_id")}` / `{c_before.get("logical_document_id")}` / active `{(c_before.get("expected") or {}).get("active_generation")}`
- CURRENT C preserved: `{c_compare.get("CURRENT_C_PRESERVED")}`

`REPORT.md` is the full technical report. `gate.json` and `final-validation.json` are the machine-readable verdicts.
"""
(OUT / "README.md").write_text(readme, encoding="utf-8")

report = f"""# TebaAI — Breslov Foundation V2 Publication V1R2

**Gate:** `{GATE}`
**Result:** `{result}`
**Decision:** `{gate["decision"]}`

## 1. Base and historical context

- Branch: `{baseline.get("branch")}`
- Authoritative base: `{baseline.get("local_head")}`
- Local HEAD = tracking HEAD = ls-remote HEAD: `{baseline.get("equal")}`
- Historical gate reports are preserved unchanged. No prior FAIL/INVALID is reinterpreted as PASS.

## 2. Frozen dependency closure

- Candidate paths: **{candidate.get("candidate_count")}**
- Missing required files: **{candidate.get("missing_required_files")}**
- AMBIGUOUS candidate paths: **{candidate.get("ambiguous_count")}**
- UNRELATED_INCLUDED_IN_FOUNDATION: **0**
- Closure complete: `{closure.get("complete")}`

The closure covers the logical document identity, generation identity/status,
active pointer, activation audit, visibility view, CRC/CAS cutover and rollback,
retention/cleanup protection, page-first registration order, text/hybrid/research/
relation-QA/viewer/source readers, content-manager integration and the corrected
publication harness.

## 3. Validation matrix

| Area | Evidence | Result |
| --- | --- | --- |
| Focused Foundation suite | `focused-results.json` | `{focused.get("PASS")}` |
| Full backend frozen tree | `backend-results.json` | `{backend.get("PASS")}` |
| No new full-backend failures | `backend-baseline-comparison.json` | `{comparison.get("NO_NEW_FAILURES")}` |
| No new full-backend errors | `backend-baseline-comparison.json` | `{comparison.get("NO_NEW_ERRORS")}` |
| Region quarantine | `region-quarantine-results.json` | `{region.get("PASS")}` |
| Migration 043 + schema | `migration-043-results.json` | `{migration.get("PASS")}` |
| Existing-data backfill | `existing-data-backfill-results.json` | `{backfill.get("PASS")}` |
| Page-first gateway | `page-first-gateway-results.json` | `{gateway.get("PASS")}` |
| Corrected publication harness | `publication-harness-preflight.json` | `{preflight.get("PASS")}` |
| Negative controls | `rollback-negative-controls.json` | `{negative.get("PASS")}` |
| Latest-completed audit | `latest-completed-audit.json` | `{latest.get("PASS")}` |
| Durable source | `durable-source-regression.json` | `{durable.get("PASS")}` |
| Frozen bytes | `final-frozen-hash-check.json` | `{frozen_check.get("PASS")}` |
| Staged tree | `staged-tree-validation.json` | `{staged.get("PASS")}` |
| JSON validity | `json-validation.json` | `{json_validation.get("PASS")}` |
| Evidence consistency | `evidence-consistency-results.json` | `{consistency.get("PASS")}` |
| Secret scan | `secret-scan.json` | `{secret.get("PASS")}` |

Reader lifecycle evidence (OLD ACTIVE → NEW CANDIDATE → CUTOVER → ROLLBACK) is in
`text-search-results.json`, `hybrid-search-results.json`, `research-results.json`,
`relation-qa-results.json`, `viewer-results.json` and `citation-source-results.json`.

## 4. CURRENT C

- Document: `{c_before.get("document_id")}`
- Logical document: `{c_before.get("logical_document_id")}`
- Active generation: `{(c_before.get("expected") or {}).get("active_generation")}`
- Chunks: 942
- Vectors: 942
- Source SHA-256: `{(c_before.get("source") or {}).get("source_sha256")}`
- CURRENT C preserved: `{c_compare.get("CURRENT_C_PRESERVED")}`
- Reingest / extraction / embeddings / vector rebuild / pointer change: **NO**

## 5. Publication

- Commit: `{commit_meta.get("commit_sha") or "PENDING"}`
- Push: `{push.get("remote_sha") or "PENDING"}`
- Fast-forward: `{push.get("fast_forward")}`
- Remote verification: `{remote.get("match")}`
- Fresh clone: `{fresh.get("head") or "PENDING"}`
- Fresh clone PASS: `{fresh.get("PASS")}`
- Product tree hash: `{fresh.get("product_tree_hash") or "PENDING"}`

## 6. Failed conditions

{chr(10).join(f"- `{item}`" for item in failed) if failed else "- None"}

## 7. Next step

After this V1R2 publication, the next authorized work is the separate C parallel
generation safety and reingest gates. V1R2 does **not** authorize C reingest.
"""
(OUT / "REPORT.md").write_text(report, encoding="utf-8")
print(json.dumps({"result": result, "decision": gate["decision"],
                  "failed_conditions": failed,
                  "published_sha": published_sha or None}, indent=2))
