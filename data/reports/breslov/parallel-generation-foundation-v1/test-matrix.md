# Foundation acceptance matrix — NOT satisfied

All A–Q acceptance cases remain pending except preservation of existing duplicate guards and narrow hydration/status protections. No synthetic parallel logical/generation fixture traversing the production system exists in this attempt.

| Case | Result |
|---|---|
| A Same-source authorized generation / accidental duplicate | Authorized path NOT IMPLEMENTED; existing migration duplicate guard test 1 PASS |
| B Logical X / two same-SHA generations | NOT IMPLEMENTED / not admitted |
| C Explicit active OLD pointer | NOT IMPLEMENTED |
| D Normal returns OLD only | NOT DEMONSTRATED; current hybrid valid-candidate leak reproduced |
| E Explicit candidate returns NEW only | NOT IMPLEMENTED |
| F Atomic OLD->NEW | NOT IMPLEMENTED |
| G Rollback NEW->OLD | NOT IMPLEMENTED |
| H Stale switch rejected | NOT IMPLEMENTED |
| I FAILED activation rejected | No generation activation primitive |
| J Partial BUILDING invisible | NOT DEMONSTRATED across routes |
| K Exact NEW cleanup / OLD unchanged | Existing manifest bounds only; lifecycle/ownership race unresolved |
| L ACTIVE cleanup rejected | Prior ready/archived guard passes offline; no pointer-aware concurrency fence |
| M Idempotent admission | NOT IMPLEMENTED; collision rejection is not replay |
| N Concurrent cutover | NOT RUN / no primitive |
| O Missing active pointer fails closed | NOT IMPLEMENTED; current readers do not resolve one |
| P NEW cannot compete in OLD vector ranking | NOT DEMONSTRATED; scope-only top-1 competition reproduced |
| Q Orphan PG hydration discarded | Prior prerequisite regressions PASS; retain defense |

## Actual denominators

- New blocker reproductions: **6 PASS**. One valid-PG candidate leak/top-1 filter reproduction, three literal SQL branch reproductions, one latest-run viewer reproduction, one safe collector-output redirection test. Green means the blocker still exists, not safety PASS.
- Selected suite total: **266 PASS / 4 warnings**, including those six and 260 existing selected tests. No test failure in this invocation.
- Existing migration 042 on synthetic temporary table: **1 PASS** separately.
- Total selected invocations: **267 passed**, not full backend suite.
- New foundation acceptance tests: **0 executed**. New migration/backfill tests: **0**. Actual PG concurrency: **0**. Actual Milvus generation-isolation tests: **0**. Complete cross-route OLD/NEW/missing-pointer acceptance: **0**. Browser E2E: **0**.
- C before/after inventories succeeded; run/content/source/vector fingerprints match. They are integrity observations, not acceptance/cutover tests or a restorable backup.

No FAILURES/PREEXISTING_FAILURES observed in selected executions. Four Litestar parameter deprecation warnings persist. No full suite claim, no silent skip/fallback counted as capability proof. [Raw result](test-results.txt), [migration result](migration-tests.txt), [concurrency plan](concurrency-tests.md).
