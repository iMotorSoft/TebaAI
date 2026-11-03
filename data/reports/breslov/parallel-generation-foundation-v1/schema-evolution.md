# Schema evolution — design only

No migration SQL was added to the auto-discovered migration directory. No index was changed. The old uniqueness test passed on connection-local temporary rows; this does not validate a replacement migration.

## Required coordinated replacement

- Logical document row with tenant/scope/collection ownership and publication state.
- Registered physical generation references existing `library_documents.id`, logical owner, build state, provenance run, immutable build/source seals and cleanup ownership.
- Scoped logical-source reservation preserves `UNIQUE(scope, collection, source_sha256)` at the **logical ownership** level. Use explicit separate unscoped protection for legacy NULL scope; do not accidentally let NULL semantics remove duplicate protection. Multiple generations may reference the same reservation; ordinary upload cannot create a second logical owner.
- Admission operation with `UNIQUE(logical_document_id, operation_key)` and immutable request digest. Reusing a key with different inputs is an error, not reuse or overwrite.
- Active pointer FK must reference a generation belonging to that logical document. Published logical rows require non-NULL pointer; unpublished/NEEDS_REVIEW rows are non-visible. A pointer holds exactly one ID; no competing per-generation active flags.
- Database constraints/controlled lifecycle writes must prevent an active target becoming FAILED/DELETING/deleted and prevent cross-tenant source/generation associations. A pointer alone does not validate READY or durable provenance.
- Switch audit records expected/actual/target/epoch, actor and operation identity in the same transaction.

Drop/recreate migration 042's scoped index only in the coordinated rollout after replacement constraints, backfill, admission and **all** reader fences are tested. Unscoped documents must also remain protected. Merely making the index `(scope, collection, SHA, generation)` would lose ordinary-upload protection and is rejected.
