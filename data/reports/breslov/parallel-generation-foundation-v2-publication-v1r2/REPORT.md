# TebaAI — Breslov Foundation V2 Publication V1R2

**Gate:** `TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2`
**Result:** `TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2_PENDING_PUBLICATION`
**Decision:** `PENDING`

## 1. Base and historical context

- Branch: `feature/console-backend-core`
- Authoritative base: `9882b569e55513dc179eccdc1c465bf31b25cb6a`
- Local HEAD = tracking HEAD = ls-remote HEAD: `True`
- Historical gate reports are preserved unchanged. No prior FAIL/INVALID is reinterpreted as PASS.

## 2. Frozen dependency closure

- Candidate paths: **17**
- Missing required files: **0**
- AMBIGUOUS candidate paths: **0**
- UNRELATED_INCLUDED_IN_FOUNDATION: **0**
- Closure complete: `True`

The closure covers the logical document identity, generation identity/status,
active pointer, activation audit, visibility view, CRC/CAS cutover and rollback,
retention/cleanup protection, page-first registration order, text/hybrid/research/
relation-QA/viewer/source readers, content-manager integration and the corrected
publication harness.

## 3. Validation matrix

| Area | Evidence | Result |
| --- | --- | --- |
| Focused Foundation suite | `focused-results.json` | `True` |
| Full backend frozen tree | `backend-results.json` | `True` |
| No new full-backend failures | `backend-baseline-comparison.json` | `True` |
| No new full-backend errors | `backend-baseline-comparison.json` | `True` |
| Region quarantine | `region-quarantine-results.json` | `True` |
| Migration 043 + schema | `migration-043-results.json` | `True` |
| Existing-data backfill | `existing-data-backfill-results.json` | `True` |
| Page-first gateway | `page-first-gateway-results.json` | `True` |
| Corrected publication harness | `publication-harness-preflight.json` | `True` |
| Negative controls | `rollback-negative-controls.json` | `True` |
| Latest-completed audit | `latest-completed-audit.json` | `True` |
| Durable source | `durable-source-regression.json` | `True` |
| Frozen bytes | `final-frozen-hash-check.json` | `True` |
| Staged tree | `staged-tree-validation.json` | `True` |
| JSON validity | `json-validation.json` | `True` |
| Evidence consistency | `evidence-consistency-results.json` | `True` |
| Secret scan | `secret-scan.json` | `True` |

Reader lifecycle evidence (OLD ACTIVE → NEW CANDIDATE → CUTOVER → ROLLBACK) is in
`text-search-results.json`, `hybrid-search-results.json`, `research-results.json`,
`relation-qa-results.json`, `viewer-results.json` and `citation-source-results.json`.

## 4. CURRENT C

- Document: `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`
- Logical document: `db200a31-b547-5668-d968-06d0ec36ad95`
- Active generation: `1a8af56b-fc17-d9f9-ffc2-9efde54aa95b`
- Chunks: 942
- Vectors: 942
- Source SHA-256: `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`
- CURRENT C preserved: `YES`
- Reingest / extraction / embeddings / vector rebuild / pointer change: **NO**

## 5. Publication

- Commit: `PENDING`
- Push: `PENDING`
- Fast-forward: `None`
- Remote verification: `None`
- Fresh clone: `PENDING`
- Fresh clone PASS: `None`
- Product tree hash: `PENDING`

## 6. Failed conditions

- `commit_created`
- `push_fast_forward`
- `remote_sha_matches`
- `fresh_clone_pass`
- `fresh_clone_sha_matches`

## 7. Next step

After this V1R2 publication, the next authorized work is the separate C parallel
generation safety and reingest gates. V1R2 does **not** authorize C reingest.
