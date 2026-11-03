"""Closing checks: final JSON validity, secret scan, frozen hashes, consistency.

If any closing check fails, the gate is downgraded to INVALID and the
machine-readable result plus REPORT.md are updated accordingly.
"""
from __future__ import annotations

import json
import re

import certlib as c
import frozen_hash_check

GATE = "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1"
KEYS = (
    "approved_source_sha_match",
    "durable_source_present",
    "durable_source_sha_match",
    "authenticated_status",
    "unauthenticated_status",
    "fresh_process_pass",
    "zero_postgres_writes",
    "zero_milvus_writes",
    "current_c_preserved",
    "ready_for_foundation_publication_v1r2",
)
BLOCK = re.compile(
    r"<!-- CONSISTENCY-KEYS -->\s*```json\s*(\{.*?\})\s*```\s*<!-- /CONSISTENCY-KEYS -->",
    re.DOTALL,
)


def report_block(text: str) -> dict | None:
    match = BLOCK.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def compare_keys(gate: dict, final: dict, report: dict | None) -> list[dict]:
    contradictions = []
    gate_keys = gate.get("consistency_keys") or {}
    final_keys = final.get("consistency_keys") or {}
    for key in KEYS:
        values = {
            "gate": gate_keys.get(key),
            "final_validation": final_keys.get(key),
            "report": (report or {}).get(key),
        }
        if len({json.dumps(value, sort_keys=True) for value in values.values()}) != 1:
            contradictions.append({"key": key, "values": values})
    status = gate.get("status")
    if final.get("status") != status:
        contradictions.append(
            {
                "key": "status_gate_vs_final_validation",
                "values": {"gate": status, "final_validation": final.get("status")},
            }
        )
    return contradictions


def update_report_status(report_text: str, old_status: str, new_status: str, keys: dict) -> str:
    text = report_text.replace(f"Result: **{old_status}**", f"Result: **{new_status}**")
    block = json.dumps(keys, indent=2)
    text = BLOCK.sub(
        "<!-- CONSISTENCY-KEYS -->\n```json\n" + block + "\n```\n<!-- /CONSISTENCY-KEYS -->",
        text,
        count=1,
    )
    return text


def main() -> None:
    frozen = frozen_hash_check.build_payload()
    c.write_json("final-frozen-hash-check.json", frozen)

    json_audit = c.strict_json_audit()
    c.write_json("json-validation.json", json_audit)

    secret = c.secret_audit()
    c.write_json("secret-scan.json", secret)

    gate = c.load_json("gate.json")
    final = c.load_json("final-validation.json")
    report_text = (c.OUT_DIR / "REPORT.md").read_text(encoding="utf-8")
    parsed_block = report_block(report_text)

    contradictions = compare_keys(gate, final, parsed_block)
    closing_failures = []
    if not json_audit["ALL_JSON_VALID"]:
        closing_failures.append("INVALID_JSON_FILES")
    if secret["SECRET_SCAN"] != "PASS":
        closing_failures.append("SECRET_SCAN_FAIL")
    if not frozen["harness_unchanged"]:
        closing_failures.append("FROZEN_HARNESS_CHANGED")
    if parsed_block is None:
        closing_failures.append("REPORT_CONSISTENCY_BLOCK_MISSING")

    if closing_failures:
        old_status = gate.get("status")
        new_status = f"{GATE}_INVALID"
        keys = dict(final.get("consistency_keys") or {})
        keys["ready_for_foundation_publication_v1r2"] = "NO"
        final["status"] = new_status
        final["decision"] = "INVALID"
        failed = list(final.get("failed_conditions") or [])
        for reason in closing_failures:
            if reason not in failed:
                failed.append(reason)
        final["failed_conditions"] = failed
        final["invalid_reasons"] = sorted(
            set(list(final.get("invalid_reasons") or []) + closing_failures)
        )
        final["consistency_keys"] = keys
        c.write_json("final-validation.json", final)

        gate["status"] = new_status
        gate["decision"] = "INVALID"
        gate["failed_conditions"] = failed
        gate["failed_condition_count"] = len(failed)
        gate["invalid_reasons"] = final["invalid_reasons"]
        gate["consistency_keys"] = keys
        gate["ready_for_foundation_publication_v1r2"] = "NO"
        gate["durable_source_certified"] = False
        c.write_json("gate.json", gate)

        report_text = update_report_status(report_text, old_status, new_status, keys)
        report_text += (
            "\n## CLOSING CHECK FAILURE\n\n"
            + "\n".join(f"- `{reason}`" for reason in closing_failures)
            + "\n"
        )
        c.write_text("REPORT.md", report_text)

        gate = c.load_json("gate.json")
        final = c.load_json("final-validation.json")
        parsed_block = report_block(report_text)
        contradictions = compare_keys(gate, final, parsed_block)

    payload = {
        "checked_at": c.now(),
        "consistency_keys": list(KEYS),
        "report_block_found": parsed_block is not None,
        "gate_status": gate.get("status"),
        "final_validation_status": final.get("status"),
        "report_status_line": (
            f"Result: **{gate.get('status')}**" in report_text
        ),
        "key_values": {
            key: {
                "gate": (gate.get("consistency_keys") or {}).get(key),
                "final_validation": (final.get("consistency_keys") or {}).get(key),
                "report": (parsed_block or {}).get(key),
            }
            for key in KEYS
        },
        "contradictions": contradictions,
        "contradiction_count": len(contradictions),
        "closing_failures": closing_failures,
        "json_valid": json_audit["ALL_JSON_VALID"],
        "secret_scan": secret["SECRET_SCAN"],
        "frozen_harness_unchanged": frozen["harness_unchanged"],
        "REPORT_CONTRADICTIONS": len(contradictions),
        "REPORT_CONSISTENCY": "PASS" if not contradictions else "FAIL",
    }
    c.write_json("evidence-consistency-results.json", payload)

    final_json = c.strict_json_audit()
    c.write_json("json-validation.json", final_json)
    print(
        json.dumps(
            {
                "json_valid": final_json["ALL_JSON_VALID"],
                "secret_scan": secret["SECRET_SCAN"],
                "frozen_unchanged": frozen["harness_unchanged"],
                "contradictions": len(contradictions),
                "closing_failures": closing_failures,
                "status": gate.get("status"),
            }
        )
    )


if __name__ == "__main__":
    main()
