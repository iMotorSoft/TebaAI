# Parallel generation rollback remediation V1

Result: **INVALID (methodology)**, not a publication authorization.

Production candidate fix and direct lifecycle tests are local/unpublished. Technical focused results: 39 PASS; full backend: 1981 PASS / 20 FAIL / 13 ERROR, identical failing/error nodes to the pre-fix current-worktree baseline. See [REPORT.md](REPORT.md), [gate.json](gate.json), [backend-results.json](backend-results.json), and [final-validation.json](final-validation.json).

The independent PostgreSQL fixture was corrected after an observed binding error. The failed attempt remains `focused-attempt-1.txt/xml`; this triggers the user's strict INVALID rule despite subsequent technical success. No expectation was relaxed. Do not use this run to authorize Foundation publication revalidation, C Safety V2 or C reingestion.

No commit/push, no changes to C, no reader/schema/worker/quarantine changes, no edits to the historical Foundation publication FAIL. Preexisting unrelated changes are hash-preserved.
