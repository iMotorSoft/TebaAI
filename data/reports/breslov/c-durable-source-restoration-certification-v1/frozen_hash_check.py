"""Recompute every frozen hash and prove the harness did not change."""
from __future__ import annotations

import certlib as c


def build_payload() -> dict:
    audit = c.frozen_hash_audit()
    payload = {
        "checked_at": c.now(),
        "frozen_at": audit.get("frozen_at"),
        "frozen_manifest_sha256": audit.get("manifest_sha256"),
        "entry_count": audit.get("entry_count", 0),
        "entries": audit.get("entries", []),
        "mismatches": audit.get("mismatches", []),
        "mismatch_count": audit.get("mismatch_count", 0),
        "category_mismatch_counts": audit.get("category_mismatch_counts", {}),
        "verification_harness_unchanged": audit.get("category_mismatch_counts", {}).get(
            "harness", 0
        )
        == 0,
        "queries_unchanged": audit.get("category_mismatch_counts", {}).get("query", 0)
        == 0,
        "expectations_unchanged": all(
            audit.get("category_mismatch_counts", {}).get(category, 0) == 0
            for category in ("expectations", "endpoint")
        ),
        "report_aggregation_logic_unchanged": all(
            audit.get("category_mismatch_counts", {}).get(category, 0) == 0
            for category in ("aggregation", "report")
        ),
        "harness_unchanged": audit.get("harness_unchanged", False),
        "post_freeze_harness_changes": audit.get("category_mismatch_counts", {}).get(
            "harness", 0
        ),
        "post_freeze_query_changes": audit.get("category_mismatch_counts", {}).get(
            "query", 0
        ),
        "post_freeze_expectation_changes": sum(
            audit.get("category_mismatch_counts", {}).get(category, 0)
            for category in ("expectations", "endpoint")
        ),
        "post_freeze_report_aggregation_changes": sum(
            audit.get("category_mismatch_counts", {}).get(category, 0)
            for category in ("aggregation", "report")
        ),
        "re_freeze_performed": False,
    }
    payload["FINAL_FROZEN_HASH_CHECK"] = (
        "PASS" if audit.get("harness_unchanged", False) else "FAIL"
    )
    return payload


def main() -> None:
    payload = build_payload()
    c.write_json("final-frozen-hash-check.json", payload)
    print(
        f"entries={payload['entry_count']} mismatches={payload['mismatch_count']} -> "
        f"{payload['FINAL_FROZEN_HASH_CHECK']}"
    )
    if not payload["harness_unchanged"]:
        for mismatch in payload["mismatches"]:
            print(f"MISMATCH {mismatch}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
