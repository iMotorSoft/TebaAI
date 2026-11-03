"""Derive the per-concern evidence files from the raw measured artifacts."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text())


def save(name: str, value: dict) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main() -> None:
    cert = load("certification-preflight-results.json")

    save(
        "certification-fixture-identifiers.json",
        {
            "source": "certification-preflight-results.json",
            "label": cert["label"],
            "run_suffix": cert["run_suffix"],
            **cert["fixture_identifier"],
        },
    )
    save(
        "cutover-results.json",
        {
            "initial": cert["initial"],
            "cutover": cert["cutover"],
            "OLD_initial": "ACTIVE",
            "NEW_initial": "CANDIDATE",
            "OLD_after": cert["cutover"]["after"]["statuses"][
                cert["fixture_identifier"]["nodes"]["old"]["generation_id"]
            ],
            "NEW_after": cert["cutover"]["after"]["statuses"][
                cert["fixture_identifier"]["nodes"]["new"]["generation_id"]
            ],
            "result": "PASS" if cert["cutover"]["ok"] else "FAIL",
        },
    )
    save(
        "rollback-results.json",
        {
            "rollback": cert["rollback"],
            "OLD_after_rollback": cert["rollback"]["after"]["statuses"][
                cert["fixture_identifier"]["nodes"]["old"]["generation_id"]
            ],
            "NEW_after_rollback": cert["rollback"]["after"]["statuses"][
                cert["fixture_identifier"]["nodes"]["new"]["generation_id"]
            ],
            "result": "PASS" if cert["rollback"]["ok"] else "FAIL",
        },
    )
    save(
        "negative-controls.json",
        {
            "controls": cert["negative_controls"],
            "all_rejected": cert["negative_controls_ok"],
            "expected_product_result": "REJECTED",
            "result": "PASS" if cert["negative_controls_ok"] else "FAIL",
        },
    )
    save(
        "cleanup-results.json",
        {
            "cleanup": cert["cleanup"],
            "result": "PASS" if cert["cleanup"]["clean"] else "FAIL",
        },
    )

    baseline = load("pre-freeze-backend-baseline.json")
    final = load("backend-results.json")
    targeted = load("targeted-v1r1-error-nodes.json")
    targeted_ids = {node["node_id"] for node in targeted["nodes"]}
    resolved_errors = sorted(
        set(baseline["error_node_ids"]) - set(final["error_node_ids"])
    )
    save(
        "backend-baseline-comparison.json",
        {
            "baseline": {
                "PASS": baseline["PASS"],
                "FAIL": baseline["FAIL"],
                "ERROR": baseline["ERROR"],
                "failing_node_ids": baseline["failing_node_ids"],
                "error_node_ids": baseline["error_node_ids"],
            },
            "final": {
                "PASS": final["PASS"],
                "FAIL": final["FAIL"],
                "ERROR": final["ERROR"],
                "failing_node_ids": final["failing_node_ids"],
                "error_node_ids": final["error_node_ids"],
            },
            "new_fail_node_ids": sorted(
                set(final["failing_node_ids"]) - set(baseline["failing_node_ids"])
            ),
            "new_error_node_ids": sorted(
                set(final["error_node_ids"]) - set(baseline["error_node_ids"])
            ),
            "resolved_error_node_ids": resolved_errors,
            "resolved_error_count": len(resolved_errors),
            "targeted_error_nodes_remaining": sorted(
                set(final["error_node_ids"]) & targeted_ids
            ),
            "targeted_error_nodes_remaining_count": len(
                set(final["error_node_ids"]) & targeted_ids
            ),
            "targeted_error_nodes_resolved_count": len(
                targeted_ids & set(resolved_errors)
            ),
        },
    )
    print("derived cutover, rollback, controls, cleanup and backend comparison")


if __name__ == "__main__":
    main()
