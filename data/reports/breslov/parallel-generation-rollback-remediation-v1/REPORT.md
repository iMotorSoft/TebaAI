# Rollback remediation — technical fix, invalid validation run

## Gate / branch / authoritative base

- Gate result: `TEBAAI_BRESLOV_PARALLEL_GENERATION_ROLLBACK_REMEDIATION_V1_INVALID`.
- Branch: `feature/console-backend-core`.
- Fetch completed. Local HEAD = tracking HEAD = ls-remote HEAD = `9882b569e55513dc179eccdc1c465bf31b25cb6a`.
- No merge, rebase, reset, clean, stash, staging, commit or push.
- Foundation V2 remains an unpublished local candidate.

## Original defect

`defect-reproduction.json` was generated before production edits, using the historical reproduction script read-only and the real original function with in-memory persistence. OLD→NEW CUTOVER was APPLIED; OLD became INACTIVE and NEW ACTIVE. ROLLBACK NEW→OLD raised GenerationPreconditionError (`Only a CANDIDATE generation can be activated; got INACTIVE`), with zero rollback writes.

Root cause: `activate_generation` compared every target against `SWITCHABLE_STATUS = CANDIDATE`, regardless of operation. There was no rollback eligibility policy. The offline direct matrix was also executed before the fix (`offline-before-fix.txt`).

## Minimal remediation

Changed only `SrvRestAstroLS_v1/backend/modules/library/generation.py` and added `SrvRestAstroLS_v1/backend/tests/test_generation_rollback_remediation.py`, plus this evidence directory. `remediation.patch` compares production code against captured original bytes; the original untracked Foundation file is also preserved as `generation-before.py` for review.

One CAS primitive remains. CUTOVER stays CANDIDATE-only. ROLLBACK requires INACTIVE, existing retention_hold, immediate predecessor recorded in the active pointer, successful APPLIED activation-to-target audit and APPLIED target→current switch edge, same logical document and source, and expected-active CAS. Departing ACTIVE gets retention_hold=true in the same transaction. A target row lock protects eligibility checks against concurrent hold changes. Unknown/non-switch operation names fail closed. BACKFILL remains the migration's responsibility, not a new runtime promotion path.

No schema changes. No reader, viewer, citation, region-publication, worker, search or extraction changes. Existing CANDIDATE structural admission is preserved, not redesigned. Existing CUTOVER no-op retry behavior is preserved; ROLLBACK rejects stale CAS even if target is already active. Successful idempotent no-ops add no audit rows. See `state-transition-contract.md` and `rollback-eligibility-contract.md`.

## Evidence and controls

- OLD ACTIVE / NEW CANDIDATE → CUTOVER → OLD INACTIVE (retained) / NEW ACTIVE.
- ROLLBACK → OLD ACTIVE / NEW INACTIVE (retained). No reingestion or re-embedding.
- Arbitrary INACTIVE, never-activated retained INACTIVE, missing history, missing switch edge, rejected-only history, released retention, historical non-immediate ACTIVE, wrong source, BUILDING, FAILED, cross-document targets and stale expectations rejected.
- Explicit G0/G1/G2-equivalent history tests reject retained historical OLD when G0 is the immediate predecessor of B.
- CUTOVER/ROLLBACK audits contain distinct operation, from/to/expected IDs, APPLIED result and non-null persisted timestamp.
- Existing ManifestCleanupService rejects retained OLD after cutover and NEW after rollback before any vector access. Cleanup implementation unchanged.
- Offline validation preceded independent PostgreSQL validation. The latter uses unique random collection/logical/document IDs and one force_rollback transaction. No fixture persists. No Milvus service access is needed by this remediation.

## Validation chronology and INVALID reason

1. Captured full worktree inventory/hashes and authoritative Git state.
2. Reproduced original defect offline; ran pre-fix full backend baseline and direct offline matrix.
3. Implemented the policy; initial offline focused run passed.
4. Added independent real-SQL coverage because existing Foundation fixture cannot initialize: its jsonb_build_object marker parameter causes IndeterminateDatatype. That preexisting fixture was not repaired and is byte-identical to its initial state.
5. First independent PostgreSQL run: 38 PASS / 1 FAIL. Fixture collection INSERT reused a named parameter for UUID and text, causing AmbiguousParameter before lifecycle execution (`focused-attempt-1.txt/xml`).
6. Split that binding into two distinct parameters, with no changes to lifecycle expectations. Subsequent focused run: **39 PASS** (22 new direct lifecycle tests including PostgreSQL, plus cleanup and safety-prerequisite regressions).
7. Full backend after correction: **1981 PASS / 20 FAIL / 13 ERROR**. Before fix: **1959 PASS / 20 FAIL / 13 ERROR**. Exact failing and error node sets match; **0 new remediation failure/error nodes**. All node IDs are in `backend-results.json`. Historical exact-node equivalence with older claimed '20 failures' is not asserted.

The user's rule explicitly classifies changing the harness after an observed failure/success as methodological contamination. The independent fixture binding was corrected after the failed attempt. Therefore **INVALID**, not PASS, despite passing technical tests. Failed evidence was retained; no observed failure was rewritten as a success. This gate does not claim full Foundation validation: 13 preexisting Foundation setup errors remain.

## Integrity / stores

- `git diff --check`: PASS.
- Pattern secret scan of candidate code/tests/new evidence: PASS; limitations recorded in `secret-scan.json`.
- `worktree-preservation.json`: zero unrelated preexisting file changes; existing Foundation test and historical publication FAIL preserved byte-for-byte.
- CURRENT C document `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`, logical `db200a31-b547-5668-d968-06d0ec36ad95`: **0 writes by gate**; no pointer/status/chunk/vector mutation, extraction, embedding, rebuilding or reingestion. Mutation scope is enforced by unique synthetic IDs in direct tests. This is not a claim backed by a database-wide write-counter snapshot; existing full-suite C assertions are read-only.
- PostgreSQL/Milvus/LiteLLM not started, stopped, reconfigured or migrated. Only isolated PostgreSQL synthetic fixture writes were made by remediation tests, then rolled back. Full-suite external-test failures are reported as observed, without a service-quality claim or silent fallback claim.

## Risks / next step

The local policy bytes are technically tested but this run cannot authorize progression. Re-run this remediation gate from a clean evidence freeze with the corrected harness, retaining this INVALID history. Investigate/fix existing Foundation fixture infrastructure under an explicitly authorized separate validation plan; do not hide its 13 errors. Only after valid remediation closure should Foundation publication gate restart FROM THE BEGINNING over corrected bytes. Do not resume the previous failed publication run. No C Safety V2 or C reingestion is authorized.
