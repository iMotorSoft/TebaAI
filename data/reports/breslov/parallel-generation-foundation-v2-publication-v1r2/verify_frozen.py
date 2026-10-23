#!/usr/bin/env python3
"""Verify frozen candidate and harness bytes after freeze."""
from __future__ import annotations
import hashlib, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"


def sha(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(table: dict[str, str], base: pathlib.Path) -> dict:
    changed, missing = [], []
    for rel, expected in table.items():
        actual = sha(base / rel)
        if actual is None:
            missing.append(rel)
        elif actual != expected:
            changed.append({"path": rel, "expected": expected, "actual": actual})
    return {"count": len(table), "changed": changed, "missing": missing,
            "PASS": not changed and not missing}


manifest = json.loads((OUT / "frozen-manifest.json").read_text())
candidate = verify(manifest["candidate_paths"], REPO)
harness = verify(manifest["report_harness_paths"], OUT)
report = {
    "gate": GATE,
    "frozen_at": json.loads((OUT / "frozen-at.json").read_text())["frozen_at_utc"],
    "candidate": candidate,
    "report_harness": harness,
    "FROZEN_BYTES_CHANGED": len(candidate["changed"]) + len(harness["changed"]),
    "FROZEN_BYTES_MISSING": len(candidate["missing"]) + len(harness["missing"]),
    "PASS": candidate["PASS"] and harness["PASS"],
}
(OUT / "final-frozen-hash-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"candidate": candidate["count"], "harness": harness["count"],
                  "changed": report["FROZEN_BYTES_CHANGED"],
                  "missing": report["FROZEN_BYTES_MISSING"], "PASS": report["PASS"]}, indent=2))
