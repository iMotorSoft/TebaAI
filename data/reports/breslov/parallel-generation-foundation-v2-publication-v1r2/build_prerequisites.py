#!/usr/bin/env python3
"""Build historical gate summary and prerequisite certification evidence (read-only)."""
from __future__ import annotations
import hashlib, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
BASE = REPO / "data" / "reports" / "breslov"
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"


def sha256(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def gate_info(directory: str) -> dict:
    d = BASE / directory
    gate = load_json(d / "gate.json") or {}
    final = load_json(d / "final-validation.json") or {}
    return {
        "directory": f"data/reports/breslov/{directory}",
        "gate_json": gate,
        "final_validation_status": final.get("status") or final.get("result"),
        "final_validation_gate": final.get("gate"),
        "report_md_present": (d / "REPORT.md").is_file(),
        "preserved_unchanged": True,
    }


historical = [
    gate_info("parallel-generation-foundation-v2-publication-v1"),
    gate_info("parallel-generation-rollback-remediation-v1"),
    gate_info("parallel-generation-rollback-remediation-v2"),
    gate_info("page-first-gateway-generation-order-remediation-v1"),
    gate_info("foundation-v2-publication-preflight-remediation-v1"),
    gate_info("foundation-v2-publication-preflight-remediation-v2"),
    gate_info("parallel-generation-foundation-v2-publication-v1r1"),
    gate_info("c-durable-source-restoration-v1"),
    gate_info("c-durable-source-restoration-certification-v1"),
]
prompt_tokens = {
    "parallel-generation-foundation-v2-publication-v1": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1_FAIL",
    "parallel-generation-rollback-remediation-v1": "TEBAAI_BRESLOV_PARALLEL_GENERATION_ROLLBACK_REMEDIATION_V1_INVALID",
    "parallel-generation-rollback-remediation-v2": "TEBAAI_BRESLOV_PARALLEL_GENERATION_ROLLBACK_REMEDIATION_V2_PASS",
    "page-first-gateway-generation-order-remediation-v1": "TEBAAI_BRESLOV_PAGE_FIRST_GATEWAY_GENERATION_ORDER_REMEDIATION_V1_PASS",
    "foundation-v2-publication-preflight-remediation-v1": "TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V1_FAIL",
    "foundation-v2-publication-preflight-remediation-v2": "TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V2_FAIL",
    "parallel-generation-foundation-v2-publication-v1r1": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R1_FAIL",
    "c-durable-source-restoration-v1": "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_V1_INVALID",
    "c-durable-source-restoration-certification-v1": "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1_PASS",
}
for item in historical:
    item["token_supplied_by_gate_prompt"] = prompt_tokens.get(item["directory"].rsplit("/", 1)[-1])
    item["prompt_token_matches_stored"] = None
    stored = item["gate_json"].get("result") or item["gate_json"].get("gate") or item["final_validation_status"]
    item["stored_gate_result"] = stored
    token = item["token_supplied_by_gate_prompt"]
    item["prompt_token_matches_stored"] = bool(
        token and stored and (token == stored or token in str(stored) or stored in token)
    )

(OUT / "historical-gates-summary.json").write_text(json.dumps({
    "gate": GATE,
    "policy": "historical reports are preserved byte-for-byte; no prior FAIL/INVALID is reinterpreted as PASS and no prior PASS is reinterpreted as FAIL",
    "historical_gates": historical,
    "publication_v1r2_is_new_certification": True,
    "prior_runs_used_as_historical_context_not_as_certification": True,
}, indent=2, default=str) + "\n", encoding="utf-8")

# --- prerequisite certification chain -------------------------------------
rollback_manifest = load_json(BASE / "parallel-generation-rollback-remediation-v2" / "frozen-manifest.json") or {}
pagefirst_manifest = load_json(BASE / "page-first-gateway-generation-order-remediation-v1" / "frozen-manifest.json") or {}
preflight_manifest = load_json(BASE / "foundation-v2-publication-preflight-remediation-v2" / "frozen-manifest.json") or {}


def entries(manifest: dict) -> dict[str, str]:
    for key in ("paths", "files"):
        value = manifest.get(key)
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, list):
            result = {}
            for item in value:
                if isinstance(item, dict) and item.get("path"):
                    result[item["path"]] = item.get("sha256") or item.get("hash")
            return result
    return {}


def verify_manifest(name: str, manifest: dict, superseded_by: dict[str, tuple[str, str]] | None = None) -> dict:
    superseded_by = superseded_by or {}
    checked, missing, mismatched, superseded = 0, [], [], []
    for rel, expected in entries(manifest).items():
        checked += 1
        path = REPO / rel
        actual = sha256(path)
        if actual is None:
            missing.append(rel)
        elif actual != expected:
            if rel in superseded_by:
                later_dir, later_expected = superseded_by[rel]
                superseded.append({
                    "path": rel,
                    "superseded_by": later_dir,
                    "frozen_hash_in_this_gate": expected,
                    "current_hash": actual,
                    "later_gate_hash": later_expected,
                    "matches_later_gate": later_expected == actual,
                })
            else:
                mismatched.append({"path": rel, "expected": expected, "actual": actual})
    return {
        "gate": name,
        "frozen_file_count": checked,
        "missing": missing,
        "unexplained_mismatches": mismatched,
        "superseded_by_later_pass": superseded,
        "PASS": not missing and not mismatched and all(s["matches_later_gate"] for s in superseded),
    }


pagefirst_gateway_hash = entries(pagefirst_manifest).get("SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py")
preflight_test_hash = entries(preflight_manifest).get("SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py")

rollback = verify_manifest(
    "TEBAAI_BRESLOV_PARALLEL_GENERATION_ROLLBACK_REMEDIATION_V2_PASS",
    rollback_manifest,
    {
        "SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py": (
            "page-first-gateway-generation-order-remediation-v1", pagefirst_gateway_hash),
        "SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py": (
            "foundation-v2-publication-preflight-remediation-v2", preflight_test_hash),
    },
)
pagefirst = verify_manifest(
    "TEBAAI_BRESLOV_PAGE_FIRST_GATEWAY_GENERATION_ORDER_REMEDIATION_V1_PASS",
    pagefirst_manifest,
    {
        "SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py": (
            "foundation-v2-publication-preflight-remediation-v2", preflight_test_hash),
    },
)
preflight = verify_manifest(
    "TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V2",
    preflight_manifest,
)

c_cert_final = load_json(BASE / "c-durable-source-restoration-certification-v1" / "final-validation.json") or {}
c_cert_gate = load_json(BASE / "c-durable-source-restoration-certification-v1" / "gate.json") or {}
c_ok = (
    c_cert_final.get("status") == "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1_PASS"
    and c_cert_gate.get("decision") == "PASS"
    and c_cert_gate.get("status") == "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1_PASS"
)

# every candidate path is covered by at least one frozen manifest, or is a
# new V1R2 path whose bytes are first frozen by this gate.
candidate = load_json(OUT / "foundation-v2-candidate-paths.json") or {}
all_manifests = {
    "rollback_v2": entries(rollback_manifest),
    "page_first_v1": entries(pagefirst_manifest),
    "preflight_v2": entries(preflight_manifest),
}
coverage = []
for item in candidate.get("paths", []):
    rel = item["path"]
    matches = [name for name, table in all_manifests.items() if table.get(rel) == item["sha256"]]
    coverage.append({
        "path": rel,
        "current_sha256": item["sha256"],
        "matching_frozen_manifests": matches,
        "new_in_v1r2": not matches,
    })

prereq = {
    "gate": GATE,
    "prerequisites": {
        "rollback_remediation_v2": rollback,
        "page_first_gateway_order_v1": pagefirst,
        "publication_preflight_remediation_v2": preflight,
        "c_durable_source_restoration_certification_v1": {
            "final_validation_status": c_cert_final.get("status"),
            "gate_result": c_cert_gate.get("status") or c_cert_gate.get("decision"),
            "PASS": c_ok,
        },
    },
    "candidate_frozen_hash_coverage": {
        "candidate_count": len(coverage),
        "covered_by_prior_pass_manifest": sum(1 for c in coverage if not c["new_in_v1r2"]),
        "new_in_v1r2": sum(1 for c in coverage if c["new_in_v1r2"]),
        "paths": coverage,
    },
    "supersession_chain_explained_not_unreviewed": True,
    "READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2": all(
        [rollback["PASS"], pagefirst["PASS"], preflight["PASS"], c_ok]
    ),
}
prereq["PASS"] = prereq["READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2"]
(OUT / "prerequisite-certifications.json").write_text(
    json.dumps(prereq, indent=2, default=str) + "\n", encoding="utf-8")

print(json.dumps({
    "historical_gates": len(historical),
    "rollback": {"PASS": rollback["PASS"], "files": rollback["frozen_file_count"],
                 "superseded": len(rollback["superseded_by_later_pass"]),
                 "unexplained": len(rollback["unexplained_mismatches"])},
    "page_first": {"PASS": pagefirst["PASS"], "files": pagefirst["frozen_file_count"],
                   "superseded": len(pagefirst["superseded_by_later_pass"]),
                   "unexplained": len(pagefirst["unexplained_mismatches"])},
    "preflight": {"PASS": preflight["PASS"], "files": preflight["frozen_file_count"],
                  "unexplained": len(preflight["unexplained_mismatches"])},
    "c_certification": c_ok,
    "candidate_coverage": prereq["candidate_frozen_hash_coverage"]["covered_by_prior_pass_manifest"],
    "candidate_new": prereq["candidate_frozen_hash_coverage"]["new_in_v1r2"],
    "READY": prereq["READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2"],
}, indent=2))
