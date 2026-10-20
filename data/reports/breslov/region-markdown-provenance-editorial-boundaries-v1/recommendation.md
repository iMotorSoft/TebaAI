# Recommendation

Proceed ONLY to:

`TEBAAI_BRESLOV_QUALITY_ENFORCEMENT_WORKER_E2E_V1`

Do not reingest C yet. `READY_FOR_C_REINGEST = NO` until worker enforcement
and isolated official DEV E2E both pass. This phase made no worker change.

## Integration constraints for the next gate

1. Retain PyMuPDF4LLM IR in the canonical extractor path. Propagate forward
   ownership and immutable candidate ranges, not matching against old stored
   Markdown. Keep raw diagnostic canonical projection separate from Markdown.
2. Persist source-part union and editorial continuation relations, not just
   envelope bboxes. Never treat a page cut as a note termination.
3. Establish how runtime supplies/verifies note-zone and direction certificates.
   Explicit fixture certificates are proven input contracts, not a universal
   automatic detector. Where labels/geometry are insufficient, record UNRESOLVED;
   do not copy57's coordinates or any golden number into runtime logic.
4. Apply existing quality decisions only to exact mapped units. Persist every
   rejected unit's trace metadata; never expose quarantined text as a citation,
   search field, embedding, warning placeholder or overlap chunk.
5. Keep good units separate across quarantine gaps. Preserve original offsets
   or supply an explicit rebasing map; never reuse stale candidate offsets on
   a concatenated accepted-only string.
6. Add reproducible DEV E2E of canonical persistence, accepted-only chunks,
   embeddings/index reconciliation and literal evidence selection. No such
   PG/Milvus/citation guarantee was tested in this phase.
7. Keep unsupported transformations UNRESOLVED. In particular, don't silently
   bless the existing page56 body dehyphenation, page55 marginal/body overlap,
   or full57 duplicate marginal line because these note goldens pass.

Do not reactivate SI-960, modify visibility, add OCR, expand Hebrew search or
perform whole-C reingestion as a shortcut. These are different gates.

Impact: reproducible source-to-editorial-to-Markdown ownership and exact
candidate exclusion, with real cross-column and cross-page note boundaries.
Risk: interpreting a successful supported-layout offline gate as automatic
whole-document coverage or current-worker protection. Both interpretations are
explicitly unsupported.
