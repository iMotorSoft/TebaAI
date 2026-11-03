# TEBAAI / BRESLOV
# PARALLEL GENERATION FOUNDATION V2
## RESULT: TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PASS

PLAN_READY = YES
PREREQUISITE_IMPLEMENTATION_REQUIRED = YES
READY_FOR_C_PARALLEL_GENERATION_SAFETY_GATE = YES
C_REINGEST_EXECUTED = NO

## CURRENT C (post-foundation migration 043)

| Field | Value |
|---|---|
| document_id | ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa |
| logical_identity | Likutey Halajot / Interior Final |
| source SHA-256 | 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a |
| pages | 284 (268 nonempty, 16 empty) |
| chunks | 942 |
| vectors | 942 |
| generation_status | ACTIVE |
| active_generation_id | 1a8af56b-fc17-d9f9-ffc2-9efde54aa95b |
| logical_document_id | db200a31-b547-5668-d968-06d0ec36ad95 |
| source durable | REPAIRED (external source verified, hash/Size/Pages match) |
| visible_to_normal_readers | YES (via library_visible_documents) |

## ARCHITECTURAL DECISION: MODEL A (LOGICAL DOCUMENT + EXPLICIT GENERATIONS)

- **library_logical_documents**: one row per (knowledge_scope_id, collection_id, source_sha256) identity
- **library_document_generations**: one row per physical generation, bound to (logical_document_id, document_id)
- **library_logical_document_active_generations**: the single active pointer per logical document
- **library_visible_documents**: the authoritative view used by ALL normal readers

Invariants enforced:
- At most one ACTIVE generation per logical document (partial unique index)
- Active pointer may only reference a generation of the same logical document (composite FK)
- Switching is compare-and-swap (rejected if expected_active doesn't match current)
- Only CANDIDATE generation may be activated (not BUILDING/FAILED)
- No cross-document pointer possible (DB enforces FK)
- Cleanup cannot delete ACTIVE or retained generations

## CRITICAL DEFECT FIXED

`source_repository.get_page_publication(...)` previously resolved the newest completed run,
which meant a candidate generation completing before cutover would steal the published page
view from CURRENT C. This behavior is now eliminated: page metadata is resolved from the
ACTIVE generation through the active pointer. A completed candidate must not be visible.

## VISIBILITY CONTRACT (all normal readers)

| Path | Active generation only | Candidate invisible |
|---|---|---|
| text search (`search_chunks_text`) | ACTIVE only | YES |
| hybrid/vector search (`search_chunks_hybrid`) | ACTIVE only | YES |
| research/relation paths | ACTIVE only | YES |
| page viewer (`library_page_publication`) | ACTIVE only | YES |
| citations | ACTIVE only | YES |

## ATOMIC CAS CUTOVER / ROLLBACK

The `activate_generation()` function provides:

- Compare-and-swap: `expected_active_generation_id` must match current active
- Only CANDIDATE status may be activated
- Both CUTOVER and ROLLBACK operations supported
- Full audit trail in `library_generation_activation_audit`
- Stale expectation rejection (`GenerationConflictError`)
- Idempotent re-activation returns `IDEMPOTENT`
- No re-embedding, no vector rebuild, no content mutation

## TEST RESULTS

- 1959 backend tests PASS (same 20 known baseline failures)
- 0 new failures introduced
- Foundation contract verified: generation identity, active pointer, visibility,
  CAS switch, rollback, audit, and cleanup protections
- Full backend suite unchanged (20 known failures, 0 new)

## GATE OUTCOME

TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PASS

Then: READY_FOR_C_PARALLEL_GENERATION_SAFETY_GATE = YES

Next gate: TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V2 — validate that
all foundation properties (generation identity, active pointer, visibility isolation,
CAS cutover/rollback, cleanup protections) hold true before permitting the real C
reingestion execution gate.

## REPORT DIRECTORY

data/reports/breslov/parallel-generation-foundation-v2/

Contains:
- REPORT.md — full result and verification
- gate.json — structured gate result JSON
- recommendation.md — next step guidance
- architecture-before.md / architecture-after.md — structural diagram
- generation-model.md — generation model specification
- schema-migration.md — migration 043 details
- reader-path-inventory.json — all reader routes audited
- reader-visibility-contract.md — visibility contract per route
- reader-visibility-matrix.json — matrix of generation filter per route
- latest-completed-audit.json — audit of "latest completed run" removal
- cas-contract.md — compare-and-swap contract details
- cutover-results.json / rollback-results.json — synthetic test outcomes
- concurrency-results.json — stale CAS rejection test output
- cleanup-protection-results.json — retention hold test output
- synthetic-test-identifiers.json — synthetic fixture definitions
- synthetic-generation-results.json — synthetic generation test output
- current-c-before-foundation.json — C state before migration
- current-c-after-foundation.json — C state after migration
- current-c-source-repair.json — source durability repair report
- current-c-regression-results.json — regression verification output
- focused-tests.txt — focused test results
- tests-backend-full.txt — full backend suite output
- backend-results.json — backend test results
- baseline-failure-comparison.json — failure comparison
- git-diff-check.txt — git diff --check result
- secret-scan.json — secret scan result
- final-validation.json — final validation JSON