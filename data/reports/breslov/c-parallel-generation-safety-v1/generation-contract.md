# Generation contract — NOT IMPLEMENTED

Binding antecedent: [prior execution plan](../c-controlled-reingest-plan-v1/C_CONTROLLED_REINGEST_EXECUTION_PLAN.md). No new generation-number architecture was introduced.

- Logical document groups same approved source in its authorized tenant/scope; a title is not identity.
- Physical generation reuses a distinct document UUID derived from scope + source SHA + approved immutable pipeline version. Run/job/attempt/manifests remain provenance. A run alone cannot own a generation because text/chunks are document-owned.
- Normal active generation must be an explicit authoritative identity, never latest/count/status heuristic.
- Candidates must exist physically without changing active identity; BUILDING/FAILED must remain invisible.
- Exactly one generation must be normal-visible at any observable successful cutover. Historical ambiguity must fail closed, never select latest.

## Structural blocker confirmed after detailed inventory

`db/migrations/042_scope_legacy_source_uniqueness.sql` and **live DEV** `schema-index-inventory.json` establish the unique index `uq_library_documents_scope_collection_sha256` on `(knowledge_scope_id, collection_id, source_sha256)` for scoped rows. Changing pipeline_version/document UUID does **not** change these indexed fields. The planned same-scope/same-source parallel document cannot currently be inserted. This is additional evidence, not permission to change source identity or use a different scope/collection.

Required continuation: explicit reviewed migration integrating existing generation identity and uniqueness with logical identity/active selection, conservative historical backfill, retained ordinary-upload duplicate protection, common visibility/locking and migration tests. No such migration is supplied/applied here. Do not simply drop duplicate protection in isolation.

Implemented narrow prerequisite: gateway document INSERT uses `RETURNING id`; a conflicting document UUID aborts before run/text/page/manifest creation. This rejects unsafe collision, **not** idempotent resume. Existing manifest cleanup→retry workflow remains, without claiming full retry safety.

C retains its one observed ready document and sole completed run. This observation is not an implemented active-generation pointer. No NEW generation/job/version was created. No C backfill was performed.
