#!/usr/bin/env python3
"""Verify a fresh clone of the pushed SHA: bytes, focused tests, preflight,
migration discovery and read-only CURRENT C preservation."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, subprocess, sys

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"
VENV = REPO / "SrvRestAstroLS_v1" / "backend" / ".venv" / "bin" / "python"
BACKEND_REL = "SrvRestAstroLS_v1/backend"
REPORT_REL = "data/reports/breslov/parallel-generation-foundation-v2-publication-v1r2"
FOCUSED = [
    "tests/test_generation_foundation.py",
    "tests/test_generation_rollback_remediation.py",
    "tests/test_page_first_gateway_generation_order.py",
    "tests/test_page_first_gateway_generation_postgres.py",
    "tests/test_parallel_generation_safety_prerequisites.py",
    "tests/test_content_manager_cleanup.py",
    "tests/test_library_search_hybrid_milvus_alias.py",
]


def sh(*args, cwd):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clone", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--out-dir", default=str(OUT))
    args = parser.parse_args()
    clone = pathlib.Path(args.clone).resolve()
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((OUT / "frozen-manifest.json").read_text())
    before = json.loads((OUT / "current-c-before.json").read_text())

    head = sh("git", "rev-parse", "HEAD", cwd=clone).stdout.strip()
    branch = sh("git", "branch", "--show-current", cwd=clone).stdout.strip()
    status = sh("git", "status", "--porcelain", cwd=clone).stdout.strip()
    product_hash_mismatches = []
    product_lines = []
    for rel, expected in frozen["candidate_paths"].items():
        path = clone / rel
        actual = sha(path) if path.is_file() else None
        product_lines.append(f"{rel}  {actual}")
        if actual != expected:
            product_hash_mismatches.append({"path": rel, "expected": expected, "actual": actual})
    product_tree_hash = hashlib.sha256("\n".join(sorted(product_lines)).encode()).hexdigest()

    backend = clone / BACKEND_REL
    run_env = {**os.environ, "PYTHONPATH": "."}
    focused = subprocess.run(
        [str(VENV), "-m", "pytest", "-q", "--junitxml=/tmp/opencode/fresh-focused.xml", *FOCUSED],
        cwd=backend, env=run_env, text=True, capture_output=True,
    )
    preflight = subprocess.run(
        [str(VENV), str(clone / REPORT_REL / "publication_preflight.py"),
         "/tmp/opencode/fresh-preflight.json", "--label", "v1r2-fresh"],
        cwd=backend, env=run_env, text=True, capture_output=True,
    )
    pf = json.loads(pathlib.Path("/tmp/opencode/fresh-preflight.json").read_text()) \
        if pathlib.Path("/tmp/opencode/fresh-preflight.json").is_file() else {}
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

    fresh_c_path = out / "fresh-current-c.json"
    capture = subprocess.run(
        [str(VENV), str(clone / REPORT_REL / "capture_current_c.py"), str(fresh_c_path)],
        cwd=backend, env=run_env, text=True, capture_output=True,
    )
    fresh_c = json.loads(fresh_c_path.read_text()) if fresh_c_path.is_file() else {}
    c_checks = {
        "active_generation_unchanged": (fresh_c.get("active_pointer") or {}).get("generation_id")
            == before["expected"]["active_generation"],
        "chunks_942": (fresh_c.get("chunks") or {}).get("count") == 942,
        "vectors_942": (fresh_c.get("milvus") or {}).get("document_vector_count") == 942,
        "embeddings_942": (fresh_c.get("embeddings") or {}).get("count") == 942,
        "source_sha_unchanged": (fresh_c.get("source") or {}).get("source_sha256")
            == before["source"]["source_sha256"],
        "chunk_digest_unchanged": (fresh_c.get("chunks") or {}).get("digest")
            == before["chunks"]["digest"],
    }

    evidence = {
        "gate": GATE,
        "clone": str(clone),
        "expected_sha": args.expected_sha,
        "head": head,
        "branch": branch,
        "worktree_clean": status == "",
        "product_tree_hash": product_tree_hash,
        "product_hash_mismatches": product_hash_mismatches,
        "focused_tests": {
            "returncode": focused.returncode,
            "tail": focused.stdout.strip().splitlines()[-1] if focused.stdout.strip() else "",
            "xml": "/tmp/opencode/fresh-focused.xml",
        },
        "preflight": {"returncode": preflight.returncode, "ok": preflight_ok,
                      "counts": pf.get("counts")},
        "migration_discovery": {"versions": versions, "includes_043": "043" in versions},
        "current_c": {"capture_returncode": capture.returncode, "checks": c_checks,
                      "fresh_capture": str(fresh_c_path)},
        "PASS": (
            head == args.expected_sha and branch == "feature/console-backend-core"
            and status == "" and not product_hash_mismatches
            and focused.returncode == 0 and preflight_ok and "043" in versions
            and all(c_checks.values())
        ),
    }
    (out / "fresh-tree-smoke-tests.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    (out / "fresh-clone-verification.json").write_text(json.dumps({
        **evidence,
        "verified_commit": head,
        "product_tree_identical": not product_hash_mismatches,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"head": head, "clean": status == "", "product_mismatches": len(product_hash_mismatches),
                      "focused": focused.returncode, "preflight": preflight_ok,
                      "includes_043": "043" in versions, "c_ok": all(c_checks.values()),
                      "PASS": evidence["PASS"]}, indent=2))
    sys.exit(0 if evidence["PASS"] else 1)


if __name__ == "__main__":
    main()
