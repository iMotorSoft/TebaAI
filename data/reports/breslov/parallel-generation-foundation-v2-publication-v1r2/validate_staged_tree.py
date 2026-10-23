#!/usr/bin/env python3
"""Validate that the git index contains exactly the allowlist and that the
staged tree is self-contained (focused tests + corrected preflight + migration)."""
from __future__ import annotations
import hashlib, json, pathlib, shutil, subprocess, sys

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"
TREE = pathlib.Path("/tmp/opencode/staged-tree")
VENV = REPO / "SrvRestAstroLS_v1" / "backend" / ".venv" / "bin" / "python"
BACKEND_REL = "SrvRestAstroLS_v1/backend"
FOCUSED = [
    "tests/test_generation_foundation.py",
    "tests/test_generation_rollback_remediation.py",
    "tests/test_page_first_gateway_generation_order.py",
    "tests/test_page_first_gateway_generation_postgres.py",
    "tests/test_parallel_generation_safety_prerequisites.py",
    "tests/test_content_manager_cleanup.py",
    "tests/test_library_search_hybrid_milvus_alias.py",
]


def sh(*args, cwd=REPO, check=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    allow = json.loads((OUT / "stage-allowlist.json").read_text())
    frozen = json.loads((OUT / "frozen-manifest.json").read_text())
    staged = [line for line in sh("git", "diff", "--cached", "--name-only").stdout.splitlines() if line]
    allow_set, staged_set = set(allow["all_paths"]), set(staged)
    missing = sorted(allow_set - staged_set)
    extra = sorted(staged_set - allow_set)

    hash_checks, hash_mismatches = [], []
    for rel, expected in frozen["candidate_paths"].items():
        try:
            blob = subprocess.run(["git", "cat-file", "-p", f":{rel}"], cwd=REPO,
                                  capture_output=True, check=True).stdout
        except subprocess.CalledProcessError:
            hash_mismatches.append({"path": rel, "error": "not_in_index"})
            continue
        actual = sha_bytes(blob)
        hash_checks.append(rel)
        if actual != expected:
            hash_mismatches.append({"path": rel, "expected": expected, "actual": actual})

    unstaged_product = [
        line for line in sh("git", "diff", "--name-only", "--", *frozen["candidate_paths"]).stdout.splitlines()
    ]

    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir(parents=True)
    sh("git", "checkout-index", "-a", f"--prefix={TREE}/")

    backend = TREE / BACKEND_REL
    env = {"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"}
    import os
    run_env = {**os.environ, **env}
    focused = subprocess.run(
        [str(VENV), "-m", "pytest", "-q", "--junitxml=/tmp/opencode/staged-focused.xml", *FOCUSED],
        cwd=backend, env=run_env, text=True, capture_output=True,
    )
    preflight = subprocess.run(
        [str(VENV), str(TREE / "data/reports/breslov/parallel-generation-foundation-v2-publication-v1r2/publication_preflight.py"),
         "/tmp/opencode/staged-preflight.json", "--label", "v1r2-staged"],
        cwd=backend, env=run_env, text=True, capture_output=True,
    )
    preflight_ok = False
    if pathlib.Path("/tmp/opencode/staged-preflight.json").is_file():
        pf = json.loads(pathlib.Path("/tmp/opencode/staged-preflight.json").read_text())
        preflight_ok = bool(pf.get("ok")) and all(v == 0 for v in pf.get("counts", {}).values())

    discovery = subprocess.run(
        [str(VENV), "-c",
         "import json;from infrastructure.postgres.migrations import _discover_migrations;"
         "print(json.dumps([v for v,_,_ in _discover_migrations()]))"],
        cwd=backend, env=run_env, text=True, capture_output=True,
    )
    try:
        versions = json.loads(discovery.stdout.strip())
    except Exception:
        versions = []

    report = {
        "gate": GATE,
        "allowlist_count": len(allow_set),
        "staged_count": len(staged_set),
        "missing_from_index": missing,
        "extra_in_index": extra,
        "product_hash_checks": len(hash_checks),
        "product_hash_mismatches": hash_mismatches,
        "unstaged_product_paths": unstaged_product,
        "staged_tree_extracted": str(TREE),
        "focused_tests": {
            "returncode": focused.returncode,
            "tail": focused.stdout.strip().splitlines()[-1] if focused.stdout.strip() else "",
            "xml": "/tmp/opencode/staged-focused.xml",
        },
        "preflight": {
            "returncode": preflight.returncode,
            "counts": (json.loads(pathlib.Path("/tmp/opencode/staged-preflight.json").read_text()).get("counts")
                       if pathlib.Path("/tmp/opencode/staged-preflight.json").is_file() else None),
            "ok": preflight_ok,
        },
        "migration_discovery": {
            "versions": versions,
            "includes_043": "043" in versions,
        },
        "PASS": (
            not missing and not extra and not hash_mismatches and not unstaged_product
            and focused.returncode == 0 and preflight_ok and "043" in versions
        ),
    }
    (OUT / "staged-tree-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "allowlist": len(allow_set), "staged": len(staged_set),
        "missing": len(missing), "extra": len(extra),
        "hash_mismatches": len(hash_mismatches), "focused": focused.returncode,
        "preflight": preflight_ok, "includes_043": "043" in versions,
        "PASS": report["PASS"],
    }, indent=2))
    sys.exit(0 if report["PASS"] else 1)


if __name__ == "__main__":
    main()
