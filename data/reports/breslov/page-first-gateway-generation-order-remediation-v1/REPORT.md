# Page-first gateway generation order remediation V1

## Result

TEBAAI_BRESLOV_PAGE_FIRST_GATEWAY_GENERATION_ORDER_REMEDIATION_V1_PASS

Branch: `feature/console-backend-core`. Local/tracking/remote HEAD all equal `9882b569e55513dc179eccdc1c465bf31b25cb6a`. Foundation V2 remains local and unpublished. No commit/push. Historical reports and all other preexisting worktree bytes preserved (see `worktree-preservation.json`).

## ROOT CAUSE / FIX

- generation before run = YES (original `persist_document_and_pages` lines 250–262).
- generation before document/logical linkage = YES (original `_register_generation` lines 342–358).
- exact product: `SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py`.
- Fixed run INSERT at line 253 before registration at line 257; linkage UPDATE at line 345 before generation INSERT at line 350.
- Original offline reproduction failed with both `run` and `document_logical_link` missing at generation execution. `defect-reproduction.json` + `pre-fix-reproduction.txt` preserve the failure.
- Incremental fix against the **initial dirty worktree**, not HEAD: `gateway-remediation.patch`. Only two SQL-call reorders and explanatory comments. Existing Foundation additions and collision guard were not introduced by this remediation.
- run exists before generation = YES.
- document/logical link exists before generation = YES.
- raw FK bypass introduced = NO.
- generation lifecycle policy changed = NO.

`gateway-fk-order-contract.json` records live catalog constraints, not only migration text. Immediate run and composite document/logical FKs were checked. Actual permitted order is document → run → resolve logical → link → generation. Schema requires a partial order: physical document's logical FK is initially nullable, so resolving logical identity before inserting the physical document is not mandatory. No change was made merely to mimic a conceptual total order. Both required parent chains exist before generation.

## SYNTHETIC PRODUCT FLOW

- logical document created/resolved = PASS.
- document created/resolved = PASS.
- document ↔ logical linkage = PASS.
- run creation = PASS.
- generation creation = PASS.
- active pointer lifecycle = PASS.
- FK errors = 0; binding errors = 0.

Real product `persist_document_and_pages`, real SQL, real DEV PostgreSQL immediate constraints. Cursor observation executes real reads proving both parent relationships immediately before generation insertion. This is registration/page persistence, not an extraction or full embeddings/vector ingestion certification. Input uses a declared synthetic regional publication; no change to regional certification/quarantine. UUID target types come from live `information_schema.columns`; generation UUID is DB-generated. Gateway JSON values are serialized separately and explicitly cast `::jsonb` (no polymorphic JSONB fixture inference).

Initial generation = BUILDING, with no pointer. A different pipeline-version physical identity reuses the logical identity, has distinct document/run/generation and no uniqueness collision. Both generations remain invisible. This test uses the same synthetic job metadata to isolate physical-generation identity, not to certify worker scheduling or new-job orchestration. The unmodified gateway finalize is then exercised for the second generation: completed run, CANDIDATE generation, no pointer and no normal authority. The source-copy adapter is isolated to the temporary fixture directory; source durability is not certified here.

## RETRY / FAILURE

- duplicate logical documents = 0.
- duplicate generations for an identical retried request = 0.
- duplicate runs for an identical retried request = 0.
- invalid active pointers = 0.
- retry idempotency = PASS **under existing reject-on-ownership-collision policy**, not a new resume feature.
- failure before generation leaves impossible state = NO.
- generation INSERT failure leaves invalid pointer = NO.

The same failed attempt retries successfully after rollback. Repeating a successfully persisted identical request is safely rejected before ownership/resource writes, with counts unchanged. Changing the pipeline version intentionally creates a different physical-generation identity, not an identical retry.

Before-insert control raises after logical/document/link/run creation; at-insert control executes production INSERT with a deliberately NULL pipeline-version argument, provoking a real NOT NULL rejection (23502). This is an expected negative-control rejection, not an FK/binding error. No schema bypass or status rewrite. `transaction-contract.md` details savepoint rollback of the entire newly created parent chain. Outer fixture transactions unconditionally roll back successful data too. Independent post-rollback queries show synthetic docs/logicals/runs/generations/pointers = 0; scope absent. Audit rows do not remain.

## ROLLBACK REGRESSION

22 existing focused rollback tests pass, including real PostgreSQL rollback contract:

- CUTOVER CANDIDATE→ACTIVE = PASS.
- ROLLBACK retained immediate previous INACTIVE→ACTIVE = PASS.
- arbitrary INACTIVE = REJECTED.
- stale CAS = REJECTED.
- cleanup/retention protection = PASS.

Rollback Remediation V2 product/test bytes preserved. No policy/reader/activation changes.

## V1R1 JSONB FIXTURE ERRORS — SEPARATE

- GATEWAY_FK_DEFECT = this gate, fixed and synthetically verified.
- V1R1_13_FIXTURE_ERRORS = separate known issue.
- Known cause = IndeterminateDatatype in jsonb_build_object (parameter $6).
- Same as gateway FK defect = NO.
- Resolved by this gate = NOT_IN_SCOPE.
- Remaining Foundation ERROR nodes = 13, exact IDs in `separate-v1r1-jsonb-error-status.json`.

No claim of full Foundation validation. Historical FAIL/INVALID/PASS gates are not modified or reinterpreted.

## CURRENT C

- document_id = ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa.
- logical_document_id = db200a31-b547-5668-d968-06d0ec36ad95.
- PostgreSQL writes = 0; Milvus writes = 0.
- reingest/extraction/embeddings/vector rebuild = NO.
- active pointer/generation status modified = NO.

Before/after hashes of document, runs, logical identity, generations, active pointer and activation audit match for each final fixture and again after full backend. No Milvus client used by the new gateway tests. No service started/stopped/restarted/reconfigured/migrated.

## TESTS / FREEZE

- Pre-freeze focused = 56 PASS / 0 FAIL / 0 ERROR.
- Fresh final fixtures = PASS (negative-before, negative-at, wholly fresh positive).
- Post-freeze focused gateway/lifecycle/rollback/cleanup suite = 56 PASS / 0 FAIL / 0 ERROR.
- Foundation regression = 41 PASS / 0 FAIL / 13 known ERROR.
- Full backend = 1985 PASS / 20 FAIL / 13 ERROR.
- Historical baseline = 1981 PASS / 20 FAIL / 13 ERROR.
- New FAIL node IDs = []; new ERROR node IDs = []. Exact comparisons in `backend-baseline-comparison.json`.
- Four new direct tests account for four additional PASS.
- Frozen manifest covers 478 backend Python/SQL, test fixture and certification contract/harness files. Hashes unchanged.
- All JSON strict-valid, git diff --check PASS, scoped secret scan PASS (see final validation artifacts).

Only gateway product bytes changed from the initial inventory; two new direct test files and this report directory were added. No `lat.md` or `@lat` change (lat check not applicable).

## Decision / next gate

GATEWAY_FIX_CERTIFIED = YES
RUN_BEFORE_GENERATION = YES
DOCUMENT_LOGICAL_LINK_BEFORE_GENERATION = YES
ROLLBACK_REMEDIATION_PRESERVED = YES
CURRENT_C_PRESERVED = YES
V1R1_13_JSONB_FIXTURE_ERRORS_RESOLVED = NOT_IN_SCOPE
READY_FOR_PUBLICATION_PREFLIGHT_REMEDIATION_V2 = YES
FOUNDATION_V2_PUBLISHED = NO
READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2 = NO
READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2 = NO
READY_FOR_C_REINGEST_EXECUTION = NO
C_REINGEST_EXECUTED = NO
COMMIT = NO
PUSH = NO

Next: independently authorized Foundation V2 publication preflight remediation V2. Its harness must address the separate JSONB fixture issue and revalidate the whole unpublished Foundation dependency closure. No Publication V1R2, Safety V2 or C execution is authorized by this result.
