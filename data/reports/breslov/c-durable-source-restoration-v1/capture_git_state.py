"""Capture authoritative git state and worktree inventory (read-only)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
REPORT_DIR = "data/reports/breslov/c-durable-source-restoration-v1/"
EXPECTED_HEAD = "9882b569e55513dc179eccdc1c465bf31b25cb6a"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def entries(*args: str) -> list[list[str]]:
    rows = []
    for line in git(*args).splitlines():
        if not line.strip():
            continue
        rows.append(line.split("\t"))
    return rows


def classify(path: str) -> str:
    if path.startswith(REPORT_DIR):
        return "GATE_EVIDENCE"
    if path.startswith("data/reports/"):
        return "PREEXISTING_REPORT"
    if path.startswith("SrvRestAstroLS_v1/backend/"):
        return "PREEXISTING_BACKEND"
    if path.startswith("SrvRestAstroLS_v1/astro/"):
        return "PREEXISTING_FRONTEND"
    if path.startswith("SrvRestAstroLS_v1/docs/"):
        return "PREEXISTING_DOCS"
    return "PREEXISTING_OTHER"


def main() -> None:
    head = git("rev-parse", "HEAD").strip()
    branch = git("branch", "--show-current").strip()
    tracking = git("rev-parse", "origin/feature/console-backend-core").strip()
    ls_remote = git("ls-remote", "origin", "refs/heads/feature/console-backend-core").split()[0]

    modified = entries("diff", "--name-status")
    staged = entries("diff", "--cached", "--name-status")
    untracked = [row[0] for row in entries("ls-files", "--others", "--exclude-standard")]
    status = [line for line in git("status", "--short").splitlines() if line.strip()]

    classified = []
    for changeset, rows in (("modified", modified), ("staged", staged)):
        for row in rows:
            if len(row) < 2:
                continue
            classified.append(
                {"state": changeset, "code": row[0], "path": row[1], "category": classify(row[1])}
            )
    for path in untracked:
        classified.append(
            {"state": "untracked", "code": "??", "path": path, "category": classify(path)}
        )

    counts: dict[str, int] = {}
    for item in classified:
        counts[item["category"]] = counts.get(item["category"], 0) + 1

    baseline = {
        "branch": branch,
        "local_head": head,
        "tracking_head": tracking,
        "ls_remote_head": ls_remote,
        "heads_match": head == tracking == ls_remote,
        "head_is_authoritative_expected": head == EXPECTED_HEAD,
        "expected_head": EXPECTED_HEAD,
        "staged_changes_at_start": len(staged),
        "preexisting_worktree_preserved": True,
        "git_precheck": "PASS" if head == tracking == ls_remote == EXPECTED_HEAD else "BLOCKED",
    }
    (OUT / "baseline-git-state.json").write_text(json.dumps(baseline, indent=2) + "\n")

    inventory = {
        "source": "git status --short / diff --name-status / diff --cached --name-status / ls-files --others",
        "captured_at_gate_start": True,
        "status_short": status,
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "classified": classified,
        "category_counts": counts,
        "preexisting_product_code_modified_before_gate": sorted(
            {item["path"] for item in classified
             if item["state"] in ("modified", "staged")
             and item["path"].startswith("SrvRestAstroLS_v1/")
             and not item["path"].startswith(REPORT_DIR)}
        ),
    }
    (OUT / "worktree-before.json").write_text(json.dumps(inventory, indent=2) + "\n")
    print(json.dumps({"git_precheck": baseline["git_precheck"], "category_counts": counts}))
    if baseline["git_precheck"] != "PASS":
        raise SystemExit("AUTHORITATIVE_BASE_MOVED_OR_DIVERGED")


if __name__ == "__main__":
    main()
