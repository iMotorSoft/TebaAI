# Recommendation

The gate fails. Frozen V4 has two unsafe failure modes on the new sealed
holdout: an annotation mapping defect on pages 13/15 and a genuine false
cross-page continuation on pages 206/207. The second is a V4 continuation-proof
defect and must not be hidden by the first.

- `TEBAAI_BRESLOV_V4_FROZEN_CONFIRMATION_AND_CONSUMER_BOUNDARY_V1 = FAIL`
- `CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO`
- `READY_FOR_C_REINGEST = NO`
- Keep the consumer boundary fix: it now calls V4 explicitly and fails closed
  without a V1 fallback.
- Do not reseal, reopen or tune against this holdout.
- Do not integrate certificates into the worker or reingest the corpus.

Next phase should, in order:

1. Treat the page 206/207 leading-body link as a V4 continuation-proof bug:
   the terminal note proof must independently establish that the next-page
   starting region is a note continuation, not body text.
2. Build a new independent holdout with line-level note grouping that is not
   based on full-width centre assignment, preserving the single-open rule.
3. Re-run frozen or successor V4 on that new holdout, then re-evaluate worker
   integration readiness.

Commit = NO; push = NO; branch changes = NO; services managed = NO.
PostgreSQL writes = NO; Milvus writes = NO; C reingest = NO; production changes
= NO; OCR = NO; orthographic search changes = NO.
