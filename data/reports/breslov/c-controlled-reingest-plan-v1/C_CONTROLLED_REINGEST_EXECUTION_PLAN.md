# C controlled reingest — future execution plan V1

**PLAN ONLY. Nothing in this document authorizes execution. DEV only.**

## Decision and authority

Use **parallel NEW document generation**, reusing document identity, pipeline version, ingestion run, job/attempt and manifests. Do not add a competing generation-number system. OLD is document `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`, run `6c1a19b8-b60b-52de-b709-5496f4c6e937`, job `cf9b886c-bd8d-4514-97d4-0fee3e0fb8ed`, attempt 1. It remains authoritative through build and validation.

Existing gateway derives document UUID5 from `(knowledge_scope_id, source_sha256 + ':' + pipeline_version)`. A new approved pipeline version produces a distinct document without overwriting OLD, in the same tenant/scope. Ingestion run alone is NOT enough: canonical text ID is document-owned, chunks have no run FK, chunk_set_version is hardcoded 1. Repeating OLD version collides with OLD document/text and is forbidden. NEW ID must be computed and checked against OLD before any job. No NEW ID/job exists in this gate.

The ordinary upload rejects EXACT_DUPLICATE; changing pipeline version alone cannot bypass that guard. A future controlled same-source/new-version admission primitive must explicitly authorize this operation without changing generic duplicate protection. Do not change the PDF, hash, tenant, title or scope to evade it. Do not repurpose the E2E scope as a production-generation namespace.

## Prerequisite gate — not implemented here

`TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1` must close:

1. `MISSING_CONTROLLED_SAME_SOURCE_NEW_VERSION_ADMISSION`: bind approval to OLD ID, source SHA, tenant, distinct immutable pipeline version, computed NEW ID, and idempotency key; preserve duplicate rejection for ordinary uploads.
2. `MISSING_UNIFIED_ACTIVE_GENERATION_VISIBILITY`: all lexical, vector, enrichment, research, relation, page-publication and citation paths must select the same authorized active document. Merely using test_candidate/archived is insufficient today (text_search and hybrid enrichment do not filter document status). Milvus primary rows lack run/attempt fields; filter by document IDs and PG authority, before top-k as well as after hydration. Reject inactive vector hits, never emit fallback metadata for them.
3. `MISSING_ATOMIC_ACTIVE_GENERATION_SWITCH`: guarded tenant-scoped OLD/NEW status transition in one PG transaction, lock logical source/rows, compare expected OLD/run/version and NEW reconciliation seal, audit transition and reverse it. Reuse existing document statuses (`ready`/`archived`, candidate `test_candidate`), not an independent N/N+1 store. Every reader must honor these statuses; any include_test_candidates diagnostic opt-in must require explicit authorized candidate selection, never automatic inclusion. Epoch/request pinning and cache invalidation must prevent cross-generation mixing during in-flight requests.
4. `MISSING_GENERATION_SAFE_RETRY_AND_CLEANUP`: resource ownership must distinguish preexisting resources; gateway currently records resources without setting was_preexisting. An attempt that collides with an existing generation must fail before writes, not claim/clean shared resources. Retries must resume an identical manifest/content seal or retire only the failed candidate attempt. Never cascade into OLD; prove crash recovery/compensation.
5. `CURRENT_C_DURABLE_SOURCE_REFERENCE_MISSING`: external original exists and hash matches, but OLD source_path/source_uri are NULL and its deterministic durable file does not exist. Preserve and bind OLD source through an approved separate operation before snapshot/build. Reuse durable_source.preserve_source; do not invent a URL fallback or assert OLD viewer works today. NEW must preserve its own hash-checked original before searchable activation, including quarantined pages. Lifecycle retention/backups must cover the configured storage root (current default resolves to backend/sources).
6. Reconciliation tooling implementing the contract here, source/viewer checks, idempotent switch/reverse API/CLI, fault-injection tests, and documented authorized commands. No fictitious cutover command is supplied in this plan.

These are blockers to execution, not reasons to delete/rebuild OLD. The prerequisite must not reingest C as a side effect.

## Phase 0 — Preflight

Freeze approved branch/commit **including provenance dependencies**, worker/extractor/publication/certificate/config hashes, approved pipeline version and embedding alias/dimension. This worktree contains uncommitted extraction dependencies; this docs commit does NOT approve or include them. Future code must be versioned/revalidated independently. Remote/worktree checks, DEV endpoint allowlist, health of PostgreSQL/Milvus/LiteLLM, worker lease/queue/scope, storage persistence/capacity, credentials present but never printed. Any minimal embedding health probe belongs only to a separately authorized future execution gate; this gate made no model calls. No silent fallback allowed. Establish a writer exclusion/fence for C, authorized inspection identity, exact candidate IDs and visibility proof, reverse-switch rehearsal on fixtures, and retention hold. Checklist must be entirely PASS; unknown is NO-GO.

Source precondition: SHA-256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`, 4,550,267 bytes, 284 physical pages. Rehash input immediately before ingestion and before activation. Mismatch -> BLOCK REINGEST. Filename is not identity.

## Phase 1 — Snapshot current C

Follow current-c-snapshot-contract.md. Recapture immediately before building, not reuse this planning snapshot. Save full authoritative text/pages/chunks, region metadata if present, all source/citation mappings, actual Milvus float vectors + schema/index/model contract, manifests and visibility state; hash/seal and independently verify readability. Current report retains vector digests only, not a restorable vector backup. Freeze known-good/bad/partial-page query fixtures and results; absence of an OLD source reference must already be resolved. Capture all 284 physical pages, including 16 presently empty pages, and adjacent non-C corpus fingerprints. Snapshot/queries may not alter store contents.

## Phase 2 — Create isolated candidate

Only after prerequisite PASS and explicit execution authorization: controlled admission with distinct pipeline version, same approved SHA and tenant; record OLD/NEW document IDs, run, job, attempt, manifest, text IDs and expected collection. Existing primary collection `tebaai_breslov_chunks_v1` is reusable **only after unified visibility is proven**; no alias switch required. NEW is not normal-retrieval eligible even during partially persisted draft/chunk/vector stages. Inspect via an authorized explicit candidate-only diagnostic path. OLD stays ready. Assert active-generation cardinality = 1. No overwrite-first, no delete-first.

## Phase 3 — Candidate ingestion

Use existing regional publication pipeline unmodified in semantics: ACCEPTED+CERTIFIED only to canonical text/chunks/embeddings/vectors/citations. Region boundaries reset chunk overlap. Preserve original for every physical page; NOT ACCEPTED/UNRESOLVED/QUARANTINED produce zero searchable text, chunks, embeddings, vectors and textual citations. Do not run a legacy serializer on the side.

Counters per attempt/page/stage: pages processed (expected 284), regions accepted/quarantined with reason/status, FULL/PARTIAL/UNUSABLE/empty pages, chunks emitted, embedding requests/results and hashes, vectors inserted/reconciled, stage errors, retries, source SHA/path health, heartbeat, manifest ownership. Persist structured diagnostics for where failure occurred. Candidate chunk/embedding/vector set equality is required internally; OLD and NEW count equality is not.

Failure: OLD remains unchanged and active; NEW remains inactive failed/incomplete. Manifest compensation is candidate-only and only after safe ownership is proven. No automatic cleanup of CURRENT. On replay, identical approved inputs/version yield the same NEW document/chunk/PK set; no extra active generation, no duplicate chunks/vectors. Changed inputs need a newly approved version, not a silent replay over existing canonical text.

## Phase 4 — Candidate reconciliation

Produce region-reconciliation.json, page-reconciliation.json, document-reconciliation.json under the future execution report, following C_RECONCILIATION_CONTRACT.md. Explain each removed old evidence span against a nonpublishable new source region; preserve known good and good neighbors. Every unmatched/ambiguous mapping blocks approval; do not interpret lack of old region metadata as quarantine. Whole-document page/source/provenance coverage is exhaustive, not sampled. Candidate failure -> no cutover, OLD stays authoritative.

## Phase 5 — Retrieval/citation verification

Run sealed A known-good, B quarantined and C partial-page cases on OLD baseline and isolated NEW. Verify lexical/hybrid/vector paths, source/page citations and visual references, tenant authorization and normal user exclusion of NEW. Query embeddings/model use require separate execution approval, never occur here. Reconcile primary keys and content/model/source metadata exactly. Active duplicate evidence = 0, no cross-generation results. Critical known-good and neighbor queries all pass; bad evidence must be absent even if semantically related good text is returned.

## Phase 6 — Cutover

Require signed ingestion/reconciliation/retrieval/citation seals and separate cutover GO. Use only prerequisite-provided reversible atomic PG visibility operation: lock expected OLD/NEW, compare seals, switch OLD ready -> archived and NEW test_candidate -> ready in a single transaction, audit and commit once. Readers pin one committed visibility epoch; cached/in-flight results cannot splice generations. No sequential independent activate/deactivate requests. All vectors already exist: **visibility switch, no embedding/ingestion/deletion**. A lost response is resolved by reading transaction/audit state, never by blind replay. See cutover-design.md.

## Phase 7 — Post-cutover validation

Immediately execute post-cutover-validation-plan.md as normal authorized users on all retrieval surfaces. Must reach only NEW for logical C, preserve known good/neighbors/citations/source and exclude old/bad evidence/duplicates. Any listed critical failure -> mandatory reverse switch. No cleanup while investigating.

## Phase 8 — Stabilization

OLD rows/chunks/pages/vectors/source/embedding records/manifests remain intact but invisible; guard against TTL, generic cleanup and background workers. Observe critical-query regression, leakage and source health. Duration is not invented: owner must approve a retention/stabilization policy. Hold remains open until post-cutover validation, stability review and explicit rollback-window closure are signed. No automatic physical expiry.

## Phase 9 — eventual old-generation cleanup

Separate authorized gate after stabilization and rollback-window closure; exact OLD resource manifest, dependency/references audit, backup/restore verification and dry-run of selection. Never combine with cutover. No broad deletion by source SHA, scope, collection or title (OLD and NEW share them). After physical cleanup, instant rollback guarantee no longer applies; disaster restore is a separate procedure. This gate executes none of phases 1–9.

## Dry-run capability

Pure `extract_pdf_region_published(path, language)` -> PublishedPage and `publish_certified_page` exist and can run in memory, without gateway/stores/model calls. No end-to-end production worker `--dry-run` switch guarantees no writes: `ConcretePageFirstPipeline.run` persists pages/chunks and dispatches embeddings. A future offline publication preflight is useful for all 284 pages; implement/reuse a strictly pure harness separately and seal versions, but do not describe a worker dry-run as safe. No full-C extraction was run here.
