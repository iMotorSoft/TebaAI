"""Run the focused source tests and the full backend suite, read-only w.r.t. C."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import certlib as c

FOCUSED = [
    "tests/test_region_source_access.py",
    "tests/test_scope_authorization.py",
    "tests/test_auth_dependencies.py",
    "tests/test_region_worker_enforcement.py::test_durable_source_survives_upload_cleanup_and_is_hash_checked",
    "tests/test_region_worker_enforcement.py::test_failed_source_copy_keeps_upload",
    "tests/test_canonical_work_edition_source_metadata.py",
]

SUMMARY = re.compile(
    r"(?:(?P<failed>\d+) failed)?[,\s]*(?:(?P<passed>\d+) passed)?[,\s]*"
    r"(?:(?P<error>\d+) error)?[,\s]*(?:(?P<skipped>\d+) skipped)?"
)


def parse_summary(text: str) -> dict:
    tail = "\n".join(text.strip().splitlines()[-5:])
    summary = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for key, pattern in (
        ("passed", r"(\d+) passed"),
        ("failed", r"(\d+) failed"),
        ("error", r"(\d+) errors?"),
        ("skipped", r"(\d+) skipped"),
    ):
        matches = re.findall(pattern, tail)
        if matches:
            summary[key] = int(matches[-1])
    return summary


def parse_node_ids(text: str) -> tuple[list[str], list[str]]:
    failures, errors = [], []
    for line in text.splitlines():
        if line.startswith("FAILED "):
            failures.append(line.removeprefix("FAILED ").split(" - ")[0].strip())
        elif line.startswith("ERROR "):
            errors.append(line.removeprefix("ERROR ").split(" - ")[0].strip())
    return sorted(set(failures)), sorted(set(errors))


def run(command: list[str], timeout: int) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=c.BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> None:
    python = str(c.BACKEND_DIR / ".venv" / "bin" / "python")

    focused_command = [
        python,
        "-m",
        "pytest",
        *FOCUSED,
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]
    focused_code, focused_text = run(focused_command, timeout=900)
    c.write_text("focused-tests.txt", "$ " + " ".join(focused_command) + "\n\n" + focused_text)
    focused_summary = parse_summary(focused_text)
    focused_fail, focused_error = parse_node_ids(focused_text)
    focused = {
        "command": focused_command,
        "exit_code": focused_code,
        "PASS": focused_summary["passed"],
        "FAIL": focused_summary["failed"],
        "ERROR": focused_summary["error"],
        "SKIP": focused_summary["skipped"],
        "failure_node_ids": focused_fail,
        "error_node_ids": focused_error,
        "focused_pass": focused_code == 0
        and focused_summary["failed"] == 0
        and focused_summary["error"] == 0,
    }
    c.write_json("focused-results.json", focused)

    full_command = [
        python,
        "-m",
        "pytest",
        "-q",
        "--tb=no",
        "-rfE",
        "-p",
        "no:cacheprovider",
    ]
    full_code, full_text = run(full_command, timeout=3600)
    c.write_text("tests-backend-full.txt", "$ " + " ".join(full_command) + "\n\n" + full_text)
    full_summary = parse_summary(full_text)
    failures, errors = parse_node_ids(full_text)
    full = {
        "source_xml": None,
        "command": full_command,
        "exit_code": full_code,
        "PASS": full_summary["passed"],
        "FAIL": full_summary["failed"],
        "ERROR": full_summary["error"],
        "SKIP": full_summary["skipped"],
        "failing_node_ids": failures,
        "error_node_ids": errors,
    }
    c.write_json("backend-results.json", full)

    baseline = json.loads(c.BASELINE_RESULTS.read_text(encoding="utf-8"))
    baseline_fail = set(baseline.get("failing_node_ids", []))
    baseline_error = set(baseline.get("error_node_ids", []))
    new_fail = sorted(set(failures) - baseline_fail)
    new_error = sorted(set(errors) - baseline_error)
    comparison = {
        "measured_at": c.now(),
        "baseline_source": str(c.BASELINE_RESULTS.relative_to(c.REPO_ROOT)),
        "baseline_sha256": c.sha256_file(c.BASELINE_RESULTS),
        "baseline": {
            "PASS": baseline.get("PASS"),
            "FAIL": baseline.get("FAIL"),
            "ERROR": baseline.get("ERROR"),
            "failing_node_ids": baseline.get("failing_node_ids", []),
            "error_node_ids": baseline.get("error_node_ids", []),
        },
        "final": {
            "PASS": full["PASS"],
            "FAIL": full["FAIL"],
            "ERROR": full["ERROR"],
            "failing_node_ids": failures,
            "error_node_ids": errors,
        },
        "new_fail_node_ids": new_fail,
        "new_error_node_ids": new_error,
        "resolved_fail_node_ids": sorted(baseline_fail - set(failures)),
        "resolved_error_node_ids": sorted(baseline_error - set(errors)),
        "new_fail_count": len(new_fail),
        "new_error_count": len(new_error),
        "known_failures_remain_not_pass": sorted(baseline_fail & set(failures)),
        "BACKEND_REGRESSION": "PASS" if not new_fail and not new_error else "FAIL",
    }
    c.write_json("backend-baseline-comparison.json", comparison)

    print(
        json.dumps(
            {
                "focused": {
                    "exit": focused_code,
                    "pass": focused["PASS"],
                    "fail": focused["FAIL"],
                    "error": focused["ERROR"],
                },
                "full": {
                    "percent": f"{full['PASS']} passed / {full['FAIL']} failed / {full['ERROR']} errors",
                    "new_fail": len(new_fail),
                    "new_error": len(new_error),
                },
            }
        )
    )


if __name__ == "__main__":
    main()
