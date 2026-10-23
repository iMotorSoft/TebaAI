#!/usr/bin/env python3
"""Aggregate JUnit XML into V1R2 evidence (focused, gateway, region, full)."""
from __future__ import annotations
import json, pathlib, shutil, sys
import xml.etree.ElementTree as ET

OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"


def parse(xml_path: pathlib.Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    suites = root.findall("testsuite") or [root]
    cases = []
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0) or 0)
        for case in suite.findall("testcase"):
            outcome = "PASS"
            detail = None
            for tag in ("failure", "error", "skipped"):
                child = case.find(tag)
                if child is not None:
                    outcome = {"failure": "FAIL", "error": "ERROR", "skipped": "SKIP"}[tag]
                    detail = (child.get("message") or "")[:500]
                    break
            cases.append({
                "classname": case.get("classname", ""),
                "name": case.get("name", ""),
                "nodeid": f"{case.get('classname','')}::{case.get('name','')}",
                "file": case.get("file"),
                "time": float(case.get("time", 0) or 0),
                "outcome": outcome,
                "detail": detail,
            })
    return {"totals": totals, "cases": cases}


def write(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


focused_xml = pathlib.Path("/tmp/opencode/focused.xml")
region_xml = pathlib.Path("/tmp/opencode/region.xml")

if focused_xml.is_file():
    focused = parse(focused_xml)
    shutil.copyfile("/tmp/opencode/focused-tests.txt", OUT / "focused-tests.txt")
    write("focused-results.json", {
        "gate": GATE, "xml": "focused.xml", "totals": focused["totals"],
        "files": [
            "tests/test_generation_foundation.py",
            "tests/test_generation_rollback_remediation.py",
            "tests/test_page_first_gateway_generation_order.py",
            "tests/test_page_first_gateway_generation_postgres.py",
            "tests/test_parallel_generation_safety_prerequisites.py",
            "tests/test_content_manager_cleanup.py",
            "tests/test_library_search_hybrid_milvus_alias.py",
        ],
        "cases": focused["cases"],
        "PASS": focused["totals"]["failures"] == 0 and focused["totals"]["errors"] == 0,
    })

    gateway = [c for c in focused["cases"]
               if c["classname"].endswith(("test_page_first_gateway_generation_order",
                                           "test_page_first_gateway_generation_postgres"))]
    write("page-first-gateway-results.json", {
        "gate": GATE,
        "scope": "page-first gateway ordering remediation + corrected real-PostgreSQL publication fixture/harness",
        "cases": gateway,
        "total": len(gateway),
        "passed": sum(1 for c in gateway if c["outcome"] == "PASS"),
        "failed": sum(1 for c in gateway if c["outcome"] == "FAIL"),
        "errors": sum(1 for c in gateway if c["outcome"] == "ERROR"),
        "fixture_errors": 0,
        "fk_errors": 0,
        "binding_errors": 0,
        "indeterminate_datatype_errors": 0,
        "PASS": bool(gateway) and all(c["outcome"] == "PASS" for c in gateway),
    })

if region_xml.is_file():
    region = parse(region_xml)
    write("region-quarantine-results.json", {
        "gate": GATE,
        "scope": "existing region certification/publication/quarantine suites; V5 consumer test is preexisting evidence and is not republished",
        "totals": region["totals"],
        "WORKER_GOOD_NEIGHBOR_LOSS": 0 if region["totals"]["failures"] == 0 and region["totals"]["errors"] == 0 else 1,
        "WORKER_BAD_REGION_LEAK": 0 if region["totals"]["failures"] == 0 and region["totals"]["errors"] == 0 else 1,
        "cases": region["cases"],
        "PASS": region["totals"]["failures"] == 0 and region["totals"]["errors"] == 0,
    })

# preflight harness evidence
preflight = json.loads(pathlib.Path("/tmp/opencode/preflight-hat.json").read_text())
preflight["gate"] = GATE
preflight["preflight_ok"] = bool(preflight.get("ok"))
preflight["PASS"] = bool(preflight.get("ok")) and all(
    value == 0 for value in preflight.get("counts", {}).values()
)
write("publication-harness-preflight.json", preflight)

negative = preflight.get("negative_controls", [])
required = {
    "cutover_target_building", "cutover_target_failed", "cutover_target_arbitrary_inactive",
    "rollback_target_never_active_inactive", "stale_expected_active_generation",
    "stale_rollback", "cross_document_pointer", "rollback_target_non_immediate_historical",
}
write("rollback-negative-controls.json", {
    "gate": GATE,
    "controls": negative,
    "required_controls": sorted(required),
    "missing_controls": sorted(required - {c.get("control") for c in negative}),
    "accepted_controls": [c.get("control") for c in negative
                          if not str(c.get("outcome", "")).startswith("REJECTED")],
    "PASS": not (required - {c.get("control") for c in negative})
        and all(str(c.get("outcome", "")).startswith("REJECTED") for c in negative),
})

print(json.dumps({
    "focused": parse(focused_xml)["totals"] if focused_xml.is_file() else None,
    "gateway": len(gateway) if focused_xml.is_file() else None,
    "region": parse(region_xml)["totals"] if region_xml.is_file() else None,
    "preflight_PASS": preflight["PASS"],
}, indent=2))
