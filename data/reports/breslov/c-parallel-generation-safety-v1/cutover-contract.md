# Cutover contract — NOT IMPLEMENTED / NEVER EXECUTED

Follow [prior cutover design](../c-controlled-reingest-plan-v1/cutover-design.md). Existing `publish_document` CAS-promotes one candidate status; it is **not** a reversible expected-OLD active-generation switch.

Required implementation must use one PostgreSQL transaction and a common tenant/logical-source lifecycle lock shared with publication, retry and cleanup. Compare expected OLD generation+epoch; validate NEW build, immutable reconciliation/source seals, same tenant/source, candidate isolation and retention ownership; update explicit active identity and audit atomically. A failure or stale expected OLD changes nothing. Lost-response retry reads committed audit state, not blind promotion. Reader/cache coherence is part of atomicity, not optional.

No vector insert/delete/alias operation belongs in this switch. Both exact document-specific PK sets remain physically stored. Never perform two independent status API calls. Never accept largest chunk count/latest run as authority.

No migration, transaction primitive, audit/reversal API, concurrent PostgreSQL test, epoch or cutover execution was delivered here. Therefore ATOMIC_SWITCH, SINGLE_ACTIVE_INVARIANT and STALE_SWITCH_REJECTED are NOT DEMONSTRATED. A single existing C generation is not an atomic-switch proof. Structural same-source uniqueness must first be resolved as described in generation-contract.md.
