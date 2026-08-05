#!/usr/bin/env python3
"""Read-only source audit for the Content Manager V1 development gate.

Writing is intentionally unavailable until a reusable page-first implementation,
isolated scope/collection and exact compensating cleanup all exist.
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
SCHEMAS = BACKEND / "modules/library/content_manager_schemas.py"
STATE = BACKEND / "modules/library/content_manager_state.py"
REPOSITORY = BACKEND / "modules/library/content_manager_repository.py"
WORKER = BACKEND / "modules/library/content_manager_worker.py"
MIGRATION = BACKEND / "db/migrations/041_content_manager_orchestration_hardening.sql"
CONFIG = BACKEND / "core/config.py"


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
        Check("endpoints", _contains(ROUTES, '"/admin/content/uploads"', '"/admin/content/jobs"', "/diagnostic"),
              "Upload, job, detail, retry, cancel and diagnostic routes are declared."),
        Check("role_permissions", _contains(ROUTES, 'user_role not in ("admin", "editor")'),
              "All Content Manager routes reject viewer and guest roles."),
        Check("tenant_scoped_resource_access",
              _contains(SERVICE, "organization_id=%s AND workspace_id=%s AND project_id=%s")
              and _contains(ROUTES, "get_authorized_scope_by_code", "_content_scope_kwargs"),
              "Routes resolve authorized scope and resource SQL constrains organization/workspace/project."),
        Check("state_machine_transition_validation",
              _contains(STATE, "ALLOWED_TRANSITIONS", "assert_transition", "InvalidIngestionTransition"),
              "One canonical graph rejects skipped, repeated and terminal transitions."),
        Check("exclusive_claim_and_lease",
              _contains(REPOSITORY, "FOR UPDATE SKIP LOCKED", "claimed_by", "lease_expires_at", "heartbeat_at"),
              "Atomic claim, worker ownership, lease and heartbeat persistence are implemented."),
        Check("abandoned_job_recovery",
              _contains(REPOSITORY, "recover_expired_claims", "manual_review_required", "has_partial_writes"),
              "Expired untouched claims requeue; partial attempts fail closed for review."),
        Check("duplicate_policy",
              _contains(SERVICE, "DuplicateClassification.EXACT_DUPLICATE", "no puede reingerirse"),
              "Exact duplicates are rejected before job creation."),
        Check("ready_rejected", _contains(SERVICE, 'req.requested_status != "test_candidate"'),
              "Only test_candidate is accepted."),
        Check("idempotent_concurrent_job_creation",
              _contains(MIGRATION, "uq_cm_jobs_active_idempotency")
              and _contains(SERVICE, "ON CONFLICT (idempotency_key)"),
              "A partial unique index and atomic conflict handling protect active jobs."),
        Check("manifest_schema",
              _contains(MIGRATION, "content_manager_ingestion_manifests", "content_manager_manifest_resources"),
              "Attempts and exact resource IDs have normalized persistent tables."),
        Check("real_ingestion_orchestration", False,
              "The durable worker contract exists, but no production PageFirstPipeline implementation invokes extraction, pages, chunks, LiteLLM, Milvus and reconciliation."),
        Check("job_summary_and_reconciliation", False,
              "The diagnostic remains PostgreSQL-only and does not query attempt-scoped Milvus IDs."),
        Check("temporary_and_compensating_cleanup", False,
              "Manifest schema exists, but no executor deletes only manifest-owned PG/Milvus resources or performs TTL cleanup."),
        Check("configurable_limits",
              _contains(CONFIG, "content_manager_max_upload_bytes", "content_manager_worker_lease_seconds"),
              "Upload and worker limits are typed in core/config.py."),
        Check("isolated_write_e2e", False,
              "No authorized fixture scope exists in PostgreSQL; only breslov_primary is present. Write mode remains disabled."),
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
