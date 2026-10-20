# Continuation analysis — V4

| Metric | Value |
|---|---|
| Cross-page units (sealed holdout) | 7 |
| Correctly linked | 7 |
| Unsafe false continuations | 0 |
| False editorial completions | 0 |

V4 links only when the next segment carries the expected continued note under
the same deterministic editorial identity. A local page segment is never
declared `COMPLETE_LOCAL` at a page cut unless the source line truly ends the
note. Development regression (older V3 holdout): 3/4 linked,
remaining unresolved pair stays open rather than falsely completed.
