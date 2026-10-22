# Recommendation

PLAN_READY = YES. Do not execute C reingestion.

Next: **TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1** — decide and seal the
generation-identity model (A: logical identity + generation rows, with a reviewed
migration of the live `uq_library_documents_scope_collection_sha256`; or B:
generation-scoped chunks inside the single document row; the old "second physical
document" model is inadmissible while that index stands), implement an explicit
fail-closed active-generation pointer, enforce one shared active-generation
predicate across every lexical/vector/research/relation/Book-QA/citation/page
route (including the page-publication route that today resolves the newest
completed run), implement an atomic audited forward/reverse visibility switch with
request epochs and cache coherence, prove generation-safe retry/manifest cleanup
ownership, repair/verify OLD source durability under separate write authorization,
and build the sealed semantic reconciliation harness with A/B/C query fixtures and
fault tests. The prerequisite must not create a C candidate or reingest C
implicitly.

Then refresh the read-only inventory, source SHA, complete snapshot and query
baseline; obtain explicit execution authorization for
**TEBAAI_BRESLOV_C_CONTROLLED_REINGEST_V1**. OLD remains authoritative and
retained throughout candidate build/validation. No delete-first, overwrite-first,
simultaneous duplicate evidence, reembed-at-cutover or cleanup-at-cutover.

Planning PASS does not mean FULL_C_REINGEST_READY. Current original source
identity, active run and 942 chunks/vectors are unambiguous and unchanged since
the previous plan run; the implementation gaps are explicit prerequisites, not a
license to fake an executable cutover command.
