# Migration/backfill/rollback plan — not executable approval

1. Snapshot schema and map every existing document, canonical text, chunk, run, manifest and vector identity. Inventory null scope/source and multi-run histories explicitly. Do not assume a ready row implies a unique completed content owner.
2. Add logical registry, generation registrations, source reservations, operation records and ownership constraints additively. Preserve all historical document/chunk/vector IDs and metadata. Do not rebuild vectors just to introduce logical identity: existing vector document_id is the generation filter.
3. Backfill deterministic logical UUID(namespace, existing physical document UUID) only for proven unambiguous single-generation histories. Bind the actual completed canonical provenance run, not MAX(created_at). Multiple plausible owners, inconsistent runs, legacy missing provenance or same-source ambiguity become NEEDS_REVIEW and are not silently published.
4. Verify C's run/document/text/pages/chunks/manifest ownership using fresh inventory before any backfill. This gate's read-only run observation is not an authorization to modify C. No C backfill occurred.
5. Implement normal and candidate reader contexts across the route map while ordinary same-source admission stays disabled. Prove compatibility on single-generation fixtures and isolated PG/Milvus. Existing APIs retain physical document_id semantics.
6. Test reversible migration with fixtures for every historical case, repeat backfill, rollback, null scopes and races. Install replacement duplicate constraints and admit new generations only once all routing/lifecycle/provenance gates pass.
7. Apply in an explicitly approved DEV window; no automatic production startup migration as an experiment.

## Reversal

Before any multi-generation admission, additive schema can be removed after returning readers to the previous version; retain original indexes throughout that phase. After same-source generations exist, a down migration must **refuse** restoration of the old unique index while duplicates exist. Never delete candidates or OLD to force a down migration. Retain/fence readers and require a separately authorized export/retirement procedure. Claiming unconditional reversible down SQL would be false.

No migration was supplied/applied in this attempt; schema transition and foundation acceptance remain blocked.
