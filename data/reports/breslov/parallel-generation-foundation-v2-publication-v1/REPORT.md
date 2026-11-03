# Foundation V2 — Publication V1

## Result

`TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1_FAIL`

Reason: `ROLLBACK_REJECTS_PREVIOUSLY_ACTIVE_GENERATION`.

COMMIT = NO; PUSH = NO. No Foundation code, tests, migration or historical evidence was changed. No Safety V2, C reingestion, extraction, embedding, vector rebuilding, service access or migration execution occurred.

## Base and inventory

Branch: `feature/console-backend-core`.
Fetch succeeded; LOCAL_HEAD = TRACKING_HEAD = LS_REMOTE_HEAD = `9882b569e55513dc179eccdc1c465bf31b25cb6a`.
Index was empty and remains untouched.

Initial inventory (excluding only this newly created publication report directory):
- 15 provisional Foundation paths: 10 production/migration, 3 test, 2 historical report files.
- 886 preexisting unrelated paths excluded (individual files, not collapsed directories).
- 0 ambiguous *path classifications*. This does NOT certify complete dependency closure or hunk-level provenance.
- Allowlist is provisional, not approved for staging. Cleanup/gateway contain earlier changes whose hunk provenance would need reconciliation before publication.

Generation implementation and migration 043 are UNTRACKED; reader changes are MODIFIED. Foundation test is UNTRACKED; two supporting tests are MODIFIED. Prior Foundation report files are UNTRACKED.

## Confirmed technical defect

Unchanged `backend/modules/library/generation.py`:
- line 55: `SWITCHABLE_STATUS = GENERATION_CANDIDATE`;
- lines 539–543: rejects every target not in that status, with no exception for ROLLBACK;
- lines 556–563: cutover changes the old ACTIVE generation to INACTIVE.

Therefore the documented inverse activation NEW→OLD cannot work directly after OLD→NEW. The existing `test_atomic_cutover_and_rollback` also calls that direct inverse without changing OLD back to CANDIDATE.

`reproduce_rollback.py` invokes the real implementation, replacing only its SQL persistence helpers with a deterministic in-memory adapter. Result in `rollback-results.json`:

1. OLD ACTIVE / NEW CANDIDATE.
2. CAS OLD→NEW: APPLIED.
3. OLD INACTIVE / NEW ACTIVE.
4. ROLLBACK NEW→OLD: `GenerationPreconditionError: Only a CANDIDATE generation can be activated; got INACTIVE`.
5. Rollback writes: 0; pointer remains NEW.

This is an offline control-flow reproduction, not a live database/CAS/reader certification. No repair was attempted. The publication gate stops on this defect as required.

## Prior PASS provenance

Only `REPORT.md` and `gate.json` actually exist in the historical Foundation V2 directory. The report enumerates many files that are absent, including raw full-backend output, failure node IDs, current-C before/after snapshots and final-validation.json. No historical hashes exist for comparison.

Historical `gate.json` is not valid JSON (`True` / `False` literals) and claims `PRODUCTION_CODE_CHANGED: False`, despite describing structural implementation. Neither historical file was rewritten.

The claimed 1959 PASS / same 20 baseline failures is historical, not independently verified, and cannot be tied to current bytes. No assertion that this is the same tree that produced that PASS is justified.

## Validation actually executed

- Remote/base precheck: PASS.
- Offline real-function cutover: APPLIED; rollback contract: FAIL (reproducer exit 1).
- `cd SrvRestAstroLS_v1/backend && uv run pytest tests/test_content_manager_cleanup.py -q`: **7 passed**, 1.09s. These use fake persistence/index adapters; not proof of complete retention protection.
- `git diff --check`: PASS, exit 0.
- Snapshot hashes and preexisting-file preservation checked in final-validation.json.

Full backend, live migration/reader/viewer/CAS/retention suites, quarantine regression, secret scan and fresh authoritative checkout were NOT executed after the blocking technical defect. Do not interpret missing results as PASS or a baseline-equivalence claim. The exact 20 known failing node IDs are unavailable in prior evidence.

## Current C

Document `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`; logical document `db200a31-b547-5668-d968-06d0ec36ad95`.
Historical claim: 942 chunks, 942 vectors, durable source repaired and source SHA256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.

Live before/after counts, content digest, source endpoint, retrieval and viewer were NOT verified in this gate. No services were accessed by this gate, no synthetic DB/vector data was created, and C was not touched. No live-state claim is inferred from historical evidence.

## Readiness

FOUNDATION_V2_PUBLISHED = NO
READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2 = NO
READY_FOR_C_REINGEST_EXECUTION = NO
C_REINGEST_EXECUTED = NO

Next step: separate, explicitly authorized defect remediation, followed by publication revalidation from a new frozen candidate. Do not silently fix and resume this attempt.
