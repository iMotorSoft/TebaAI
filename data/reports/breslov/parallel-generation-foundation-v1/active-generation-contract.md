# Active-generation contract — NOT implemented

Authoritative mapping must be logical_document_id -> exactly one physical generation ID for a published document. No MAX/latest/title/source-hash heuristic and no interpretation of completed run as active.

Proposed logical row has pointer + monotonically increasing epoch and publication state. A composite FK enforces target ownership. Published state requires non-NULL pointer. Lifecycle validation enforces eligible target and prevents active deletion/failure. Unpublished/NEEDS_REVIEW rows return no normal evidence. Fail closed on missing/invalid ownership, pointer or provenance.

One immutable authorized request context captures logical IDs, physical generation IDs, provenance run and epoch. All PG branches, Milvus prefilters, viewer/publication and citations use that context. A consistent PG snapshot prevents intra-request splicing; if the epoch changed before response, discard/retry rather than mixing cached/in-flight evidence. An empty authorized ID set returns empty evidence or explicit unavailable state, never an omitted filter.

Current repository lacks this resolver and database invariants. Six new blocker reproductions and prior hydration regressions are not a proof of single-active behavior.
