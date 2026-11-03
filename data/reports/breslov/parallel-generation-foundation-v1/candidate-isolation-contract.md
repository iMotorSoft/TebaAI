# Explicit candidate isolation — NOT implemented

Candidate evidence requires logical_document_id + exact generation_id, scope authorization and explicit inspector permission. Validate ownership and READY build/provenance seal. BUILDING/FAILED inspection diagnostics must not be returned as searchable/citable evidence. Do not repurpose include_test_candidates=true to admit every candidate.

Candidate resolver must produce the same immutable generation-bound context shape as normal retrieval but with explicit candidate policy. It never updates active pointer, never falls back to active/latest/siblings and rejects cross-logical or cross-tenant IDs. Normal APIs must not accept candidate mode accidentally through a generic boolean.

Filter Milvus by the exact physical document_id before ranking. Every PG literal, page and chunk lookup must apply the same exact owner; returned evidence/citation/source maps identify the generation. Normal viewer resolves active; candidate viewer requires explicit inspector context. Historical document-specific citations remain pinned and require separate retention access policy, not a redirect to the new generation.

No candidate API/resolver/UI was added. The new synthetic hybrid test proves that a canonically hydrated candidate is still surfaced today; this is a blocker, not successful isolation.
