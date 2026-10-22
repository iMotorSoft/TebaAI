# C controlled reingest — future execution plan V1

**PLAN ONLY. Nothing in this document authorizes execution. DEV only.**

Refresh: 2026-10-22 (second plan run, after `TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1`
and `TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V1` both closed **BLOCKED**).
Current C was re-inventoried read-only and is **byte-identical** to the first plan run
(2026-10-21): same document, run, job/attempt, 284 pages, 942 chunks, 942 vectors,
same content digests. No C data changed between the two plan runs.

## Decision and authority

Strategy: **parallel NEW generation, no delete-first, no overwrite-first**. OLD stays
authoritative and retrievable from the first second of the candidate build until an
explicit, audited, reversible cutover.

OLD identity (re-verified 2026-10-22, read-only):

| Field | Value |
|---|---|
| document_id | `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa` |
| ingestion run | `6c1a19b8-b60b-52de-b709-5496f4c6e937` (completed) |
| job / attempt | `cf9b886c-bd8d-4514-97d4-0fee3e0fb8ed` / 1 |
| manifest | `445e33ee-b352-5191-aa20-a13208695442` |
| canonical text | `8be8899c-07e4-54b7-954f-d719ce217af4` |
| pipeline | `content_page_first_v1` |
| source SHA-256 | `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a` (4 550 267 bytes, 284 pages) |
| pages / chunks / vectors | 284 (268 nonempty, 16 empty) / 942 / 942 |
| durable source | **NO** (`source_path`/`source_uri` NULL, deterministic durable file absent) |

The historical document `132a791a-…` (2026-07-30 page-first run, 268 chunks) is **not**
OLD for this cutover and is not present in current DEV.

**No NEW ID/job exists in this gate.** No candidate document, generation, run, job,
attempt, manifest, chunk, embedding or vector was created, claimed or reserved by
this planning gate.

### Refresh delta 2026-10-22 — what the two blocked prerequisite gates changed

1. **The "second physical document" candidate is structurally blocked.** Live DEV
   `library_documents` carries unique index
   `uq_library_documents_scope_collection_sha256 (knowledge_scope_id, collection_id, source_sha256)`
   (migration `042_scope_legacy_source_uniqueness.sql`, re-probed read-only in
   `indexes-readonly.json`). A second physical document with the same tenant, same
   legacy collection and the same approved source SHA **cannot be inserted**, no
   matter which pipeline version or UUID is chosen. The first plan run assumed that a
   distinct pipeline version yields a distinct document; that assumption is now
   falsified by live schema evidence. The candidate admission model must therefore
   change (see *Candidate admission models*).
2. **A completed candidate run would hijack the source viewer.** `source_repository.get_page_publication`
   selects `ORDER BY r.finished_at DESC LIMIT 1` over runs with `status='completed'`
   for the same `document_id`. With a per-generation run inside the same document, a
   finished NEW run silently replaces the published page view of OLD **before** any
   cutover. This is a concrete, currently-unmitigated isolation defect and belongs to
   the isolation prerequisite.
3. **No unified active-generation predicate exists anywhere.** `text_search.py` and
   `hybrid_search.py` contain **no** `status` filter; `simple_research_repository.py`
   filters `ready` (+ opt-in `test_candidate`); `relation_qa_repository.py` filters by
   an allow-list of statuses; `source_repository.py` accepts `ready` and
   `test_candidate` and picks the newest completed run. Retrieval, citation and viewer
   therefore disagree about which generation is visible.
4. **Defensive patches exist but are not generation primitives.** Uncommitted work in
   this worktree adds: an INSERT-collision guard in `page_first_gateway.persist_document_and_pages`
   (aborts instead of adopting preexisting resources), a status preflight in
   `content_manager_cleanup` (refuses to clean a `ready`/archived document), and PG
   hydration hardening in `hybrid_search` (never emits Milvus metadata for a chunk PG
   cannot authorize). These reduce damage; they do **not** provide isolation, an
   active pointer, an atomic switch, a rollback primitive or a safe retry/cleanup
   ownership proof.

### Candidate admission models (must be decided by the prerequisite gate)

| Model | Description | Consequence |
|---|---|---|
| **A. Logical identity + generation rows** (recommended) | One logical document (NEW: `logical_document_id`), N physical generations; uniqueness moves from `(scope, collection, source_sha256)` to `(logical_document_id, generation)`; explicit `active_generation` pointer. | Requires reviewed schema evolution, backfill, reader/admission/lifecycle changes, rollback of the migration. Highest fidelity to the required semantics; the only model that supports "same source, same scope, two coexisting generations". |
| **B. One document row, generation-scoped chunks** | Keep the single `library_documents` row (unique index untouched); chunks/embeddings/vectors/pages carry `generation_id`; one active-generation pointer on the document. | Avoids the uniqueness conflict without a uniqueness relaxation, but requires adding generation identity to chunks/pages/embeddings/vectors, rewriting every reader and citation, and re-deriving all reconciliation keys. Chunk/vector citation identity (currently `document_id + chunk_id`) changes. |
| **C. Second physical document** (rejected) | Different `document_id`, same scope/collection/source. | **Blocked by live unique index 042.** Requires dropping duplicate protection, which this plan forbids. Not admissible. |

Both A and B must additionally implement: an explicit active-generation pointer, a
unified visibility predicate used by *every* reader, a reversible atomic switch, a
safe retry/cleanup ownership proof, generation-scoped citation identity, and durable
source binding. **The plan does not choose the schema; the prerequisite gate must.**

**The E2E scope/collection must not be repurposed** as a production generation
namespace: it would change tenant/scope semantics, citation scope and the collection
of record, and it cannot be promoted without re-ingesting at cutover (forbidden).

## Reuse of existing abstractions

Do not invent a competing N/N+1 versioning system. Reuse, in this order:

1. `library_ingestion_runs_v2` (run identity, status, `finished_at`) — the generation
   *execution* identity, already per document and per job/attempt.
2. `content_manager_jobs` / `content_manager_job_attempts` /
   `content_manager_ingestion_manifests` / `content_manager_manifest_resources` —
   attempt and ownership identity, already sealed and auditable.
3. `library_documents.status` (`draft` → `test_candidate` → `ready` → `archived`) —
   the existing visibility vocabulary, **plus** the missing explicit active-generation
   pointer.
4. `chunk_set_version` on `library_document_chunks` — currently hardcoded to 1; a
   candidate implementation must make it meaningful and enforced, not merely bumped.
5. `library_pages_v2.layout_notes->'region_publication'` — the per-page
   FULL/PARTIAL/UNUSABLE + per-region ACCEPTED/QUARANTINED record produced by
   `modules/library/region_publication.py` (`region-publication-v1`).

Constraints that are **not** generation identity and must not be used as such:
canonical text id is document-owned; chunks carry no run FK; Milvus primary rows
carry no run/attempt; evidence id v2 is chunk+entity derived and may legitimately
change between generations.

## Prerequisite gate — not implemented here

`TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1` (with the foundation work it
already declared) must close all of:

1. `MISSING_LOGICAL_IDENTITY_AND_ACTIVE_GENERATION_POINTER` — explicit logical
   document identity, per-generation rows, exactly one active generation, unknown
   historical active identity must **fail closed** (never "select latest").
   Includes the reviewed schema evolution required by the live unique index.
2. `MISSING_CONTROLLED_SAME_SOURCE_NEW_VERSION_ADMISSION` — bind approval to OLD ID,
   source SHA, tenant, distinct immutable pipeline/generation version, computed NEW
   identity and an idempotency key; preserve duplicate rejection for ordinary uploads.
3. `MISSING_UNIFIED_ACTIVE_GENERATION_VISIBILITY` — one predicate shared by
   lexical (`text_search`), vector/hybrid (`hybrid_search`), enrichment, research
   (`simple_research_repository`), relation (`relation_qa_repository`), Book QA,
   page-publication (`source_repository.get_page_publication`) and citation
   resolution. Milvus filtering must use the PG-selected active document set **before
   top-k**, not only after hydration; inactive hits must never contribute fallback
   metadata. The `include_test_candidates` diagnostic opt-in must require an explicit
   authorized candidate selection, never automatic inclusion.
4. `MISSING_ATOMIC_ACTIVE_GENERATION_SWITCH` — one PG transaction that locks the
   logical source, compares the expected OLD identity and the NEW reconciliation
   seal, flips exactly one active generation, audits and advances a visibility epoch.
   Reverse operation must be the same primitive, not two ad-hoc status updates.
5. `MISSING_GENERATION_SAFE_RETRY_AND_CLEANUP` — resource ownership must distinguish
   preexisting resources; a colliding attempt must fail **before** any write; retries
   must resume an identical manifest/content seal or retire only the failed
   candidate; cleanup must never cascade into OLD; concurrent publication vs
   cleanup TOCTOU must be closed.
6. `CURRENT_C_DURABLE_SOURCE_REFERENCE_MISSING` — bind OLD to a hash-checked durable
   original (reuse `durable_source.preserve_source`) and prove storage
   persistence/retention/backup plus authenticated viewer access. A URL fallback is
   not durability.
7. `MISSING_RECONCILIATION_HARNESS` — the tooling that emits
   `region-reconciliation.json`, `page-reconciliation.json`,
   `document-reconciliation.json` and the A/B/C query fixtures, plus fault-injection
   tests (crash during ingest, during reconciliation, during cutover; rollback from
   each state).

These are blockers to execution, not reasons to delete or rebuild OLD. The
prerequisite must not create a C candidate or reingest C as a side effect.

## Phase 0 — Preflight

Freeze the approved branch/commit **including provenance dependencies**
(worker/extractor/certifier/publication/config hashes, the uncommitted
`pdf_font_unicode.py`, `pdf_text_reconstruction.py`, `pdf_text_visibility.py`
dependencies must be versioned and revalidated separately — this plan does not
approve them), the approved pipeline/generation version, and the embedding
alias/dimension. Verify remote/worktree state, DEV endpoint allowlist, health of
PostgreSQL/Milvus/LiteLLM, worker lease/queue/scope, storage persistence/capacity,
and credential presence (never printed). Establish a writer exclusion/fence for C,
an authorized inspection identity, the exact candidate identity and its visibility
proof, a reverse-switch rehearsal on fixtures, and the retention hold. Every item
must be PASS; UNKNOWN is NO-GO.

Source precondition: SHA-256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`,
4 550 267 bytes, 284 physical pages. Rehash the input immediately before ingestion
**and** before activation. Mismatch → `BLOCK REINGEST`. Filename is not identity.

## Phase 1 — Snapshot current C

Follow `current-c-snapshot-contract.md`. Recapture immediately before building; do
not reuse this planning snapshot. Capture authoritative text/pages/chunks, region
metadata if present, all source/citation mappings, the **actual** Milvus float
vectors plus schema/index/model contract, manifests, manifests resource ownership
and the visibility state; hash/seal and independently verify readability. This
planning report retains vector **digests only**, not a restorable vector backup.
Freeze known-good / known-bad / partial-page query fixtures and their OLD results.
Capture all 284 physical pages, including the 16 presently empty pages, plus
adjacent non-C corpus fingerprints. Snapshot and queries must not alter the store.

## Phase 2 — Create isolated candidate

Only after prerequisite PASS and an explicit execution authorization. Admission must
be an explicit, audited, tenant-scoped operation that creates the candidate under
the model chosen by the prerequisite (A or B) and records OLD/NEW identity, run,
job, attempt, manifest, text ids, expected collection and the reconciliation seal.

Hard rules:

- The candidate must be **ingested, inspectable and reconcilable but NOT ACTIVE for
  normal retrieval** until cutover. `CURRENT C visible = YES` and
  `NEW C visible to normal users = NO` at every instant before cutover.
- If the candidate shares the physical document row (model B), its pages/chunks/
  vectors must carry the candidate generation identity and every reader must filter
  by the active generation. If it uses a separate row (model A), the same-source
  uniqueness constraint must already have been migrated away under the reviewed
  plan.
- The candidate must not hijack the source viewer: `get_page_publication` must
  resolve the **active** generation, not "latest completed run".
- Assert active-generation cardinality = 1 at every step. Assert OLD chunks/vectors
  are untouched (content digests equal to the Phase 1 snapshot).
- No overwrite-first, no delete-first, no reuse of the OLD document id, no change of
  the PDF, hash, tenant, title or scope to evade any guard.

## Phase 3 — Candidate ingestion

Use the regional publication pipeline with unchanged semantics
(`modules/library/region_publication.py`, `region-publication-v1`):

- Only **ACCEPTED + CERTIFIED** regions reach canonical text, chunks, embeddings,
  vectors and textual citations.
- `NOT ACCEPTED / UNRESOLVED / QUARANTINED` regions produce **0** searchable text,
  **0** chunks, **0** embeddings, **0** vectors, **0** textual retrieval and **0**
  textual citations, while the visual source stays preserved and resolvable.
- Region boundaries reset chunk overlap: no quote may span a quarantined gap.
- The original PDF is preserved (hash-checked) for **every** physical page, accepted
  or not, before any searchable activation.

Mandatory counters (observability, §45 of the gate brief) per attempt / page /
stage, persisted as structured diagnostics so a failure point is always
identifiable: `pages_processed` (expected 284), `regions_accepted`,
`regions_quarantined` (with reason codes), `pages_full`, `pages_partial`,
`pages_unusable`, `pages_empty`, `chunks_emitted`, `embedding_requests`,
`embeddings_generated`, `vectors_inserted`, `vectors_reconciled`, `errors`,
`retries`, `source_sha256`, `durable_source_path`, `heartbeat`.

Failure behaviour: OLD remains unchanged and active; the candidate remains
inactive and failed/incomplete; compensation is candidate-only and only after safe
ownership is proven; CURRENT is never auto-cleaned. Replay with identical approved
inputs must yield the identical candidate identity and PK set — no duplicate
chunks, no duplicate vectors, no extra active generation. Changed inputs require a
newly approved generation, never a silent replay over existing canonical text.

## Phase 4 — Candidate reconciliation

Produce `region-reconciliation.json`, `page-reconciliation.json` and
`document-reconciliation.json` under the future execution report, following
`C_RECONCILIATION_CONTRACT.md`. Every removed OLD evidence span must be explained
against a non-publishable NEW source region. Known good and good neighbours must be
preserved. Every unmatched or ambiguous mapping blocks approval: absence of OLD
region metadata is **not** evidence of quarantine. Coverage is exhaustive over all
284 pages, never sampled. Candidate failure → no cutover; OLD stays authoritative.

## Phase 5 — Retrieval/citation verification

Run the sealed A (known good), B (quarantined) and C (partial page) query groups
against the OLD baseline and the isolated candidate, on every retrieval surface
(lexical, hybrid/vector, research, relation, Book QA, page publication). Verify
citation page/source correctness, tenant authorization, and that normal users
cannot see the candidate. Query embeddings/model calls require separate execution
approval and never occur in this planning gate. Reconcile primary keys and
content/model/source metadata exactly. Active duplicate evidence = 0; no
cross-generation results.

## Phase 6 — Cutover

Require signed ingestion, reconciliation, retrieval and citation seals plus a
**separate** cutover GO. Use only the prerequisite-provided reversible atomic PG
visibility operation: lock the expected OLD/NEW, compare seals, flip exactly one
active generation, audit, advance the visibility epoch, commit once. Readers pin
one committed visibility epoch; cached or in-flight results cannot splice
generations. No sequential independent activate/deactivate requests. All vectors
already exist: **cutover is a visibility switch — no ingestion, no embedding, no
deletion**. A lost response is resolved by reading the transaction/audit state, never
by blind replay. See `cutover-design.md`.

## Phase 7 — Post-cutover validation

Immediately execute `post-cutover-validation-plan.md` as normal authorized users on
all retrieval surfaces. Normal retrieval must reach only NEW for logical C;
known-good, neighbour and partial-page cases must pass; bad evidence must stay
absent; citations must point to NEW; the visual source must resolve; OLD results
must not leak; no duplicate evidence. Any listed critical failure → mandatory
reverse switch. No cleanup while investigating.

## Phase 8 — Stabilization

OLD rows, chunks, pages, vectors, source, embedding records and manifests remain
intact but invisible. Guard against TTL, generic cleanup and background workers.
Observe critical-query regression, leakage and source health. The stabilization
duration is **not invented here**: the owner must approve a retention/stabilization
policy. The hold stays open until post-cutover validation, the stability review and
an explicit rollback-window closure are signed. No automatic physical expiry.

## Phase 9 — eventual old-generation cleanup

A separate authorized gate, after stabilization and rollback-window closure. Exact
OLD resource manifest, dependency/reference audit, backup/restore verification and a
dry-run of the selection. Never combined with cutover. **Never** delete by source
SHA, scope, collection or title — OLD and NEW share all of them; deletion must be by
exact resource manifest. After physical cleanup the instant rollback guarantee no
longer applies; disaster restore is a separate procedure. This planning gate
executes none of phases 1–9.

## Dry-run capability

`extract_pdf_region_published(path, language)` → `PublishedPage` and
`publish_certified_page` are pure and can run in memory without gateway, store or
model calls. There is **no** end-to-end worker `--dry-run` that guarantees no
writes: `ConcretePageFirstPipeline.run` persists pages/chunks and dispatches
embeddings. A strictly pure offline publication preflight over all 284 pages is
valuable and should be implemented in the prerequisite as a sealed harness, but a
worker dry-run must never be described as safe. No full-C extraction was run in this
planning gate.
