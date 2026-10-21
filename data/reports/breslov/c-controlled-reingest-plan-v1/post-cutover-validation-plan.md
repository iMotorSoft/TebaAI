# Post-cutover validation — future execution gate

Immediately after the atomic switch, use normal authenticated viewer requests, not privileged inspector results. Record visibility epoch, request config, query IDs, returned document/chunk/vector/evidence IDs and source/page lineage.

1. Active cardinality for logical C = 1, document = sealed NEW; OLD and other historic generation IDs never appear as normal results. Repeat on lexical, phrase, fuzzy, vector, hybrid, simple/advanced research and relation paths, including conversation follow-ups and direct page/citation hydration.
2. Sealed A known-good and C partial-page queries all PASS with NEW accepted evidence, correct physical page and textual citations. No good-neighbor loss. Compare baseline semantics, not OLD chunk IDs/counts.
3. Sealed B known-bad queries expose no rejected-region text/evidence/citations, no embedding/vector lineage from those spans. Exhaustive storage/region checks complement query tests; no infra fallback masquerading as no evidence.
4. All 284 physical pages represented; source original hash unchanged and durable viewer authorized/readable. Accepted and quarantined bbox references open correct original page; quarantined has visual source but no textual citation. Playwright+Chromium reproducible source/citation regression with environment-provided credentials; exploratory HTTP/browser status is insufficient.
5. Exact NEW chunk/embedding/vector PK+metadata reconciliation, duplicate active chunks/vectors/citations = 0; no OLD vector leaks or candidate remnants from other attempts. Recheck source, dimensions/model alias and visibility after caches expire/reconnect, with concurrent requests and in-flight epoch handling.
6. Check OLD retained data fingerprints and source, non-C A/B fingerprints, absence of unintended jobs/cleanup, error/heartbeat/leakage/coverage counters.

Any critical failure in C_ROLLBACK_RUNBOOK.md => ROLLBACK REQUIRED immediately; missing infrastructure/results => validation incomplete, no stabilization closure/cleanup. After rollback run the same identity/isolation/source checks targeting OLD and its sealed baseline. OLD may retain legacy text defects: rollback restores previous authority, not claims regional correctness for OLD.

Stabilization has no invented duration. Owner must approve window, observation frequency and acceptance; OLD retention hold remains until signed post-cutover review, rollback window closure and a separate cleanup gate. No time-based physical deletion by default. This gate executes none of these requests or switches.
