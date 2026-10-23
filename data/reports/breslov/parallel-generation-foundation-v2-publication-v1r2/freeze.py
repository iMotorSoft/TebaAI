#!/usr/bin/env python3
"""Freeze the Foundation V2 candidate and report harness (SHA-256)."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"
HARNESS = [
    "build_inventory.py", "capture_current_c.py", "v1r2_lifecycle_harness.py",
    "validate_migration_and_schema.py", "audit_latest_completed.py",
    "aggregate_tests.py", "build_prerequisites.py", "freeze.py",
    "verify_frozen.py", "compare_current_c.py", "consistency_check.py",
    "secret_scan.py", "aggregate_full_tests.py", "stage_allowlist.py",
    "validate_staged_tree.py", "fresh_tree_verify.py", "build_final_report.py",
    "publication_preflight.py",
]


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    candidate = json.loads((OUT / "foundation-v2-candidate-paths.json").read_text())
    paths = {item["path"]: item["sha256"] for item in candidate["paths"]}
    harness = {}
    for name in HARNESS:
        path = OUT / name
        if path.is_file():
            harness[name] = sha(path)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                          capture_output=True, check=True).stdout.strip()
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO, text=True,
                            capture_output=True, check=True).stdout.strip()
    manifest = {
        "gate": GATE,
        "algorithm": "sha256",
        "branch": branch,
        "authoritative_base": head,
        "candidate_count": len(paths),
        "candidate_paths": paths,
        "report_harness_count": len(harness),
        "report_harness_paths": harness,
        "post_freeze_rule": "no product/test/fixture/expected-outcome edits and no report-aggregation-logic edits after this point; any edit invalidates the gate",
    }
    if not args.write:
        print(json.dumps({"candidate_count": len(paths), "harness_count": len(harness),
                          "head": head, "branch": branch}, indent=2))
        return
    (OUT / "frozen-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [f"{digest}  {path}" for path, digest in sorted(paths.items())]
    (OUT / "frozen-hashes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    frozen_at = {
        "gate": GATE,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "authoritative_base": head,
        "candidate_count": len(paths),
        "report_harness_count": len(harness),
        "manifest_sha256": sha(OUT / "frozen-manifest.json"),
        "hashes_file_sha256": sha(OUT / "frozen-hashes.txt"),
        "post_freeze_rule": manifest["post_freeze_rule"],
    }
    (OUT / "frozen-at.json").write_text(json.dumps(frozen_at, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frozen": True, **frozen_at}, indent=2))


if __name__ == "__main__":
    main()
