"""Capture the authoritative Git base and the pre-existing worktree state."""
from __future__ import annotations

import certlib as c
import subprocess

EXPECTED_BASE = "9882b569e55513dc179eccdc1c465bf31b25cb6a"
BRANCH = "feature/console-backend-core"


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=c.REPO_ROOT, capture_output=True, text=True
    )
    return (result.stdout + result.stderr).strip()


def main() -> None:
    fetch_output = run_git("fetch", "origin", BRANCH)
    branch = run_git("branch", "--show-current")
    head = run_git("rev-parse", "HEAD")
    tracking = run_git("rev-parse", f"origin/{BRANCH}")
    ls_remote_line = run_git("ls-remote", "origin", f"refs/heads/{BRANCH}")
    ls_remote = ls_remote_line.split()[0] if ls_remote_line else ""
    base_ok = head == tracking == ls_remote == EXPECTED_BASE
    payload = {
        "captured_at": c.now(),
        "repo": str(c.REPO_ROOT),
        "branch": branch,
        "expected_branch": BRANCH,
        "head": head,
        "tracking_head": tracking,
        "ls_remote_head": ls_remote,
        "expected_base": EXPECTED_BASE,
        "fetch_output": fetch_output,
        "local_head_equals_tracking": head == tracking,
        "local_head_equals_ls_remote": head == ls_remote,
        "authoritative_base_ok": base_ok,
        "merge_performed": False,
        "rebase_performed": False,
        "reset_performed": False,
        "force_performed": False,
    }
    c.write_json("baseline-git-state.json", payload)

    status = run_git("status", "--short")
    diff_names = run_git("diff", "--name-status")
    cached_names = run_git("diff", "--cached", "--name-status")
    untracked = run_git("ls-files", "--others", "--exclude-standard")
    worktree = {
        "captured_at": c.now(),
        "repo": str(c.REPO_ROOT),
        "branch": branch,
        "head": head,
        "git_status_short": status.splitlines(),
        "git_status_short_count": len(status.splitlines()),
        "git_diff_name_status": diff_names.splitlines(),
        "git_diff_cached_name_status": cached_names.splitlines(),
        "git_ls_files_others_exclude_standard": untracked.splitlines(),
        "preexisting_worktree_was_not_modified_by_gate": True,
        "forbidden_commands_used": [],
    }
    c.write_json("worktree-before.json", worktree)
    print(
        f"branch={branch} head={head} tracking={tracking} ls_remote={ls_remote} "
        f"base_ok={base_ok} preexisting_status_lines={len(status.splitlines())}"
    )


if __name__ == "__main__":
    main()
