# TEBAAI / BRESLOV — Rollback Remediation V2

**TEBAAI_BRESLOV_PARALLEL_GENERATION_ROLLBACK_REMEDIATION_V2_PASS**

## Scope / Git / preservation

Branch: `feature/console-backend-core`.
Fetch, local HEAD, origin tracking and ls-remote all match
`9882b569e55513dc179eccdc1c465bf31b25cb6a`.
Only this report directory was created. Existing `generation.py` remediation and
`test_generation_rollback_remediation.py` were not changed. Existing Foundation
and unrelated worktree bytes remain intact. No reader, worker, quarantine,
frontend, schema or service changes; no commit/push/publication.

Historical Publication V1 **FAIL** and Remediation V1 **INVALID** remain immutable:
all historical file SHA-256 values match their initial capture.

Known antecedent: unconditional CANDIDATE target requirement previously permitted
cutover but prevented retained INACTIVE rollback. Existing local fix separates
CUTOVER and ROLLBACK admission and validates retention, prior successful activation,
immediate predecessor pointer/history, logical/source identity and CAS.

## METHODOLOGY

| Item | Result |
|---|---|
| Preflight performed before freeze | YES |
| UUID/text binding validated before freeze | YES |
| Preflight fixture reused for certification | NO |
| Certification fixture fresh | YES; CERT-V2 prefix and disjoint UUID sets |
| Freeze timestamp UTC | 2026-10-22T20:35:03.621999+00:00 |
| Frozen inputs | 494 files; SHA-256 |
| Post-freeze code modifications | 0 |
| Post-freeze harness modifications | 0 |
| Post-freeze fixture modifications | 0 |
| Post-freeze expectation modifications | 0 |

Phase A includes schema/UUID/FK/unique-ACTIVE-index checks, committed synthetic
positive and negative lifecycle operations, cleanup and one full backend baseline.
None counts toward PASS. First harness attempt exposed an untyped text probe;
explicit ::text then ::uuid resolved it BEFORE freeze. Next attempt exposed a
harness assertion expecting the retained-INACTIVE message for ACTIVE cleanup;
the dedicated ACTIVE guard/message was asserted BEFORE freeze. Final preflight
passed with unique-ACTIVE schema assertion and actual rollback call profiling.
No production-code repair was necessary.

Initial capture launcher used unavailable `python`; immediately rerun with
`python3`. The existing 22-test non-certifying preflight completed between that
failed launcher and successful capture. No source/harness candidate bytes were
modified during that interval. `worktree-before.json` preserves actual capture
state, including that output; its generic note predates this timing clarification.

Phase B used fresh UUID4 identifiers from unchanged frozen construction rules.
No certification rerun, byte/configuration change or silent fallback occurred.
Preflight cleanup and certification cleanup verified zero synthetic logical
records, generations and documents; audit deliberately remains by schema design.
Identifiers are in the respective fixture JSON files.

## POSITIVE FLOW

| Step | OLD | NEW | Result |
|---|---|---|---|
| Initial | ACTIVE; pointer OLD | CANDIDATE | verified |
| CUTOVER expected OLD, target NEW | INACTIVE + retained | ACTIVE; pointer NEW | APPLIED |
| ROLLBACK expected NEW, target OLD | ACTIVE; pointer OLD | INACTIVE + retained | APPLIED |

Reingestion, extraction, embeddings and vector rebuild calls during rollback: 0.
A Python call profiler around the real activation primitive observed only
`modules.library.generation` library calls; repository SQL performs the switch.
No pipeline or Milvus API is invoked by the harness.

## ACTIVATION POLICY

| Operation / target | Observed |
|---|---|
| CUTOVER CANDIDATE | ALLOWED |
| ROLLBACK retained immediate previous ACTIVE / INACTIVE | ALLOWED |
| arbitrary unretained INACTIVE | REJECTED |
| retained never-active INACTIVE | REJECTED |
| retained non-immediate historical ACTIVE | REJECTED |
| BUILDING, CUTOVER and ROLLBACK | REJECTED |
| FAILED, CUTOVER and ROLLBACK | REJECTED |
| cross-document generation, both operations | REJECTED |
| stale CUTOVER CAS | GenerationConflictError; pointer preserved |
| stale ROLLBACK CAS | GenerationConflictError; pointer preserved |
| ROLLBACK CANDIDATE / CUTOVER INACTIVE | REJECTED |

Non-immediate historical sequence is deterministic: OLD → G1 → G2;
G2 → OLD rejected, G2 → G1 rollback applied. All rejections assert unchanged
real generation, pointer and audit snapshots. Offline focused tests additionally
exercise no history, rejected history, missing edge, unretained and wrong source.

## AUDIT / RETENTION / ATOMICITY

CUTOVER audit = PASS; ROLLBACK audit = PASS; operations distinguishable = YES.
Exact successful edges, expected-active, operation and APPLIED result verified.
Retained OLD cleanup rejected = YES; ACTIVE cleanup rejected = YES.
Actual ManifestCleanupService guard is used with an isolated metadata loader
adapter and forbidden vector adapter. Real PostgreSQL protection queries also
verify protected rows. This tests admission, not destructive vector cleanup.

Idempotency = IDEMPOTENT, no duplicate state mutation or audit. ROLLBACK always
checks CAS; existing CUTOVER retry semantics preserved.
Independent READ COMMITTED observer verifies exactly one ACTIVE and matching
pointer before each commit and after every successful/rejected switch. The
partial unique ACTIVE index is independently verified. No inconsistent committed
state observed. This is bounded serial committed-state validation, not a new
high-contention stress certification.

## CURRENT C

- document_id: `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`
- logical_document_id: `db200a31-b547-5668-d968-06d0ec36ad95`
- PostgreSQL writes by gate to C: 0; Milvus writes by gate: 0.
- reingest: NO; extraction: NO; embedding generation: NO; vector rebuild: NO.
- active pointer modified: NO.

Read-only before/after snapshots of document/logical/generations/pointer/audit
match after the synthetic lifecycle and cleanup. All write parameters in the
lifecycle harness are newly generated synthetic IDs, never either Current C ID.

## BACKEND VALIDATION

| Run | PASS | FAIL | ERROR |
|---|---:|---:|---:|
| Pre-freeze full baseline (non-certifying) | 1981 | 20 | 13 |
| Final frozen full backend | 1981 | 20 | 13 |
| Frozen focused rollback tests | 22 | 0 | 0 |
| Frozen Foundation-related regression subset | 19 | 0 | 13 |

New full backend FAIL node IDs = 0; new ERROR node IDs = 0.
Foundation-related new FAIL / ERROR node IDs = 0 / 0.
All exact IDs are persisted in `pre-freeze-backend-baseline.json`,
`final-backend-results.json` and `backend-baseline-comparison.json`, with raw
stdout/stderr and JUnit XML for each run. No counts were hardcoded as criteria.

**The 20 FAIL and 13 ERROR are reproduced pre-existing baseline, not Foundation
PASS.** Fails: 16 investigative-QA, 2 named-topic and 2 V5 evaluator tests.
All 13 errors are existing Foundation fixture setup errors:
`library_pages_v2` JSON construction parameter $6 has IndeterminateDatatype.
No publication claim is made for those blocked scenarios. The certification
fixture independently exercises actual PostgreSQL generation lifecycle without
pages/chunks/vectors, which the switch primitive does not reconstruct or require.

## INTEGRITY

Frozen production hashes unchanged = YES.
Frozen harness / fixture / contract hashes unchanged = YES.
Unrelated pre-existing bytes preserved = YES.
All report JSON explicitly parsed = YES.
git diff --check = PASS.
Secret scan = PASS (matched values never persisted).
Historical V1 INVALID preserved = YES.
Historical Publication V1 FAIL preserved = YES.

Evidence creation is allowed after freeze; no frozen code/fixtures/expectations
were modified. Documentation and machine-readable evidence are REPORT_ONLY.

## Readiness

ROLLBACK_FIX_CERTIFIED = YES
CUTOVER_SEMANTICS_PRESERVED = YES
ROLLBACK_RETAINED_INACTIVE_TO_ACTIVE = PASS
ARBITRARY_INACTIVE_ACTIVATION_ALLOWED = NO
NEVER_ACTIVE_INACTIVE_ACTIVATION_ALLOWED = NO
STALE_CAS_PROTECTION = PASS
CROSS_DOCUMENT_PROTECTION = PASS
CLEANUP_RETENTION_PROTECTION = PASS
POST_FREEZE_MUTATIONS = 0
CURRENT_C_PRESERVED = YES
FOUNDATION_V2_PUBLISHED = NO
READY_FOR_FOUNDATION_V2_PUBLICATION_REVALIDATION = YES
READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2 = NO
READY_FOR_C_REINGEST_EXECUTION = NO
C_REINGEST_EXECUTED = NO
COMMIT = NO
PUSH = NO

Next gate: rerun `TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1`
**FROM THE BEGINNING**, preserving its previous historical FAIL evidence.
