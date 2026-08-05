#!/usr/bin/env python3
"""Read-only source audit for the Content Manager V1 development gate.

This audit never uploads files, opens service connections, applies migrations, or
writes corpus data. It verifies whether the checked-in implementation contains
the minimum structural controls needed before any isolated real-ingestion test.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "SrvRestAstroLS_v1" / "backend"
SERVICE = BACKEND / "modules/library/content_manager.py"
ROUTES = BACKEND / "modules/library/routes.py"
MIGRATION = BACKEND / "db/migrations/040_content_manager_uploads_and_jobs.sql"


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    evidence: str


def _contains(path: Path, *needles: str) -> bool:
    text = path.read_text(encoding="utf-8")
    return all(needle in text for needle in needles)


def run_audit() -> dict[str, object]:
    checks = [
        Check(
            "endpoints",
            _contains(ROUTES, '"/admin/content/uploads"', '"/admin/content/jobs"', "/diagnostic"),
            "Upload, job, detail, retry, cancel and diagnostic route declarations are present.",
        ),
        Check(
            "coarse_role_permissions",
            _contains(ROUTES, 'user_role not in ("admin", "editor")'),
            "Routes reject roles outside admin/editor, but this does not prove tenant scope.",
        ),
        Check(
            "tenant_scoped_resource_access",
            False,
            "get_upload/get_job/diagnostic queries are keyed only by resource id; effective organization/workspace/project context is not enforced.",
        ),
        Check(
            "state_machine_transition_validation",
            False,
            "Stages are enumerated, but update_job_stage has no allowed-transition graph or compare-and-swap worker ownership.",
        ),
        Check(
            "duplicate_policy",
            False,
            "Exact duplicates are classified but create_job does not reject them; filename/hash classifications are incomplete.",
        ),
        Check(
            "ready_rejected",
            _contains(SERVICE, 'req.requested_status == "ready"'),
            "The service rejects requested_status=ready.",
        ),
        Check(
            "idempotent_concurrent_job_creation",
            False,
            "A select-then-insert check exists without a database uniqueness constraint or atomic conflict handling.",
        ),
        Check(
            "real_ingestion_orchestration",
            False,
            "No worker or reusable page-first pipeline is invoked; a created job remains in validating.",
        ),
        Check(
            "job_summary",
            _contains(SERVICE, "get_diagnostic", "canonical_pages", "pg_embedding_count"),
            "A partial PostgreSQL diagnostic exists; textual pages, Milvus consistency, warnings and cleanup are not computed.",
        ),
        Check(
            "temporary_file_cleanup",
            False,
            "Failure cleanup exists, but no expiry sweeper, success cleanup, retention policy enforcement or cleanup audit exists.",
        ),
        Check(
            "configurable_limits",
            False,
            "Upload limits and TTL are module constants rather than typed core/config.py settings.",
        ),
        Check(
            "database_constraints",
            _contains(MIGRATION, "content_manager_uploads", "content_manager_jobs"),
            "Tables exist, but tenant/document/user FKs, state checks and idempotency uniqueness are absent.",
        ),
    ]
    blockers = [check.name for check in checks if not check.passed]
    return {
        "audit": "TEBAAI_PDF_UPLOAD_INGESTION_CONSOLE_V1",
        "mode": "read_only_source_audit",
        "writes_performed": False,
        "services_contacted": [],
        "status": "BLOCKED" if blockers else "PASS",
        "checks": [asdict(check) for check in checks],
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()
    result = run_audit()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Content Manager V1 audit: {result['status']}")
        for check in result["checks"]:
            marker = "PASS" if check["passed"] else "BLOCKED"
            print(f"[{marker}] {check['name']}: {check['evidence']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
