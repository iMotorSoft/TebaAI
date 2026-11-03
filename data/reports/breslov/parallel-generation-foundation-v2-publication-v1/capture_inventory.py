"""Capture read-only Git inventory and provisional Foundation bytes; never stage."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PREFIX = OUT.relative_to(ROOT).as_posix() + "/"
BASE = "9882b569e55513dc179eccdc1c465bf31b25cb6a"

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

backend = "SrvRestAstroLS_v1/backend/"
production = [backend + "db/migrations/043_generation_foundation.sql"] + [backend + "modules/library/" + name + ".py" for name in ["generation", "content_manager", "content_manager_cleanup", "hybrid_search", "page_first_gateway", "relation_qa_repository", "simple_research_repository", "source_repository", "text_search"]]
tests = [backend + "tests/" + name + ".py" for name in ["test_generation_foundation", "test_content_manager_cleanup", "test_library_search_hybrid_milvus_alias"]]
historical = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "data/reports/breslov/parallel-generation-foundation-v2").rglob("*") if p.is_file())
candidates = production + tests + historical
raw = git("status", "--porcelain=v1", "-uall")
entries = []
for line in raw.splitlines():
    status, path = line[:2], line[3:]
    if path.startswith(PREFIX):
        continue
    category = "FOUNDATION_V2" if path in production else "FOUNDATION_V2_TEST" if path in tests else "FOUNDATION_V2_REPORT" if path in historical else "PREEXISTING_UNRELATED"
    data = (ROOT / path).read_bytes() if (ROOT / path).is_file() else b""
    entries.append({"path": path, "git_status": status, "classification": category, "sha256": hashlib.sha256(data).hexdigest()})
save("worktree-before.json", {"captured_at": datetime.now(timezone.utc).isoformat(), "note": "Before any code modification/staging; excludes only new publication evidence files. Classification provisional: dependency closure stopped at defect.", "files": entries, "diff_name_status": git("diff", "--name-status"), "cached_name_status": git("diff", "--cached", "--name-status"), "untracked": [e["path"] for e in entries if e["git_status"] == "??"]})
save("baseline-git-state.json", {"branch": git("branch", "--show-current").strip(), "local_head": git("rev-parse", "HEAD").strip(), "tracking_head": git("rev-parse", "origin/feature/console-backend-core").strip(), "ls_remote_head": git("ls-remote", "origin", "refs/heads/feature/console-backend-core").split()[0], "expected": BASE})
save("foundation-v2-candidate-paths.json", {"status": "PROVISIONAL_NOT_APPROVED_FOR_STAGING", "paths": candidates, "count": len(candidates), "unrelated_excluded_count": sum(e["classification"] == "PREEXISTING_UNRELATED" for e in entries), "ambiguous_classification_count": 0, "closure_complete": False, "note": "No claim of complete publication allowlist; stopped on technical defect. Existing mixed cleanup/gateway changes require hunk-level provenance review before future publication."})
save("foundation-v2-versioning-gap.json", {"files": [{"path": p, "status": next(("UNTRACKED" if e["git_status"] == "??" else "MODIFIED" for e in entries if e["path"] == p), "TRACKED" if (ROOT / p).exists() else "MISSING")} for p in candidates]})
manifest = [{"path": p, "sha256": hashlib.sha256((ROOT / p).read_bytes()).hexdigest(), "size_bytes": (ROOT / p).stat().st_size} for p in candidates]
save("publication-candidate-manifest.json", {"scope": "PROVISIONAL_DIAGNOSTIC_SNAPSHOT_NOT_APPROVED_CANDIDATE", "files": manifest})
(OUT / "publication-candidate-hashes.txt").write_text("".join(f"{e['sha256']}  {e['path']}\n" for e in manifest))
save("publication-candidate-frozen-at.json", {"at": datetime.now(timezone.utc).isoformat(), "scope": "Diagnostic snapshot; production/test/migration bytes will not be changed. Not a complete validated candidate."})
save("previous-pass-comparison.json", {"comparison": "NO_PRIOR_HASH", "same_tree_as_historical_pass": "UNPROVEN", "present_historical_files": historical, "historical_gate_json_parseable": False, "historical_gate_issue": "Python True/False literals instead of JSON true/false", "missing_referenced_evidence": ["final-validation.json", "reader-path-inventory.json", "reader-visibility-matrix.json", "cas-contract.md", "cutover-results.json", "rollback-results.json", "current-c-before-foundation.json", "current-c-after-foundation.json", "tests-backend-full.txt", "backend-results.json", "baseline-failure-comparison.json", "secret-scan.json"], "note": "Historical evidence preserved byte-for-byte; claimed 1959 pass / 20 failures cannot be independently tied to current bytes."})
print(json.dumps({"candidate_count": len(candidates), "unrelated": sum(e["classification"] == "PREEXISTING_UNRELATED" for e in entries)}, indent=2))
