# C durable source restoration certification V1

Gate: `TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1`

Result: **TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1_PASS**

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

Evaluated: 47. Failed: 0.

Failed conditions:

- none

Blocked reasons:

- none

Invalid reasons:

- none

## SOURCE CHAIN

```text
external SHA = 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a
durable SHA  = 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a
served SHA   = 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a
external == durable = YES
durable == served   = YES
all three equal approved SHA = YES
```

## SOURCE ACCESS

```text
authenticated status = 200
authenticated PDF pages = 284
unauthenticated status = 401
public leak = NO
fresh-process resolution = PASS
```

Authentication used a normally signed access token minted from the configured
application issuer for an existing active admin user. The login route was not
called, so no auth-session row and no `last_login_at` write were produced.

## ZERO-WRITE CERTIFICATION

```json
{
  "postgresql_rows_modified": 0,
  "source_metadata_modified": "NO",
  "milvus_writes": 0,
  "durable_source_filesystem_writes": 0,
  "new_generations": 0,
  "new_runs": 0,
  "active_pointer_changes": 0,
  "auth_session_rows_changed": false
}
```

PostgreSQL sessions ran with `default_transaction_read_only=on`. Milvus was
read with `query()`/`get_collection_stats()` only. The static harness contract
reports `PASS` with
0 violations across
19 harness files.

The focused and full backend test suites ran before the observation window.
Their live-DB fixtures use isolated synthetic scopes or force-rollback
transactions and never address document C; the pre-test and post-test C
snapshots are included for comparison.

## CURRENT C

```json
{
  "document_id": "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa",
  "logical_document_id": "db200a31-b547-5668-d968-06d0ec36ad95",
  "active_generation_before": "1a8af56b-fc17-d9f9-ffc2-9efde54aa95b",
  "active_generation_after": "1a8af56b-fc17-d9f9-ffc2-9efde54aa95b",
  "active_pointer_unchanged": true,
  "chunks_before": 942,
  "chunks_after": 942,
  "vectors_before": 942,
  "vectors_after": 942,
  "content_digest_changed": false,
  "source_path_changed_during_certification": false,
  "generation_statuses_changed": false
}
```

## METHODOLOGY

```json
{
  "harness_frozen_before_first_certification_run": true,
  "post_freeze_harness_changes": 0,
  "post_freeze_query_changes": 0,
  "post_freeze_expectation_changes": 0,
  "post_freeze_report_aggregation_changes": 0,
  "re_freeze_performed": false
}
```

Harness frozen before the first certification run; no re-freeze and no
supersession inside this gate.

## TESTS

```json
{
  "PASS": 1998,
  "FAIL": 20,
  "ERROR": 0,
  "new_fail_node_ids": [],
  "new_error_node_ids": []
}
```

Focused source certification: {'PASS': 40, 'FAIL': 0, 'ERROR': 0}

Known baseline failures are preserved as failures, never reported as PASS.

## CONSISTENCY KEYS

<!-- CONSISTENCY-KEYS -->
```json
{
  "approved_source_sha_match": true,
  "durable_source_present": true,
  "durable_source_sha_match": true,
  "authenticated_status": 200,
  "unauthenticated_status": 401,
  "fresh_process_pass": "PASS",
  "zero_postgres_writes": true,
  "zero_milvus_writes": true,
  "current_c_preserved": true,
  "ready_for_foundation_publication_v1r2": "YES"
}
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
