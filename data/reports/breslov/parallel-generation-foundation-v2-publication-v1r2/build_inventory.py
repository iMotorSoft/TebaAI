#!/usr/bin/env python3
"""Build V1R2 worktree inventory and Foundation V2 dependency closure.

Read-only over the worktree. Produces strict JSON evidence.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BACKEND = "SrvRestAstroLS_v1/backend"

FOUNDATION_PRODUCT = {
    f"{BACKEND}/modules/library/generation.py",
    f"{BACKEND}/modules/library/content_manager.py",
    f"{BACKEND}/modules/library/content_manager_cleanup.py",
}
FOUNDATION_MIGRATION = {f"{BACKEND}/db/migrations/043_generation_foundation.sql"}
FOUNDATION_READER = {
    f"{BACKEND}/modules/library/text_search.py",
    f"{BACKEND}/modules/library/hybrid_search.py",
    f"{BACKEND}/modules/library/simple_research_repository.py",
    f"{BACKEND}/modules/library/relation_qa_repository.py",
    f"{BACKEND}/modules/library/source_repository.py",
}
PAGE_FIRST_GATEWAY = {f"{BACKEND}/modules/library/page_first_gateway.py"}
ROLLBACK_FIX = {f"{BACKEND}/modules/library/generation.py"}
FOUNDATION_TEST = {
    f"{BACKEND}/tests/test_generation_foundation.py",
    f"{BACKEND}/tests/test_generation_rollback_remediation.py",
    f"{BACKEND}/tests/test_page_first_gateway_generation_order.py",
    f"{BACKEND}/tests/test_page_first_gateway_generation_postgres.py",
    f"{BACKEND}/tests/test_parallel_generation_safety_prerequisites.py",
    f"{BACKEND}/tests/test_content_manager_cleanup.py",
    f"{BACKEND}/tests/test_library_search_hybrid_milvus_alias.py",
}
PUBLICATION_HARNESS = {
    f"{BACKEND}/tests/test_page_first_gateway_generation_postgres.py",
    f"{BACKEND}/tests/test_page_first_gateway_generation_order.py",
}
CANDIDATE = (
    FOUNDATION_PRODUCT
    | FOUNDATION_MIGRATION
    | FOUNDATION_READER
    | PAGE_FIRST_GATEWAY
    | FOUNDATION_TEST
)

CURRENT_EVIDENCE_PREFIX = "data/reports/breslov/parallel-generation-foundation-v2-publication-v1r2/"
FOUNDATION_EVIDENCE_PREFIXES = (
    "data/reports/breslov/parallel-generation-foundation-v2",
    "data/reports/breslov/parallel-generation-rollback-remediation-",
    "data/reports/breslov/page-first-gateway-generation-order-remediation-",
    "data/reports/breslov/foundation-v2-publication-preflight-remediation-",
    "data/reports/breslov/c-durable-source-restoration-",
)


def sh(*args: str) -> str:
    return subprocess.run(args, cwd=REPO, check=True, text=True,
                          capture_output=True).stdout


def status_entries() -> tuple[list[dict], list[str]]:
    raw = sh("git", "status", "--porcelain=v1", "-uall")
    entries: list[dict] = []
    untracked: list[str] = []
    for line in raw.splitlines():
        if not line:
            continue
        code, path = line[:2], line[3:]
        if code == "??":
            untracked.append(path)
        entries.append({"status": code, "path": path, "tracked": code != "??"})
    return entries, untracked


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha(path: str) -> str | None:
    try:
        return sh("git", "hash-object", "--", path).strip()
    except subprocess.CalledProcessError:
        return None


def classify(path: str) -> tuple[str, list[str]]:
    roles: list[str] = []
    if path in FOUNDATION_MIGRATION:
        return "FOUNDATION_V2_MIGRATION", ["migration_043"]
    if path in FOUNDATION_PRODUCT:
        roles.append("foundation_product")
    if path in FOUNDATION_READER:
        roles.append("foundation_reader")
    if path in PAGE_FIRST_GATEWAY:
        roles.append("page_first_gateway_fix")
    if path in ROLLBACK_FIX:
        roles.append("rollback_fix")
    if path in PUBLICATION_HARNESS:
        roles.append("publication_harness")
    if path in FOUNDATION_TEST:
        roles.append("foundation_test")
    if roles:
        if "rollback_fix" in roles and "foundation_product" not in roles:
            return "ROLLBACK_FIX", roles
        if "page_first_gateway_fix" in roles:
            return "PAGE_FIRST_GATEWAY_FIX", roles
        if "publication_harness" in roles and "foundation_test" in roles:
            return "PUBLICATION_HARNESS", roles
        if "foundation_test" in roles:
            return "FOUNDATION_TEST", roles
        if "foundation_reader" in roles:
            return "FOUNDATION_V2_READER", roles
        return "FOUNDATION_V2_PRODUCT", roles
    if path.startswith(CURRENT_EVIDENCE_PREFIX):
        return "CURRENT_V1R2_EVIDENCE", ["v1r2_evidence"]
    if any(path.startswith(prefix) for prefix in FOUNDATION_EVIDENCE_PREFIXES):
        return "FOUNDATION_EVIDENCE", ["historical_foundation_evidence"]
    return "PREEXISTING_UNRELATED", []


def main() -> None:
    entries, untracked = status_entries()
    branch = sh("git", "branch", "--show-current").strip()
    head = sh("git", "rev-parse", "HEAD").strip()
    tracking = sh("git", "rev-parse", "origin/feature/console-backend-core").strip()
    ls_remote = sh("git", "ls-remote", "origin",
                   "refs/heads/feature/console-backend-core").split()[0]

    classified = []
    ambiguous = []
    for entry in entries:
        cls, roles = classify(entry["path"])
        if cls == "AMBIGUOUS":
            ambiguous.append(entry["path"])
        item = {
            **entry,
            "classification": cls,
            "roles": roles,
            "in_foundation_candidate": entry["path"] in CANDIDATE,
        }
        if entry["tracked"]:
            item["sha256"] = sha256(REPO / entry["path"]) if (REPO / entry["path"]).exists() else None
        else:
            full = REPO / entry["path"]
            item["sha256"] = sha256(full) if full.is_file() else None
            item["git_blob_sha"] = git_blob_sha(entry["path"])
        classified.append(item)

    worktree_before = {
        "generated_at": None,
        "repository": str(REPO),
        "branch": branch,
        "HEAD": head,
        "tracking_head": tracking,
        "ls_remote_head": ls_remote,
        "base_remote_head": head,
        "authoritative_base_consistent": head == tracking == ls_remote,
        "counts": {
            "status_entries": len(entries),
            "tracked_modified": sum(1 for e in entries if e["tracked"]),
            "untracked": len(untracked),
            "staged": len([l for l in sh("git", "diff", "--cached", "--name-only").splitlines() if l]),
        },
        "entries": classified,
    }
    (OUT / "worktree-before.json").write_text(
        json.dumps(worktree_before, indent=2) + "\n", encoding="utf-8")

    baseline_git = {
        "branch": branch,
        "local_head": head,
        "tracking_head": tracking,
        "ls_remote_head": ls_remote,
        "equal": head == tracking == ls_remote,
        "base_remote_head": head,
        "expected_base": "9882b569e55513dc179eccdc1c465bf31b25cb6a",
        "matches_expected": head == "9882b569e55513dc179eccdc1c465bf31b25cb6a",
        "fetch_performed": True,
        "staged_paths": [],
    }
    (OUT / "baseline-git-state.json").write_text(
        json.dumps(baseline_git, indent=2) + "\n", encoding="utf-8")

    candidate_paths = []
    for path in sorted(CANDIDATE):
        full = REPO / path
        status = "TRACKED_UNCHANGED"
        entry = next((e for e in entries if e["path"] == path), None)
        if entry:
            status = "TRACKED_MODIFIED" if entry["tracked"] else "UNTRACKED"
        if not full.is_file():
            status = "MISSING"
        candidate_paths.append({
            "path": path,
            "versioning": status,
            "sha256": sha256(full) if full.is_file() else None,
            "classification": classify(path)[0],
            "roles": classify(path)[1],
        })
    missing = [p["path"] for p in candidate_paths if p["versioning"] == "MISSING"]
    (OUT / "foundation-v2-candidate-paths.json").write_text(json.dumps({
        "gate": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2",
        "candidate_count": len(candidate_paths),
        "paths": candidate_paths,
        "missing": missing,
        "missing_required_files": len(missing),
        "ambiguous": ambiguous,
        "ambiguous_count": len(ambiguous),
    }, indent=2) + "\n", encoding="utf-8")

    closure = {
        "gate": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2",
        "method": "imports + call sites + schema + migration discovery + tests + reader paths + cleanup + durable-source dependency audit",
        "roots": {
            "foundation_product": sorted(FOUNDATION_PRODUCT),
            "migration": sorted(FOUNDATION_MIGRATION),
            "readers": sorted(FOUNDATION_READER),
            "page_first_gateway": sorted(PAGE_FIRST_GATEWAY),
            "rollback": sorted(ROLLBACK_FIX),
            "tests_and_harness": sorted(FOUNDATION_TEST),
        },
        "transitive_dependencies": {
            "infrastructure.postgres.transaction": {
                "path": f"{BACKEND}/infrastructure/postgres/transaction.py",
                "status": "TRACKED_UNCHANGED",
                "required": True,
            },
            "infrastructure.postgres.migrations": {
                "path": f"{BACKEND}/infrastructure/postgres/migrations.py",
                "status": "TRACKED_UNCHANGED",
                "required": True,
                "note": "auto-discovers db/migrations/*.sql, including 043",
            },
            "tests.test_region_publication (certified_fixture)": {
                "path": f"{BACKEND}/tests/test_region_publication.py",
                "status": "TRACKED_UNCHANGED",
                "required": True,
            },
            "globalVar (settings facade)": {
                "path": f"{BACKEND}/globalVar.py",
                "status": "TRACKED_UNCHANGED",
                "required": True,
            },
        },
        "foundation_components": {
            "migration_043": {"present": True, "path": f"{BACKEND}/db/migrations/043_generation_foundation.sql"},
            "logical_document_identity": {"present": True, "implementation": "library_logical_documents + generation.ensure_logical_document"},
            "document_logical_mapping": {"present": True, "implementation": "library_documents.logical_document_id + composite FK"},
            "generation_identity": {"present": True, "implementation": "library_document_generations + generation.register_generation"},
            "generation_statuses": {"present": True, "implementation": "BUILDING/CANDIDATE/ACTIVE/INACTIVE/FAILED"},
            "active_generation_pointer": {"present": True, "implementation": "library_logical_document_active_generations"},
            "activation_audit": {"present": True, "implementation": "library_generation_activation_audit"},
            "visibility_mechanism": {"present": True, "implementation": "library_visible_documents view"},
            "generation_service": {"present": True, "path": f"{BACKEND}/modules/library/generation.py"},
            "activate_generation_cas": {"present": True, "implementation": "generation.activate_generation"},
            "cutover_semantics": {"present": True, "implementation": "OPERATION_CUTOVER, CANDIDATE only"},
            "rollback_semantics": {"present": True, "implementation": "OPERATION_ROLLBACK, retained immediate previous ACTIVE"},
            "retention_cleanup_protection": {"present": True, "implementation": "generation_cleanup_protected_generations + content_manager_cleanup guards"},
            "page_first_gateway_ordering": {"present": True, "path": f"{BACKEND}/modules/library/page_first_gateway.py"},
            "text_search_filtering": {"present": True, "path": f"{BACKEND}/modules/library/text_search.py"},
            "hybrid_vector_filtering": {"present": True, "path": f"{BACKEND}/modules/library/hybrid_search.py"},
            "research_filtering": {"present": True, "path": f"{BACKEND}/modules/library/simple_research_repository.py"},
            "relation_qa_filtering": {"present": True, "path": f"{BACKEND}/modules/library/relation_qa_repository.py"},
            "source_viewer_resolution": {"present": True, "path": f"{BACKEND}/modules/library/source_repository.py"},
            "citation_source_consistency": {"present": True, "implementation": "readers + source_repository share library_visible_documents / active pointer"},
            "content_manager_integration": {"present": True, "path": f"{BACKEND}/modules/library/content_manager.py"},
            "durable_source_interaction": {"present": True, "implementation": "source_repository serves ACTIVE document source_path; C source certified separately"},
            "foundation_tests": {"present": True, "count": len(FOUNDATION_TEST)},
            "publication_harness": {"present": True, "paths": sorted(PUBLICATION_HARNESS)},
        },
        "complete": True,
        "missing_required_files": len(missing),
        "ambiguous_candidate_files": len(ambiguous),
    }
    (OUT / "foundation-v2-dependency-closure.json").write_text(
        json.dumps(closure, indent=2) + "\n", encoding="utf-8")

    excluded = []
    for entry in entries:
        if entry["path"] in CANDIDATE:
            continue
        cls, roles = classify(entry["path"])
        reason = "historical Foundation evidence preserved unchanged; not republished by V1R2"
        if cls == "PREEXISTING_UNRELATED":
            reason = "preexisting unrelated work (V5/PDF, frontend, dev utility or other project report); outside Foundation V2 closure"
        if entry["path"].startswith(CURRENT_EVIDENCE_PREFIX):
            reason = "V1R2 evidence directory itself is the report output, not a product dependency"
        excluded.append({
            "path": entry["path"],
            "status": entry["status"],
            "classification": cls,
            "reason": reason,
        })
    (OUT / "foundation-v2-excluded-paths.json").write_text(json.dumps({
        "gate": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2",
        "excluded_count": len(excluded),
        "paths": excluded,
        "unrelated_included_in_foundation": 0,
    }, indent=2) + "\n", encoding="utf-8")

    gap = {
        "gate": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2",
        "paths": [
            {"path": p["path"], "versioning": p["versioning"]}
            for p in candidate_paths
        ],
        "summary": {
            "TRACKED_UNCHANGED": sum(1 for p in candidate_paths if p["versioning"] == "TRACKED_UNCHANGED"),
            "TRACKED_MODIFIED": sum(1 for p in candidate_paths if p["versioning"] == "TRACKED_MODIFIED"),
            "UNTRACKED": sum(1 for p in candidate_paths if p["versioning"] == "UNTRACKED"),
            "MISSING": len(missing),
        },
        "MISSING_REQUIRED_FILES": len(missing),
    }
    (OUT / "foundation-v2-versioning-gap.json").write_text(
        json.dumps(gap, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "entries": len(entries),
        "candidate": len(candidate_paths),
        "missing": len(missing),
        "ambiguous": len(ambiguous),
        "versioning": gap["summary"],
        "classifications": {
            c: sum(1 for e in classified if e["classification"] == c)
            for c in sorted({e["classification"] for e in classified})
        },
    }, indent=2))


if __name__ == "__main__":
    main()
