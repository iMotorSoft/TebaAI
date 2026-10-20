# Safe adjacent-page continuation proof

All required:

1. Same source SHA, adjacent physical pages; exactly one open terminal note.
2. Origin segment passes every unchanged V2 note proof except continuation/completion. V2's native/source corroboration is not weakened for open segments.
3. Next page independently matches the ruled editorial family, including notes separator and explicit anchors.
4. Its entire note-zone typography is a subset of origin segment font/size pairs; all boxes have supported text/footnote/source-linked footer roles.
5. Existing provenance adapter validates disjoint columns, source identities and stable editorial flow, with origin ownership retained as context, not a manual certificate.
6. First next-page segment has no new marker. It ends before an explicit next consecutive marker. A page cut alone never proves the relation or end.
7. Next segment has unique non-overlapping ownership, monotonic unique source IDs, visible native horizontal LTR direction and unmixed strong script.
8. Exact source-part partition is preserved when rebuilding page slices; no untracked line may be discarded or borrowed.

Then emit reciprocal deterministic editorial links and `CROSS_PAGE_COMPLETE` on the relation, with distinct physical segment states. Every segment's quality still independently requires exact native/source tokens and serializer equivalence. The next segment may correctly remain quality UNRESOLVED.

No semantic similarity, LLM, trailing punctuation, visual adjacency alone, or automatic left-bottom→right-top transition proves continuity. Missing proof produces no link, no editorial ID borrowed from a neighbor and no claimed completion. Auditable reasons: unchanged V2 missing-proof codes, `CROSS_PAGE_IDENTITY_PROVEN`, and `INDEPENDENT_SEGMENT_PROOFS_REQUIRED` for other newly discovered notes that were not independently certified.

Development controls include same-page notes, a genuinely unmarked continuation, a new numbered unrelated note, wrong successor, changed typography, absent separator, mixed/incorrect direction, duplicate owner, missing actual end and a non-adjacent page.
