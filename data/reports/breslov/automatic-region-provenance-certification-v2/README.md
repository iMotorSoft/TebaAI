# Automatic region provenance certification V2 — FAIL

```text
TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V2_FAIL
READY_FOR_C_REINGEST = NO
CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO
```

**Safety improved; required-class utility remains incomplete.** No worker/default extractor integration. All V1 files and preexisting worktree content preserved.

## Results

| Question | Answer |
|---|---|
| Did V2 eliminate all 5 V1 unsafe certifications? | YES, exact source-IR tests and live evaluation |
| New holdout pages / regions | 18 / 240 |
| Unsafe false CERTIFIED + ACCEPTED | 0 |
| Incorrect provenance CERTIFIED, regardless of quality | 0 |
| Safe good source units left unresolved/unseparated | 103 of 111 annotated good units |
| Useful supported certifications? | YES: 8 provenance-certified notes, 7 ACCEPTED; notes/columns work |
| Required supported classes all work? | NO: body unsupported → utility FAIL |
| Page 167 body / quality | UNRESOLVED / UNRESOLVED |
| Page 167 notes | 60–66 discovered; 61–64 CERTIFIED + ACCEPTED; 60/65/66 UNRESOLVED |
| Page 167 column/order correctness | PASS against original source goldens |
| Page 167 RTL | UNRESOLVED (zone/direction unproven) |
| Page 167 aggregate candidate | PARTIAL |
| Page 55 bad heading | UNRESOLVED; no quality attribution without zone proof |
| Page 55 previous / next neighbor | UNRESOLVED / CERTIFIED + ACCEPTED (33) |
| Page 55 neighbor sequence / symmetric contract | PASS / YES |
| Page 56 note 35 | CERTIFIED provenance, quality UNRESOLVED |
| Page 56 note 36 continuation | UNRESOLVED; local boundary KNOWN; no automatic link to 57 |
| Note 66 continuation | UNRESOLVED; local boundary KNOWN; no automatic link to 168 |
| Cross-page editorial units represented safely? | YES as unresolved segments, NOT automatically linked/certified units |
| False completion of 36 on 56 / 66 on 167 | NO / NO |
| Ambiguous layout fails closed? | YES on evaluated regressions/holdout |
| Missing direction evidence fails closed? | YES |
| Holdout sealed before evaluation? | YES; definition, source inventory, evaluator, tests and rule dependencies hashed |
| Rules modified after holdout? | NO |
| New backend regressions | 0 |
| OCR / orthographic search used? | NO / NO |
| Worker enforcement integrated? | NO |
| C reingested? | NO |
| Certificates safe enough for worker integration? | NO: required gate FAIL |

## Why FAIL, not BLOCKED

The five V1 false zones share one root cause: converter class labels were treated as editorial proof. V2 removes that trust and validates explicit conjunctive proofs. It preserves useful supported notes while withholding terminal/open notes, unsupported body, ambiguous columns and missing native direction/order evidence.

However, the requested minimum includes simple Spanish body. V2 has no independent body-family proof and certifies none. It also does not automatically recover cross-page editorial owners/ends. These are implementation gaps, not an external geometry barrier. No post-holdout adjustment was made to force PASS.

## Validation

- Focal automatic/provenance/layout/zones/notes/columns/cross-page/quality: **118 passed**, including **27 new V2 tests**.
- Related library/PDF/Markdown/quality/content-ingestion helpers: **664 passed**, 10 warnings.
- Full backend: **1802 passed, 18 failed, 94 warnings**.
- All 18 failed nodes and complete failure-detail blocks are **byte-identical** to the demonstrated 1775/18/94 baseline. All PREEXISTING_BASELINE_FAILURE; **0 new regressions**. None fixed.
- Three fresh development certifications: identical full JSON digests, IDs, proofs, statuses, boundaries and continuation states. Real IR block/line permutations pass. Span container permutation is not claimed: within-line span order remains source-authoritative.
- Development eight-page extraction: 5.25–6.68 s/run; 18-page holdout: 15.71 s. No pathological growth observed on these samples; no general performance bound claimed.
- `git diff --check`: PASS; new source/docs whitespace and final diff review PASS. Frontend/LAT unchanged; no frontend or LAT gate required.

Tests and reproduction commands are in [backend-results.json](backend-results.json). `evaluate_holdout.py` is intentionally one-shot; do not delete its opening marker to rerun/tune V2.

## Evidence

- [V1 root cause](v1-failure-analysis.md), [five exact cases](v1-unsafe-certifications.json).
- [Proof contract](v2-proof-contract.md), [reason codes](v2-reason-codes.md).
- [167](page167-results.json), [55](page55-results.json), [56](page56-results.json), [cross-page](cross-page-results.json), [development](development-regressions.json).
- [Sealed definition](holdout-v2-definition.json), [hash manifest](holdout-v2-sealed-hash.txt), [opening record](holdout-evaluation-started.json), [results](holdout-v2-results.json).
- [Safety](unsafe-certification-analysis.md), [coverage](coverage-analysis.md), [stability](stability-results.json).
- [Baseline comparison](baseline-failure-comparison.json), [worktree](worktree-report.md), [recommendation](recommendation.md).

Scope: reviewed source ownership, structural/editorial boundaries and native text checks; not exhaustive rendered glyph QA, an independent human audit, or a guarantee over unseen documents. Coverage denominator includes known-good reference units that discovery does not separate. Unknown ownership is never ignored when evaluating a certification.

## Operations

Branch: `feature/console-backend-core`. HEAD initial/final:
`1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Only new V2 module, tests, development fixture and this report directory added. Existing files modified by this phase: **none**. Preexisting worktree SHA-256 preservation: YES.

Commit = NO; push = NO. PostgreSQL writes = NO; Milvus writes = NO;
C reingest = NO; publication changes = NO; production changes = NO;
services managed = NO; OCR = NO; worker enforcement = NO.

Next step: V3 certification work with another sealed holdout. Worker E2E remains closed; no reingesta of `Likutey Halajot — Interior Final`.
