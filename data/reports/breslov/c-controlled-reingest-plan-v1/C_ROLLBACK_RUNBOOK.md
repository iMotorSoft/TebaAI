# C rollback runbook V1 — future only

**No rollback/cutover is executed here.** Rollback is conceptually possible without reingesting OLD, but a unified visibility predicate and atomic reversible operation are missing today. Do not issue two independent status updates as a substitute. Required prerequisite: TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1 (which must first resolve the same-source uniqueness conflict and the page-publication hijack described below).

**Refresh 2026-10-22:** OLD identity re-verified read-only and unchanged (document, run, job/attempt, manifest, text, 284 pages, 942 chunks, 942 vectors, identical content digests to the 2026-10-21 run). NEW does not exist and cannot be identified by "latest completed run" — that heuristic is itself a defect, because `source_repository.get_page_publication` selects the newest completed run and would therefore resolve an un-cutover candidate as the published page view.

## Identify OLD and NEW

OLD: document `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`, ingestion run `6c1a19b8-b60b-52de-b709-5496f4c6e937`, job `cf9b886c-bd8d-4514-97d4-0fee3e0fb8ed`, attempt 1, manifest `445e33ee-b352-5191-aa20-a13208695442`, text `8be8899c-07e4-54b7-954f-d719ce217af4`, pipeline content_page_first_v1; 284 pages, 942 chunks/vectors at planning inventory. All must be rechecked against the pre-execution snapshot. Historical `132a791a-...` is NOT OLD for this cutover.

NEW: does not exist. The future execution manifest must contain the computed NEW identity **as decided by the prerequisite** — either a distinct document UUID (requires the reviewed migration of the live uniqueness index `uq_library_documents_scope_collection_sha256`) or a generation identity inside the same document row — plus the approved pipeline/generation version, run/job/attempt/manifest IDs, exact chunk/vector PK set, source SHA, tenant/scope, completed reconciliation seal and cutover transaction/audit identity. NEVER infer NEW as latest finished run or by title/source SHA alone (OLD shares source SHA). Compare expected active generation before acting.

## Mandatory rollback triggers

Any unexpected accepted-content loss, bad Hebrew/searchable leakage, lost good neighbor, missing page/source, citation/page mismatch, vector/chunk/content mismatch, duplicate active retrieval, mixed OLD/NEW evidence, critical query regression, partial visibility state or unverified activation -> **ROLLBACK REQUIRED**. Infrastructure outage blocks validation; do not declare stabilization or delete OLD. If the switch cannot be safely verified, fence normal C queries and escalate rather than serve both generations.

## Future reverse operation

1. Freeze C publication/retry/cleanup writers; retain both full generations and evidence. Acquire the same logical-source/tenant lock as cutover. Record incident and expected cutover audit/visibility epoch. Do not stop/reconfigure external services.
2. Read current OLD/NEW state and audit in read-only mode. If OLD already active and NEW inactive, verify and return idempotent success; if an unknown third generation is active, refuse and escalate. If the prior transaction never committed, OLD should still be active.
3. Use the prerequisite's approved audited reverse-switch primitive: in **one PG transaction**, assert expected NEW active + OLD inactive, validate retained OLD snapshot/PK/source integrity and same approved tenant/source; make NEW inactive and OLD active, record reverse event and advance visibility epoch. Commit once. Disable NEW normal retrieval and reactivate OLD at the same commit boundary. No Milvus insertion/deletion, no reembedding and no reingestion. If OLD and NEW share the physical document row, the reverse switch must also restore the **page-publication** resolution to OLD's generation, not merely a status flag.
4. Invalidate generation-bound query/result caches and conversation evidence references or revalidate them; in-flight responses must be pinned or discarded if their epoch is no longer active. Never mix retained NEW citations into OLD results.
5. Run all post-cutover tests with target OLD: normal lexical/vector/hybrid/research/relation results for C contain only OLD chunk/evidence IDs; PG hydration maps to OLD; critical known-good and partial-page baseline behavior is restored; NEW has zero normal hits; active logical-evidence duplicates zero; source/viewer resolves OLD approved PDF/page. OLD corruption that already existed is recorded baseline debt, not claimed fixed by rollback. Validate unrelated A/B corpus unchanged.
6. Persist reverse audit, before/after state, test results and issue follow-up. Keep NEW inactive for forensic inspection. No automatic cleanup. If verification fails, fence affected C queries and escalate; never delete OLD or blindly repeat ingestion.

## What must remain retained

OLD document/text/pages (all physical pages and source maps), chunk contents and search fields, embedding tracking/model metadata, actual Milvus vectors/PKs, ingestion/embedding runs, manifests/resource ownership, citation entity/evidence lineage, durable original and external approved source reference, original metadata/status snapshot, cutover and reverse audits, sealed baseline/reconciliation results and visibility/cache contract. Shared-source cleanup by SHA is forbidden. Source TTL or filesystem cleanup must not remove retained originals.

There is no approved time-based retention policy in the inspected implementation. No invented 7/30-day window. OLD cannot be physically deleted until post-cutover validation and stabilization close, owner approves a retention policy, rollback window is explicitly closed and a separate cleanup gate is authorized. Initial cutover never deletes OLD. Retaining rows without filtering them from all retrieval paths is not a valid rollback implementation.

## Partial cutover / lost response

Atomic PG commit yields either OLD active or NEW active, never a committed half-state. Read audit and state to determine outcome; a network timeout is not proof of failure. Milvus stores both generations, so no distributed PG/Milvus visibility dual-write is necessary **after all readers filter through PG active state**. Cache/reader coherence still must be proved. If partial state is observable under today's code, the execution gate is blocked: fix prerequisite, do not attempt compensating ad-hoc SQL.

ROLLBACK POSSIBLE = YES, conditional on prerequisite and retained data.
ROLLBACK REQUIRES REINGESTING OLD C = NO.
OLD PHYSICALLY DELETED AT CUTOVER = NO.
CUTOVER REVERSIBLE BEFORE CLEANUP = YES, after prerequisite PASS.
