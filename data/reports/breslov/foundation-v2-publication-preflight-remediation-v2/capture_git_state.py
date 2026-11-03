"""Capture the authoritative git state and classify the preexisting worktree.

Read-only: only `git` queries, no writes to the repository.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
REPORT_DIR = "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2/"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def entries(*args: str) -> list[list[str]]:
    rows = []
    for line in git(*args).splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        rows.append(parts)
    return rows


def classify(path: str) -> str:
    if path.startswith(REPORT_DIR):
        return "PUBLICATION_HARNESS"
    if path == "SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py":
        return "PUBLICATION_FIXTURE"
    if "page_first_gateway" in path or "page-first-gateway" in path:
        return "GATEWAY_REMEDIATION"
    if "rollback" in path or "parallel-generation-rollback" in path:
        return "ROLLBACK_REMEDIATION"
    if "publication" in path and path.startswith("data/reports"):
        return "REPORT"
    if path.startswith("SrvRestAstroLS_v1/backend/modules/library/generation.py"):
        return "FOUNDATION_PRODUCT"
    if path.startswith("SrvRestAstroLS_v1/backend/db/migrations/043_"):
        return "FOUNDATION_PRODUCT"
    if path.startswith("SrvRestAstroLS_v1/backend/tests/"):
        return "TEST"
    if path.startswith("data/reports/"):
        return "REPORT"
    if path.startswith("SrvRestAstroLS_v1/astro/"):
        return "PREEXISTING_UNRELATED"
    if path.startswith("SrvRestAstroLS_v1/docs/"):
        return "REPORT"
    return "PREEXISTING_UNRELATED"


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
        "base_remote_head": head,
        "heads_match": head == tracking == ls_remote,
        "head_is_authoritative_expected": head
        == "9882b569e55513dc179eccdc1c465bf31b25cb6a",
        "worktree_clean_of_staged_changes": not staged,
        "preexisting_scope": "declared by previous gates; preserved untouched",
    }
    (OUT / "baseline-git-state.json").write_text(
        json.dumps(baseline, indent=2) + "\n"
    )

    inventory = {
        "source": "git status --short / diff --name-status / diff --cached / ls-files --others",
        "status_short": status,
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "classified": classified,
        "category_counts": counts,
        "ambiguous": [item for item in classified if item["category"] == "AMBIGUOUS"],
        "ambiguous_count": sum(1 for item in classified if item["category"] == "AMBIGUOUS"),
    }
    (OUT / "worktree-before.json").write_text(json.dumps(inventory, indent=2) + "\n")

    diff_check = subprocess.run(
        ["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True
    )
    (OUT / "git-diff-check.txt").write_text(
        f"$ git diff --check\nexit_code={diff_check.returncode}\n"
        f"{diff_check.stdout}{diff_check.stderr}"
    )
    print(json.dumps({"heads_match": baseline["heads_match"], "category_counts": counts}))
    assert baseline["heads_match"], "authoritative base diverged"
    assert inventory["ambiguous_count"] == 0, "ambiguous worktree entries"


if __name__ == "__main__":
    main()
