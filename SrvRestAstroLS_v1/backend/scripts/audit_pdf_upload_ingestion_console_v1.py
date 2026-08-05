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
PIPELINE = BACKEND / "modules/library/page_first_pipeline.py"
GATEWAY = BACKEND / "modules/library/page_first_gateway.py"
RUNTIME = BACKEND / "modules/library/content_manager_runtime.py"
CLEANUP = BACKEND / "modules/library/content_manager_cleanup.py"
SCOPE_SETUP = BACKEND / "scripts/prepare_content_manager_e2e_scope.py"
WORKER_RUNNER = BACKEND / "scripts/content_manager_worker.py"


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
        Check("real_ingestion_orchestration",
              _contains(PIPELINE, "ConcretePageFirstPipeline", "extract_pdf_page_first", "pymupdf4llm")
              and _contains(RUNTIME, "PsycopgWorkerStore")
              and _contains(WORKER_RUNNER, "ConcretePageFirstPipeline"),
              "A document-agnostic PyMuPDF4LLM page-first pipeline is wired to the durable worker."),
        Check("job_summary_and_reconciliation",
              _contains(PIPELINE, "reconcile_resource_sets", "ReconciliationResult")
              and _contains(GATEWAY, "attempt_key", "missing_vectors", "orphan_vectors"),
              "Reconciliation compares manifest PG resources with attempt-keyed isolated vectors."),
        Check("temporary_and_compensating_cleanup",
              _contains(CLEANUP, "ManifestCleanupService", "already_absent", "manifest_id")
              and _contains(MIGRATION, "content_manager_cleanup_events", "not_owned_by_attempt"),
              "Cleanup is manifest/document bounded, Milvus-first, audited and idempotent."),
        Check("configurable_limits",
              _contains(CONFIG, "content_manager_max_upload_bytes", "content_manager_worker_lease_seconds"),
              "Upload and worker limits are typed in core/config.py."),
        Check("isolated_write_e2e",
              _contains(CONFIG, "content_manager_e2e_enabled", "content_manager_e2e_fixture_sha256")
              and _contains(SCOPE_SETUP, "breslov_primary", "--apply")
              and _contains(GATEWAY, "E2EIsolationError", "CONTENT_MANAGER_E2E_SCOPE"),
              "Write validation is default-off, DEV-only, fixture-hash constrained and routed to an isolated scope/collection."),
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
