# Identity model — explicit design decision, NOT implemented

## Existing semantics to preserve

`document_id` denotes the physical processed document representation. Canonical texts, chunks, embedding mappings, vector metadata and source URLs depend on this ownership. Reinterpreting it as logical identity would cause two generations to overwrite/share document-owned resources. Keep historical UUIDs and existing public API argument meaning.

## Proposed identities

- `logical_document_id`: new stable identity within authorized tenant/scope/collection; not filename, title or source SHA. One logical document may eventually accept changed sources as well as same-source reprocessing.
- `generation_id`: alias of physical `library_documents.id`, not a second unrelated UUID. A generation is immutable processed content once sealed.
- `ingestion_run_id`: existing `library_ingestion_runs_v2.run_id`, related to a build attempt, never automatically equal to generation ID. Multiple failed/retried attempts must not change generation identity or claim sibling resources.
- Active pointer: proposed logical row `(logical_document_id, active_generation_id, epoch)`; composite ownership FK to the selected generation.

Current gateway derives document UUID from scope/source/pipeline, run from document/attempt. Preserve old IDs. For controlled new admissions derive physical UUID from logical ID plus a durable admission operation identity, not source alone or only pipeline version: A/B candidates with the same parser may be intentionally distinct. Normal one-generation upload retains its existing compatibility ID.

Idempotent operation replay uses a stored request digest, not a new attempt ID. Existing chunk/entity evidence IDs are already physical-document-bound via chunk identity. Responses should additionally expose logical/generation provenance. Existing document-specific source URLs stay pinned; logical normal viewer resolution must be a separate operation, not a silent redirect of historical citations.

C generation ID remains `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`; observed run is `6c1a19b8-b60b-52de-b709-5496f4c6e937`. The latter is **not** an existing generation pointer.
