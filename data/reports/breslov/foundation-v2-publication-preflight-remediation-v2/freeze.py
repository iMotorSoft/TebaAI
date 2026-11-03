"""Freeze the remediation harness bytes and verify them later.

Usage:
  python freeze.py freeze   -> frozen-manifest.json, frozen-hashes.txt, frozen-at.json
  python freeze.py check    -> final-frozen-hash-check.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]

FROZEN_FILES = [
    "SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/publication_preflight.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/verify_durable_source.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/current_c_check.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/capture_git_state.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/summarize_junit.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/write_analysis_evidence.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/extract_evidence.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/verify_evidence.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/build_reports.py",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/freeze.py",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    mode = sys.argv[1]
    if mode == "freeze":
        manifest = []
        for relative in FROZEN_FILES:
            path = ROOT / relative
            manifest.append(
                {
                    "path": relative,
                    "sha256": digest(path),
                    "size_bytes": path.stat().st_size,
                }
            )
        manifest.sort(key=lambda item: item["path"])
        (OUT / "frozen-manifest.json").write_text(
            json.dumps(
                {
                    "scope": [
                        "fixture code",
                        "fixture SQL",
                        "bind types",
                        "test helpers",
                        "expected outcomes",
                        "cleanup behavior",
                        "durable-source verification",
                        "report consistency logic",
                    ],
                    "files": manifest,
                    "count": len(manifest),
                },
                indent=2,
            )
            + "\n"
        )
        (OUT / "frozen-hashes.txt").write_text(
            "".join(f"{item['sha256']}  {item['path']}\n" for item in manifest)
        )
        frozen_at = {
            "at": datetime.now(timezone.utc).isoformat(),
            "files": len(manifest),
            "rule": "no fixture, SQL, bind/cast, test, expectation, cleanup, durable verification or reporting logic change after this instant",
        }
        (OUT / "frozen-at.json").write_text(json.dumps(frozen_at, indent=2) + "\n")
        print(json.dumps({"frozen_files": len(manifest), "at": frozen_at["at"]}))
    elif mode == "check":
        manifest = json.loads((OUT / "frozen-manifest.json").read_text())
        results = []
        for item in manifest["files"]:
            actual = digest(ROOT / item["path"])
            results.append(
                {
                    "path": item["path"],
                    "expected": item["sha256"],
                    "actual": actual,
                    "unchanged": actual == item["sha256"],
                }
            )
        unchanged = all(item["unchanged"] for item in results)
        payload = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "files": results,
            "unchanged": unchanged,
            "modified_files": [item["path"] for item in results if not item["unchanged"]],
        }
        (OUT / "final-frozen-hash-check.json").write_text(
            json.dumps(payload, indent=2) + "\n"
        )
        print(json.dumps({"unchanged": unchanged}))
        if not unchanged:
            raise SystemExit(1)
    else:
        raise SystemExit("mode must be freeze|check")


if __name__ == "__main__":
    main()
