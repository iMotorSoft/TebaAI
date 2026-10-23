#!/usr/bin/env python3
"""Aggregate the post-freeze full backend run and compare with the baseline."""
from __future__ import annotations
import argparse, json, pathlib, shutil
import xml.etree.ElementTree as ET

OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"
KNOWN_EXCLUDED_PREFIXES = ("tests.test_v5_evaluator_semantics",)


def parse(xml_path: pathlib.Path) -> dict:
    root = ET.parse(xml_path).getroot()
    suites = root.findall("testsuite") or [root]
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    cases, failures, errors = [], [], []
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0) or 0)
        for case in suite.findall("testcase"):
            nodeid = f"{case.get('classname','')}::{case.get('name','')}"
            outcome = "PASS"
            detail = None
            for tag, label in (("failure", "FAIL"), ("error", "ERROR"), ("skipped", "SKIP")):
                child = case.find(tag)
                if child is not None:
                    outcome = label
                    detail = (child.get("message") or "")[:800]
                    break
            item = {"nodeid": nodeid, "file": case.get("file"),
                    "time": float(case.get("time", 0) or 0), "outcome": outcome,
                    "detail": detail}
            cases.append(item)
            if outcome == "FAIL":
                failures.append(nodeid)
            elif outcome == "ERROR":
                errors.append(nodeid)
    return {"totals": totals, "cases": cases, "failures": failures, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-xml", default="/tmp/opencode/pre-freeze.xml")
    parser.add_argument("--frozen-xml", default="/tmp/opencode/post-freeze-full.xml")
    parser.add_argument("--frozen-txt", default="/tmp/opencode/post-freeze-full.txt")
    args = parser.parse_args()
    baseline = parse(pathlib.Path(args.baseline_xml))
    frozen = parse(pathlib.Path(args.frozen_xml))
    new_failures = sorted(set(frozen["failures"]) - set(baseline["failures"]))
    new_errors = sorted(set(frozen["errors"]) - set(baseline["errors"]))
    disappeared = sorted(set(baseline["failures"]) - set(frozen["failures"]))
    known_disappeared = [n for n in disappeared if n.startswith(KNOWN_EXCLUDED_PREFIXES)]
    unexplained_disappeared = [n for n in disappeared if n not in known_disappeared]
    baseline_pass = baseline["totals"]["tests"] - baseline["totals"]["failures"] - baseline["totals"]["errors"] - baseline["totals"]["skipped"]
    frozen_pass = frozen["totals"]["tests"] - frozen["totals"]["failures"] - frozen["totals"]["errors"] - frozen["totals"]["skipped"]

    results = {
        "gate": GATE,
        "frozen_candidate": "git archive HEAD + 17 frozen candidate paths; no excluded untracked V5 files",
        "totals": frozen["totals"], "passed": frozen_pass,
        "baseline": {"totals": baseline["totals"], "passed": baseline_pass},
        "failures": frozen["failures"], "errors": frozen["errors"],
        "new_failures": new_failures, "new_errors": new_errors,
        "disappeared_failures": disappeared,
        "known_disappeared_failures": known_disappeared,
        "unexplained_disappeared_failures": unexplained_disappeared,
        "NEW_FAILURES": len(new_failures), "NEW_ERRORS": len(new_errors),
        "PASS": not new_failures and not new_errors and not unexplained_disappeared,
    }
    (OUT / "backend-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    comparison = {
        "gate": GATE,
        "baseline": {"totals": baseline["totals"], "passed": baseline_pass,
                     "failures": baseline["failures"], "errors": baseline["errors"]},
        "frozen": {"totals": frozen["totals"], "passed": frozen_pass,
                   "failures": frozen["failures"], "errors": frozen["errors"]},
        "new_failures": new_failures, "new_errors": new_errors,
        "disappeared_failures": disappeared,
        "known_disappeared_failures": known_disappeared,
        "unexplained_disappeared_failures": unexplained_disappeared,
        "NO_NEW_FAILURES": not new_failures,
        "NO_NEW_ERRORS": not new_errors,
        "PASS": results["PASS"],
    }
    (OUT / "backend-baseline-comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    for src, dst in ((args.frozen_xml, "backend.xml"), (args.frozen_txt, "tests-backend-full.txt"),
                     (args.baseline_xml, "pre-freeze-backend.xml")):
        if pathlib.Path(src).is_file():
            shutil.copyfile(src, OUT / dst)
    if pathlib.Path("/tmp/opencode/pre-freeze.txt").is_file():
        shutil.copyfile("/tmp/opencode/pre-freeze.txt", OUT / "pre-freeze-backend-output.txt")
    print(json.dumps({"frozen": frozen["totals"], "passed": frozen_pass,
                      "new_failures": len(new_failures), "new_errors": len(new_errors),
                      "disappeared": len(disappeared), "PASS": results["PASS"]}, indent=2))


if __name__ == "__main__":
    main()
