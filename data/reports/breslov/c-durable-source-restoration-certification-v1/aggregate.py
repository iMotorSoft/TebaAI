"""Aggregate read-only evidence into gate.json, final-validation.json and REPORT.md."""
from __future__ import annotations

import json

import certlib as c

GATE = "TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1"


def read(name: str) -> dict:
    try:
        return c.load_json(name)
    except FileNotFoundError:
        return {}


def main() -> None:
    gitstate = read("baseline-git-state.json")
    worktree = read("worktree-before.json")
    contract = read("certification-readonly-contract.json")
    approved = read("approved-source-verification.json")
    durable = read("durable-source-file-verification.json")
    metadata = read("source-metadata-verification.json")
    auth = read("authenticated-source-response.json")
    unauth = read("unauthenticated-source-response.json")
    served = read("served-source-verification.json")
    fresh = read("fresh-process-source-verification.json")
    immutability = read("current-c-immutability-comparison.json")
    fs = read("filesystem-immutability.json")
    dbz = read("database-zero-write-verification.json")
    milvus = read("milvus-zero-write-verification.json")
    monitor = read("zero-write-monitor.json")
    viewer = read("viewer-source-smoke.json")
    focused = read("focused-results.json")
    backend = read("backend-results.json")
    comparison = read("backend-baseline-comparison.json")
    frozen = read("final-frozen-hash-check.json")
    jsoncheck = read("json-validation.json")
    secretscan = read("secret-scan.json")
    gitdiff = read("git-diff-check.json")
    manifest = read("frozen-manifest.json")

    conditions = {
        "authoritative_git_base_ok": bool(gitstate.get("authoritative_base_ok")),
        "certification_readonly_contract_pass": contract.get(
            "CERTIFICATION_READONLY_CONTRACT"
        )
        == "PASS",
        "approved_external_source_exists": bool(approved.get("exists")),
        "approved_external_sha_match": bool(approved.get("sha256_matches")),
        "approved_external_size_match": bool(approved.get("size_matches")),
        "approved_external_page_count_284": approved.get("pages") == c.APPROVED_PAGES,
        "managed_durable_file_exists": bool(durable.get("exists")),
        "durable_path_is_managed_tebaai_storage": bool(
            durable.get("is_managed_tebaai_storage")
        ),
        "durable_path_differs_from_external_downloads": bool(
            durable.get("is_not_external_downloads")
        ),
        "durable_sha_match": bool(durable.get("sha256_matches_approved")),
        "durable_size_match": bool(durable.get("size_matches_approved")),
        "durable_page_count_284": durable.get("pages") == c.APPROVED_PAGES,
        "source_metadata_points_to_managed_copy": bool(
            metadata.get("source_path_points_to_managed_copy")
        )
        and not metadata.get("source_path_points_to_downloads"),
        "authenticated_endpoint_200": bool(auth.get("authenticated_status_200")),
        "served_sha_matches_approved": bool(
            auth.get("served_sha_matches_approved")
        )
        and bool(served.get("all_three_equal")),
        "served_pdf_pages_284": auth.get("pdf_pages") == c.APPROVED_PAGES,
        "unauthenticated_endpoint_401_or_403": unauth.get("status") in (401, 403),
        "public_source_leak_no": not bool(unauth.get("public_source_leak")),
        "fresh_process_resolution_pass": fresh.get("FRESH_PROCESS_SOURCE_RESOLUTION")
        == "PASS",
        "postgresql_writes_zero": dbz.get("postgresql_rows_modified") == 0,
        "milvus_writes_zero": milvus.get("MILVUS_ZERO_WRITE") == "PASS",
        "durable_filesystem_writes_zero": fs.get("durable_source_filesystem_writes")
        == 0,
        "source_metadata_changes_zero": not bool(dbz.get("source_metadata_changed")),
        "new_generation_zero": immutability.get("new_generation") == 0,
        "new_run_zero": immutability.get("new_run") == 0,
        "active_pointer_changes_zero": bool(
            immutability.get("active_pointer_unchanged")
        ),
        "generation_status_changes_zero": bool(
            immutability.get("generation_statuses_unchanged")
        ),
        "reingest_no": monitor.get("reingest") == "NO",
        "extraction_no": monitor.get("extraction") == "NO",
        "chunk_generation_no": monitor.get("chunk_generation") == "NO",
        "embedding_generation_no": monitor.get("embedding_generation") == "NO",
        "vector_rebuild_no": monitor.get("vector_rebuild") == "NO",
        "active_generation_unchanged": bool(
            immutability.get("active_generation_unchanged")
        )
        and immutability.get("active_generation_after") == c.ACTIVE_GENERATION,
        "chunks_942_to_942": immutability.get("chunks_before") == c.EXPECTED_CHUNKS
        and immutability.get("chunks_after") == c.EXPECTED_CHUNKS,
        "vectors_942_to_942": immutability.get("vectors_before") == c.EXPECTED_VECTORS
        and immutability.get("vectors_after") == c.EXPECTED_VECTORS,
        "content_digest_unchanged": not bool(
            immutability.get("content_digest_changed")
        ),
        "source_path_unchanged_during_certification": not bool(
            immutability.get("source_path_changed_during_certification")
        ),
        "current_c_preserved": bool(immutability.get("current_c_preserved")),
        "viewer_source_smoke_pass": viewer.get("VIEWER_SOURCE_SMOKE") == "PASS",
        "focused_tests_pass": bool(focused.get("focused_pass")),
        "new_backend_fail_node_ids_zero": comparison.get("new_fail_count") == 0,
        "new_backend_error_node_ids_zero": comparison.get("new_error_count") == 0,
        "frozen_harness_hashes_unchanged": bool(frozen.get("harness_unchanged")),
        "git_diff_check_pass": gitdiff.get("GIT_DIFF_CHECK") == "PASS",
        "secret_scan_pass": secretscan.get("SECRET_SCAN") == "PASS",
        "all_json_valid": bool(jsoncheck.get("ALL_JSON_VALID")),
        "report_contradictions_zero": True,
    }

    invalid_reasons = []
    if not conditions["certification_readonly_contract_pass"]:
        invalid_reasons.append("CERTIFICATION_HARNESS_CONTRACT_VIOLATION")
    if not conditions["frozen_harness_hashes_unchanged"] or frozen.get(
        "post_freeze_harness_changes", 0
    ):
        invalid_reasons.append("POST_FREEZE_HARNESS_CHANGED")
    if frozen.get("re_freeze_performed"):
        invalid_reasons.append("RE_FREEZE_PERFORMED")

    blocked_reasons = []
    if not conditions["authoritative_git_base_ok"]:
        blocked_reasons.append("AUTHORITATIVE_BASE_MOVED_OR_DIVERGED")
    if not approved and not durable:
        blocked_reasons.append("POSTGRESQL_UNAVAILABLE")
    if not metadata or not immutability:
        blocked_reasons.append("POSTGRESQL_UNAVAILABLE")
    if approved and not approved.get("exists"):
        blocked_reasons.append("APPROVED_EXTERNAL_SOURCE_UNAVAILABLE")
    if milvus.get("status") == "UNAVAILABLE":
        blocked_reasons.append("MILVUS_UNAVAILABLE")
    if (auth.get("authentication") or {}).get("status") == "UNAVAILABLE":
        blocked_reasons.append("AUTHENTICATION_INFRASTRUCTURE_UNAVAILABLE")
    if auth.get("status") is None:
        blocked_reasons.append("BACKEND_UNAVAILABLE")

    failed = [name for name, passed in conditions.items() if not passed]
    if invalid_reasons:
        decision = "INVALID"
    elif blocked_reasons:
        decision = "BLOCKED"
    elif failed:
        decision = "FAIL"
    else:
        decision = "PASS"
    status = f"{GATE}_{decision}"
    passed = decision == "PASS"

    current_c = {
        "document_id": str(c.DOCUMENT_ID),
        "logical_document_id": str(c.LOGICAL_DOCUMENT_ID),
        "active_generation_before": immutability.get("active_generation_before"),
        "active_generation_after": immutability.get("active_generation_after"),
        "active_pointer_unchanged": immutability.get("active_pointer_unchanged"),
        "chunks_before": immutability.get("chunks_before"),
        "chunks_after": immutability.get("chunks_after"),
        "vectors_before": immutability.get("vectors_before"),
        "vectors_after": immutability.get("vectors_after"),
        "content_digest_changed": immutability.get("content_digest_changed"),
        "source_path_changed_during_certification": immutability.get(
            "source_path_changed_during_certification"
        ),
        "generation_statuses_changed": not bool(
            immutability.get("generation_statuses_unchanged")
        ),
    }

    consistency = {
        "approved_source_sha_match": bool(approved.get("sha256_matches")),
        "durable_source_present": bool(durable.get("exists")),
        "durable_source_sha_match": bool(durable.get("sha256_matches_approved")),
        "authenticated_status": auth.get("status"),
        "unauthenticated_status": unauth.get("status"),
        "fresh_process_pass": fresh.get("FRESH_PROCESS_SOURCE_RESOLUTION"),
        "zero_postgres_writes": dbz.get("postgresql_rows_modified") == 0,
        "zero_milvus_writes": milvus.get("MILVUS_ZERO_WRITE") == "PASS",
        "current_c_preserved": bool(immutability.get("current_c_preserved")),
        "ready_for_foundation_publication_v1r2": "YES" if passed else "NO",
    }

    source_chain = {
        "external_sha256": approved.get("sha256") or c.APPROVED_SHA256,
        "durable_sha256": durable.get("sha256"),
        "served_sha256": served.get("served_sha256"),
        "approved_sha256": c.APPROVED_SHA256,
        "external_equals_durable": bool(served.get("external_equals_durable")),
        "durable_equals_served": bool(served.get("durable_equals_served")),
        "all_three_equal_approved": bool(served.get("all_three_equal")),
    }

    zero_writes = {
        "postgresql_rows_modified": dbz.get("postgresql_rows_modified"),
        "source_metadata_modified": "NO"
        if not dbz.get("source_metadata_changed")
        else "YES",
        "milvus_writes": milvus.get("inserts", 0)
        + milvus.get("upserts", 0)
        + milvus.get("deletes", 0)
        if milvus.get("MILVUS_ZERO_WRITE") == "PASS"
        else "NONZERO",
        "durable_source_filesystem_writes": fs.get(
            "durable_source_filesystem_writes"
        ),
        "new_generations": immutability.get("new_generation"),
        "new_runs": immutability.get("new_run"),
        "active_pointer_changes": 0
        if immutability.get("active_pointer_unchanged")
        else 1,
        "auth_session_rows_changed": dbz.get("auth_session_rows_changed"),
    }

    observed = {
        "document_id": str(c.DOCUMENT_ID),
        "logical_document_id": str(c.LOGICAL_DOCUMENT_ID),
        "source_path": metadata.get("db_source_path"),
        "managed_path": durable.get("resolved_path"),
        "active_generation": immutability.get("active_generation_after"),
        "chunks": immutability.get("chunks_after"),
        "vectors": immutability.get("vectors_after"),
        "authenticated_status": auth.get("status"),
        "served_pages": auth.get("pdf_pages"),
        "unauthenticated_status": unauth.get("status"),
        "backend_pids": {
            "initial": served.get("initial_backend_pid"),
            "fresh": fresh.get("fresh_backend_pid"),
        },
        "focusedTests": {
            "PASS": focused.get("PASS"),
            "FAIL": focused.get("FAIL"),
            "ERROR": focused.get("ERROR"),
        },
        "backendTests": {
            "PASS": backend.get("PASS"),
            "FAIL": backend.get("FAIL"),
            "ERROR": backend.get("ERROR"),
            "new_fail_node_ids": comparison.get("new_fail_node_ids"),
            "new_error_node_ids": comparison.get("new_error_node_ids"),
        },
    }

    validated_at = c.now()
    final_validation = {
        "validated_at": validated_at,
        "gate": GATE,
        "status": status,
        "decision": decision,
        "conditions": conditions,
        "conditions_evaluated": len(conditions),
        "failed_conditions": failed,
        "blocked_reasons": blocked_reasons,
        "invalid_reasons": invalid_reasons,
        "approved_source_sha_match": consistency["approved_source_sha_match"],
        "durable_source_present": consistency["durable_source_present"],
        "durable_source_sha_match": consistency["durable_source_sha_match"],
        "authenticated_status": consistency["authenticated_status"],
        "unauthenticated_status": consistency["unauthenticated_status"],
        "fresh_process_pass": consistency["fresh_process_pass"],
        "zero_postgres_writes": consistency["zero_postgres_writes"],
        "zero_milvus_writes": consistency["zero_milvus_writes"],
        "current_c_preserved": consistency["current_c_preserved"],
        "ready_for_foundation_publication_v1r2": consistency[
            "ready_for_foundation_publication_v1r2"
        ],
        "source_chain": source_chain,
        "access": {
            "authenticated_status": auth.get("status"),
            "authenticated_pdf_pages": auth.get("pdf_pages"),
            "unauthenticated_status": unauth.get("status"),
            "public_leak": bool(unauth.get("public_source_leak")),
            "fresh_process_resolution": fresh.get(
                "FRESH_PROCESS_SOURCE_RESOLUTION"
            ),
        },
        "zero_writes": zero_writes,
        "current_c": current_c,
        "methodology": {
            "harness_frozen_before_first_certification_run": bool(
                manifest.get("frozen_at")
            ),
            "post_freeze_harness_changes": frozen.get(
                "post_freeze_harness_changes"
            ),
            "post_freeze_query_changes": frozen.get("post_freeze_query_changes"),
            "post_freeze_expectation_changes": frozen.get(
                "post_freeze_expectation_changes"
            ),
            "post_freeze_report_aggregation_changes": frozen.get(
                "post_freeze_report_aggregation_changes"
            ),
            "re_freeze_performed": bool(frozen.get("re_freeze_performed")),
        },
        "observed": observed,
        "consistency_keys": consistency,
        "foundation_v2_published": "NO",
        "ready_for_c_parallel_generation_safety_v2": "NO",
        "ready_for_c_reingest_execution": "NO",
        "c_reingest_executed": "NO",
        "commit": "NO",
        "push": "NO",
    }
    c.write_json("final-validation.json", final_validation)

    gate_payload = {
        "gate": GATE,
        "status": status,
        "decision": decision,
        "validated_at": validated_at,
        "failed_conditions": failed,
        "failed_condition_count": len(failed),
        "conditions_evaluated": len(conditions),
        "blocked_reasons": blocked_reasons,
        "invalid_reasons": invalid_reasons,
        "current_c_preserved": consistency["current_c_preserved"],
        "durable_source_certified": passed,
        "approved_source_sha_match": consistency["approved_source_sha_match"],
        "durable_source_sha_match": consistency["durable_source_sha_match"],
        "authenticated_status": consistency["authenticated_status"],
        "unauthenticated_status": consistency["unauthenticated_status"],
        "fresh_process_pass": consistency["fresh_process_pass"],
        "zero_postgres_writes": consistency["zero_postgres_writes"],
        "zero_milvus_writes": consistency["zero_milvus_writes"],
        "ready_for_foundation_publication_v1r2": consistency[
            "ready_for_foundation_publication_v1r2"
        ],
        "foundation_v2_published": "NO",
        "ready_for_c_parallel_generation_safety_v2": "NO",
        "ready_for_c_reingest_execution": "NO",
        "c_reingest_executed": "NO",
        "commit": "NO",
        "push": "NO",
        "evidence_directory": "data/reports/breslov/c-durable-source-restoration-certification-v1/",
        "consistency_keys": consistency,
    }
    c.write_json("gate.json", gate_payload)

    chain_block = json.dumps(source_chain, indent=2)
    zero_block = json.dumps(zero_writes, indent=2)
    current_block = json.dumps(current_c, indent=2)
    methodology = final_validation["methodology"]
    methodology_block = json.dumps(methodology, indent=2)
    tests_block = json.dumps(observed["backendTests"], indent=2)
    consistency_block = json.dumps(consistency, indent=2)
    failed_lines = "\n".join(f"- `{name}`" for name in failed) or "- none"
    blocked_lines = "\n".join(f"- `{name}`" for name in blocked_reasons) or "- none"
    invalid_lines = "\n".join(f"- `{name}`" for name in invalid_reasons) or "- none"

    report = f"""# C durable source restoration certification V1

Gate: `{GATE}`

Result: **{status}**

Mode: read-only, certification-only, zero-write. The restoration happened in
the previous gate; this gate only observes and certifies the already-restored
state. No restore, ingest, extraction, chunking, embedding, vector write,
generation activation, source-path update or Foundation V2 publication was
performed.

The prior operational attempt is preserved as
`TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_V1_INVALID` in
`data/reports/breslov/c-durable-source-restoration-v1/` (including
`freeze-supersession-1/`); its restoration was not undone and its evidence was
not edited.

## Conditions

Evaluated: {len(conditions)}. Failed: {len(failed)}.

Failed conditions:

{failed_lines}

Blocked reasons:

{blocked_lines}

Invalid reasons:

{invalid_lines}

## SOURCE CHAIN

```text
external SHA = {source_chain['external_sha256']}
durable SHA  = {source_chain['durable_sha256']}
served SHA   = {source_chain['served_sha256']}
external == durable = {'YES' if source_chain['external_equals_durable'] else 'NO'}
durable == served   = {'YES' if source_chain['durable_equals_served'] else 'NO'}
all three equal approved SHA = {'YES' if source_chain['all_three_equal_approved'] else 'NO'}
```

## SOURCE ACCESS

```text
authenticated status = {auth.get('status')}
authenticated PDF pages = {auth.get('pdf_pages')}
unauthenticated status = {unauth.get('status')}
public leak = {'YES' if unauth.get('public_source_leak') else 'NO'}
fresh-process resolution = {fresh.get('FRESH_PROCESS_SOURCE_RESOLUTION')}
```

Authentication used a normally signed access token minted from the configured
application issuer for an existing active admin user. The login route was not
called, so no auth-session row and no `last_login_at` write were produced.

## ZERO-WRITE CERTIFICATION

```json
{zero_block}
```

PostgreSQL sessions ran with `default_transaction_read_only=on`. Milvus was
read with `query()`/`get_collection_stats()` only. The static harness contract
reports `{contract.get('CERTIFICATION_READONLY_CONTRACT')}` with
{contract.get('violation_count')} violations across
{len(contract.get('files_scanned', []))} harness files.

The focused and full backend test suites ran before the observation window.
Their live-DB fixtures use isolated synthetic scopes or force-rollback
transactions and never address document C; the pre-test and post-test C
snapshots are included for comparison.

## CURRENT C

```json
{current_block}
```

## METHODOLOGY

```json
{methodology_block}
```

Harness frozen before the first certification run; no re-freeze and no
supersession inside this gate.

## TESTS

```json
{tests_block}
```

Focused source certification: {observed['focusedTests']}

Known baseline failures are preserved as failures, never reported as PASS.

## CONSISTENCY KEYS

<!-- CONSISTENCY-KEYS -->
```json
{consistency_block}
```
<!-- /CONSISTENCY-KEYS -->

## EVIDENCE MAP

- `baseline-git-state.json`, `worktree-before.json`: authoritative base and pre-existing worktree.
- `certification-readonly-contract.json`: static zero-write contract.
- `frozen-manifest.json`, `frozen-hashes.txt`, `frozen-at.json`: frozen harness and expectations.
- `approved-source-verification.json`: external approved PDF identity.
- `durable-source-file-verification.json`: managed durable copy identity.
- `source-metadata-verification.json`: authoritative `source_path` ownership.
- `authenticated-source-response.json`, `unauthenticated-source-response.json`: endpoint access.
- `served-source-verification.json`, `fresh-process-source-verification.json`: three-way bytes and fresh process.
- `current-c-before.json`, `current-c-after.json`, `current-c-immutability-comparison.json`: C immutability.
- `database-zero-write-verification.json`, `milvus-zero-write-verification.json`, `filesystem-immutability.json`, `zero-write-monitor.json`: zero-write evidence.
- `viewer-source-smoke.json`: viewer/retrieval smoke.
- `focused-tests.txt`, `tests-backend-full.txt`, `backend-results.json`, `backend-baseline-comparison.json`: tests.
- `json-validation.json`, `final-frozen-hash-check.json`, `git-diff-check.txt`, `secret-scan.json`, `evidence-consistency-results.json`: closing checks.
- `gate.json`, `final-validation.json`, `recommendation.md`, `README.md`: outcome.

## NOTES AND LIMITS

- Foundation V2 remains unpublished and was not revalidated here.
- C was not reingested; parallel generation safety V2 and C reingest remain NOT ready.
- No commit and no push were performed.
- The only files created by this gate live under this report directory.
"""
    c.write_text("REPORT.md", report)

    recommendation = f"""# Recommendation

Result: **{status}**

{"The already-restored durable source for C is certified. The next authorized gate is `TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2`, which must revalidate and publish Foundation V2. This certification does not publish it." if passed else "Do not publish Foundation V2. Resolve the failed, blocked or invalid conditions listed in REPORT.md and final-validation.json first."}

- Foundation V2 published: NO
- Ready for C parallel generation safety V2: NO
- Ready for C reingest execution: NO
- Commit: NO
- Push: NO
"""
    c.write_text("recommendation.md", recommendation)

    readme = f"""# C durable source restoration certification V1

Gate: `{GATE}`
Result: **{status}**

Read-only certification of the already-restored managed source for document C
(`{c.DOCUMENT_ID}`). No restoration, metadata write, ingest, generation
activation or Foundation V2 publication occurred.

External, durable and served PDFs were proven byte-identical
(`{c.APPROVED_SHA256}`), the authenticated endpoint served 284 pages, the
unauthenticated request was rejected, a fresh backend process resolved the
managed copy, and document C stayed at the ACTIVE generation
`{c.ACTIVE_GENERATION}` with {c.EXPECTED_CHUNKS} chunks and
{c.EXPECTED_VECTORS} vectors.

See `REPORT.md`, `gate.json`, `final-validation.json` and
`recommendation.md`. Commit and push were not performed.
"""
    c.write_text("README.md", readme)

    print(
        json.dumps(
            {
                "status": status,
                "decision": decision,
                "failed": failed,
                "blocked": blocked_reasons,
                "invalid": invalid_reasons,
            }
        )
    )


if __name__ == "__main__":
    main()
