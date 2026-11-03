"""Summarize pytest JUnit XML files into deterministic JSON evidence.

Usage: python summarize_junit.py <xml> <out.json> [--compare baseline.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree


def parse(path: Path) -> dict:
    tree = ElementTree.parse(path)
    root = tree.getroot()
    suites = root.iter("testsuite") if root.tag == "testsuites" else [root]
    passed = failed = errored = skipped = 0
    fail_ids: list[str] = []
    error_ids: list[str] = []
    for suite in suites:
        for case in suite.iter("testcase"):
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            name = name.replace(".", "/", 1).replace("::", "::", 1)
            # Rebuild the pytest node id: tests/test_x.py::test_name[param]
            classname = case.get("classname", "")
            filepart = classname.split(".")[0] if classname else ""
            rest = classname.split(".")[1:]
            module = ".".join(rest)
            node = f"{filepart}/{module}.py::{case.get('name', '')}" if module else case.get("name", "")
            node = node.replace(".py.py", ".py")
            outcome = "passed"
            for child in case:
                if child.tag == "failure":
                    outcome = "failed"
                    break
                if child.tag == "error":
                    outcome = "error"
                    break
                if child.tag == "skipped":
                    outcome = "skipped"
                    break
            if outcome == "passed":
                passed += 1
            elif outcome == "failed":
                failed += 1
                fail_ids.append(node)
            elif outcome == "error":
                errored += 1
                error_ids.append(node)
            else:
                skipped += 1
    return {
        "source_xml": str(path),
        "PASS": passed,
        "FAIL": failed,
        "ERROR": errored,
        "SKIP": skipped,
        "failing_node_ids": sorted(fail_ids),
        "error_node_ids": sorted(error_ids),
    }


def main() -> None:
    xml = Path(sys.argv[1])
    out = Path(sys.argv[2])
    summary = parse(xml)
    if "--compare" in sys.argv:
        baseline_path = Path(sys.argv[sys.argv.index("--compare") + 1])
        baseline = json.loads(baseline_path.read_text())
        base_fail = set(baseline.get("failing_node_ids", []))
        base_error = set(baseline.get("error_node_ids", []))
        current_fail = set(summary["failing_node_ids"])
        current_error = set(summary["error_node_ids"])
        summary["comparison"] = {
            "baseline": str(baseline_path),
            "new_fail_node_ids": sorted(current_fail - base_fail),
            "new_error_node_ids": sorted(current_error - base_error),
            "resolved_fail_node_ids": sorted(base_fail - current_fail),
            "resolved_error_node_ids": sorted(base_error - current_error),
        }
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("PASS", "FAIL", "ERROR", "SKIP")}))
    if "comparison" in summary:
        print(json.dumps(summary["comparison"]))


if __name__ == "__main__":
    main()
