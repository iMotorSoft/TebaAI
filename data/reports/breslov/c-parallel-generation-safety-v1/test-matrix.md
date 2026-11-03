# Test matrix and honest limits

The required end-to-end generation matrix is **not satisfied**. Do not interpret the green local regression suite as generation-safety PASS.

| Required case | Result | Reason/evidence |
|---|---|---|
| A OLD only | NOT DEMONSTRATED as retrieval test | Read-only inventory proves sole current C ready document/run, 942/942; not active-pointer/query isolation |
| B Parallel candidate | BLOCKED | Live unique scope/collection/source index disallows planned parallel document; no NEW created |
| C NEW→normal no leak | NOT DEMONSTRATED | New regression only rejects unrehydratable/misattributed synthetic hits, not a valid inactive candidate row |
| D OLD→candidate no reverse leak | NOT DEMONSTRATED | No explicit restricted candidate-generation retrieval |
| E Atomic cutover | NOT IMPLEMENTED | No pointer/audit/epoch/CAS pair or real PG concurrency proof |
| F Rollback without reingest | NOT IMPLEMENTED | No switch primitive/hold/source-viewer support for retained OLD |
| G Interrupted NEW invisible | NOT DEMONSTRATED | Existing normal literal readers lack generation predicate |
| H Failed validation rejects activation | PARTIAL EXISTING ONLY | Pipeline rejects inconsistent reconciliation; not a generation activation seal |
| I Stale cutover rejected | NOT IMPLEMENTED | Candidate status CAS is not expected-OLD active CAS |
| J Candidate cleanup OLD unchanged | NOT DEMONSTRATED | Existing exact manifest cleanup passes; no ownership/racing-publication/retention proof |
| K Retry no duplicate logical candidate | PARTIAL | New UUID collision aborts before claiming resources; not same-source admission/resume/idempotent replay |
| L Missing active metadata fails closed | NOT IMPLEMENTED globally | New hybrid missing-PG hydration fail-closed covered; no active metadata exists to resolve |

## New deterministic regressions

`backend/tests/test_parallel_generation_safety_prerequisites.py`: 10 cases, all synthetic and offline.

- Missing/empty PG hydration and index/PG document mismatch: reject result (3).
- Canonical chunk index zero and identity retained (1).
- Cleanup ready/archived/missing/unknown status rejects before any cleanup/index side effect (4).
- Gateway conflicting document INSERT rejects before run/manifest ownership claim (1).
- Real `/library/search` Litestar handler + actual hybrid orchestration cannot serialize unrehydrated `NEW_ONLY_MARKER` (1).

First nine cases reproduced failures on pre-patch production code (`regressions-before.txt`); these are newly reproduced safety bugs, not unrelated historical test failures. HTTP case was added after the fix and is not claimed red-tested.

`test_inventory_guard.py`: 4 static tests enforce local DEV/read-only probes, exact Milvus method allowlist, PG SELECT-only wrappers and immutable evidence labels. They do not supply a global writer fence or replace server read-only mode.

## Executed validation

- Before patch: 55 existing focused tests PASS (`tests-before.txt`).
- Initial regressions on original code: 9 FAIL (intentional reproduction).
- After patch: selected relevant offline suite including HTTP orchestration, Content Manager, source authorization, simple RAG and Relation QA; final count in `test-results.txt`.
- No full repository suite: it includes service-dependent/mutating tests and no isolated test database/collection was provisioned in this gate. No such test was allowed to fall through to live C.
- No authenticated browser/Playwright generation proof, no real embedding/generative calls, no cutover/rollback concurrency/fault injection, no 284-page extraction/reconciliation.

Normal assistant, viewer, semantic/literal cross-route generation isolation remains untested/unimplemented; existing regression suites validate their prior behavior only. NEW_ONLY/OLD_ONLY fixture strings do not certify actual candidate isolation without the generation filter.

Commands were run from `SrvRestAstroLS_v1/backend` with `uv run --no-sync pytest ... -q`. Exact selected suite invocation is in `validation-commands.txt`. Source PDF was only hashed/read for cheap page count; never extracted/reingested.
