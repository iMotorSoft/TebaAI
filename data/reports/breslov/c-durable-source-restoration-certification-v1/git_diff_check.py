"""Run ``git diff --check`` and persist its exact output."""
from __future__ import annotations

import subprocess

import certlib as c


def main() -> None:
    result = subprocess.run(
        ["git", "diff", "--check"],
        cwd=c.REPO_ROOT,
        capture_output=True,
        text=True,
    )
    body = (
        "$ git diff --check\n"
        f"exit_code={result.returncode}\n"
        "--- stdout ---\n"
        f"{result.stdout}"
        "--- stderr ---\n"
        f"{result.stderr}"
    )
    c.write_text("git-diff-check.txt", body)
    payload = {
        "checked_at": c.now(),
        "command": "git diff --check",
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "GIT_DIFF_CHECK": "PASS" if result.returncode == 0 else "FAIL",
    }
    c.write_json("git-diff-check.json", payload)
    print(f"exit={result.returncode} -> {payload['GIT_DIFF_CHECK']}")
    if result.returncode != 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
