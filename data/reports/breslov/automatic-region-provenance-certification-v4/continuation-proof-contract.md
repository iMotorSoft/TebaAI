# V4 continuation proof contract

1. A note origin segment within a page is `CONTINUES_NEXT_PAGE` only when the
   following page's first note-zone lines carry the expected continued marker
   under the same deterministic `editorial_unit_id`.
2. The receiving segment is `CONTINUED_FROM_PREVIOUS` with the reciprocal
   link.
3. Continuation across the document is resolved after all pages are mapped so
   identity is stable and order-invariant.
4. A page cut alone never implies `COMPLETE_LOCAL`; false completions are
   counted independently and must stay 0.
