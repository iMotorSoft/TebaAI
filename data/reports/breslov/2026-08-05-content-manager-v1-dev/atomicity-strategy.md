# PostgreSQL–Milvus atomicity strategy

Migration 041 establishes attempt and manifest persistence. Each created resource is intended to be recorded as `(manifest_id, resource_type, resource_id, was_preexisting)` before a later stage relies on it.

The required eventual-consistency algorithm is specified but not executable yet:

1. deterministic IDs per source/profile/pipeline;
2. PostgreSQL stage commit plus manifest resource rows;
3. idempotent Milvus upsert into an isolated collection;
4. reconciliation by exact document/job/attempt vector IDs;
5. terminal completion only with zero missing, orphan and duplicate IDs;
6. compensation only for non-preexisting manifest IDs.

Because the current Milvus client exposes insertion/search but no exact manifest cleanup/reconciliation API, the implementation gate remains BLOCKED.
