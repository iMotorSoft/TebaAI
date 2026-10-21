# Cutover design — blocked until prerequisite implementation

## Existing vs missing

`content_manager.publish_document` (content_manager.py) checks candidate reconciliation then updates that document to ready. It does not deactivate a prior same-source document and supplies no atomic reverse pair. library_documents has ready/test_candidate/archived statuses; no active-run pointer or superseded_by column. Chunk_set_version exists but the page-first gateway writes 1 and retrieval does not gate on it. Therefore do not invent a run-active flag or perform two publication requests.

Reuse separate document identities with immutable pipeline versions and existing statuses. Every reader must enforce generation visibility consistently first; otherwise even archived OLD can leak through lexical/hybrid search. Unified authorization/visibility must apply to candidate exclusion, vector prefilter and PG hydration, relation/research branches, citation construction, page selection and cached results. Direct diagnostic inspection of inactive NEW must be explicit, authorized and excluded from ordinary user query parameters. Source access for retained OLD citations may remain explicitly inspectable under authorized archival policy without making OLD searchable.

## Desired invariant

For tenant + logical source SHA, exactly one normal-search eligible document:

| State | OLD | NEW |
|---|---|---|
| build | ready/eligible | draft or test_candidate/ineligible |
| reconciled, pre-cutover | ready/eligible | test_candidate/ineligible |
| committed cutover | archived/ineligible | ready/eligible |
| rollback | ready/eligible | archived/ineligible |

Any committed dual eligibility or zero eligibility caused by partial state is an incident. No physical data is deleted during these transitions. Existing independently stored chunks/vectors must not count as duplicates unless both are visible for the same source evidence.

## Future transaction semantics (design, not executable SQL/API)

Acquire tenant/source lock; lock OLD+NEW rows in deterministic ID order. Read and compare expected active OLD identity/run/version, candidate completed immutable reconciliation seal, source durability, manifest ownership, tenant equality and active cardinality. Atomically archive OLD and ready NEW plus append audit/reversal metadata in one PG transaction with compare-and-swap semantics. Reject stale approvals or a third active generation. A repeated identical request returns its recorded committed result; it cannot increment generations or embed again. Both changes and audit roll back if any assertion fails. The exact implementation/API and schema for audit/seals must be delivered by prerequisite; no such command is runnable today.

Milvus stores both document-specific PK sets; no visibility bits/aliases are dual-written there. Filter query candidates to the PG-selected active document IDs before top-k, then revalidate PG hydration; semantic search cannot consume candidate slots and hide OLD during build. Avoid stale active-ID cache: pin generation/epoch once per request, execute consistent PG reads and bind vector filter/citations to it, revalidate before response or discard stale responses. Conversation/citation caches cannot reuse inactive evidence as normal results. Existing archived source lookup may require a deliberate historical-inspection path; source references must stay resolvable through retention.

Lost network response -> read audit/visibility state. Before commit, OLD remains authoritative; after commit, NEW is authoritative; rollback only by reverse transaction. Current architecture lacks these controls, so any partial switch recovery today is a blocking gap, not a supported workaround. No embedding, ingestion, vector mutation or OLD cleanup is part of cutover.

## Verification required in prerequisite

Concurrency: simultaneous promotion, stale job retry, racing readers/cleanup, lease recovery, process death before/between updates/after commit, lost response and retry, stale caches, guessed candidate IDs, include_test_candidates opt-in and page metadata selecting latest run. Demonstrate one visible generation and zero mixed evidence throughout. Reverse switch must succeed with OLD retained and no external reembedding. Fault tests use fixtures/disposable stores, never current C without separate approval.
