# C controlled reingest plan V1 — inventory and design (refresh 2026-10-22)

## Result

**TEBAAI_BRESLOV_C_CONTROLLED_REINGEST_PLAN_V1_PASS** — PLAN_READY=YES,
PREREQUISITE_IMPLEMENTATION_REQUIRED=YES, READY_FOR_C_REINGEST_EXECUTION_GATE=NO,
C_REINGEST_EXECUTED=NO.

Planning PASS establishes identity and deterministic safety prerequisites; it is not
implementation readiness nor authorization to migrate C. No production behavior
changed. PostgreSQL/Milvus data writes, new worker jobs, document/chunk/vector
modifications by this gate: **0**. No embedding or generative service calls, worker
execution, reset, cleanup, cutover or source-preservation write occurred. All
runtime database connections were local DEV read-only.

This is the **second execution** of the planning gate. The first (commit `490be67`,
2026-10-21) produced the identity, the plan, the reconciliation contract, the
rollback runbook and the capability matrix. Between then and now two prerequisite
attempts were made and both closed **BLOCKED**
(`TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1_BLOCKED`,
`TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V1_BLOCKED`). This refresh
re-observes current C read-only, keeps every still-valid conclusion, and folds in the
two structural findings that the blocked attempts produced.

## Exact current C (re-observed 2026-10-22, read-only)

| Field | Observed DEV value |
|---|---|
| document | `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa` |
| logical identity/title | Likutey Halajot — Interior Final; same approved PDF, not LM II 8 Rosenberg or LM II BRI |
| stored filename | `LIKUTEY HALAJOT Interior Final.pdf` |
| external original | `/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf` |
| SHA256 | `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a` |
| physical pages | 284 (268 nonempty, 16 empty) |
| active run | `6c1a19b8-b60b-52de-b709-5496f4c6e937`, completed, content_page_first_v1 |
| job / attempt | `cf9b886c-bd8d-4514-97d4-0fee3e0fb8ed` / 1 |
| manifest / canonical text | `445e33ee-b352-5191-aa20-a13208695442` / `8be8899c-07e4-54b7-954f-d719ce217af4` |
| organization | `9b6406e1-66c1-49ae-80e0-0e4a6ccb324f` |
| workspace | `b4a32c1c-dcdc-486e-86e7-51714f9a45f4` |
| project | `2a95333c-fe1c-4f3d-83b8-5f2411ab0160` |
| scope / legacy collection | breslov_primary / breslov |
| Milvus collection | tebaai_breslov_chunks_v1 (2146 live total, C 942) |
| chunks / embeddings / vectors | 942 / 942 / 942, exact PK/chunk/content/source/page/dimension mappings verified, 0 missing / 0 extra / 0 mismatches / 0 duplicates / 0 orphans |
| visibility | ready; sole live C document + sole C ingestion run, **no active-run pointer** |
| citation identity | document/chunk/editorial entity, evidence ID v2 derived from chunk+entity, physical page |
| durable source today | **NO**: source_path/source_uri NULL, deterministic durable file absent |
| original source available | **YES**: 4 550 267-byte PDF readable, exact approved SHA, 284 pages |
| persisted regional status OLD | none; legacy page metadata, not retroactive FULL/ACCEPTED |

**C is unchanged between the two plan runs.** Content digests for documents, pages,
chunks, embeddings and runs are identical to the 2026-10-21 snapshot, and the
before/after captures of this run differ only in their timestamps. Do not confuse
filesystem original availability with working authenticated source viewer. No
current-C browser/source API success is claimed; the NULL source reference proves a
prerequisite gap. The newer worker has durable preservation implemented, but it did
not retroactively populate OLD. This does not make source identity ambiguous: the
external original matches PostgreSQL and the historical source manifests exactly.

## History and anomalous runs

Live PostgreSQL has one C run, no hidden/failed/cancelled C runs, one active
generation. Current C chunks carry the exact job/attempt; pages carry run_id, the
manifest links both, embeddings/vectors match. No orphan chunks/pages in the
queried live tables and no orphan vectors in loaded TebaAI collections.

Archived reports identify:

- Page-first `132a791a-d12b-45bc-9b34-dd143605de12`, run `a5220a7c-11f8-40ac-a1fd-0ca6732f0508`, completed, 284 pages, 268 chunks/vectors, `test_candidate` historically; absent after the later DEV reset.
- Earlier same-source documents `37b5842d-517d-49d1-bab0-3584f409f355` (268 structural nodes, 0 chunks) and `47768aac-704e-4296-9649-53b9ea037096` (2652 chunks, 2222 embedding tracking rows, 0 Milvus vectors reported), removed in the 2026-07-30 historical purge. The backup had zero ingestion-run rows for them: run IDs/timestamps cannot honestly be reconstructed and are recorded as null, not invented. This plan does not repeat that delete-first strategy.
- 19 cleaned regional E2E jobs retain now-absent document IDs with completed cleanup manifests; they include subset-source and synthetic case-C fixtures, not full-C generations. Do not mistake the 671 glyph/text visibility runs for ingestion runs.

Historical incompleteness does not obscure current authority; source hash, current
job/run and PK sets are unambiguous. Related titles with different source hashes are
not generations of C. `current-c-run-inventory.json` and
`current-c-historical-anomalies.json` distinguish current facts, archived
observations and unrecoverable historical IDs.

One unloaded bm25 test collection reports stats `row_count=0`; no load/flush was
performed and no Strong live-empty proof is asserted for it. Loaded collections were
fully enumerated, including primary and E2E. The execution preflight must resolve any
residual cross-collection attribution uncertainty. No access failure was encountered
for required current C data.

## Refresh deltas — what the blocked prerequisite attempts changed

1. **The "second physical document" candidate is blocked by live schema.**
   `uq_library_documents_scope_collection_sha256 (knowledge_scope_id, collection_id, source_sha256)`
   is present in DEV (re-probed read-only in `indexes-readonly.json`). No pipeline
   version, UUID or idempotency trick admits a second same-source document row in
   the same scope/collection. The first plan run's assumption is falsified; the plan
   now enumerates three admission models and marks the old one inadmissible.
2. **A completed candidate run hijacks the source viewer.**
   `source_repository.get_page_publication` picks the newest `completed` run of a
   document. A candidate that completes before cutover replaces OLD's published
   region metadata — a concrete isolation defect that the prerequisite must close.
3. **No unified active-generation predicate exists.** `text_search.py` and
   `hybrid_search.py` have no generation/status filter; research and relation
   repositories filter by ad-hoc status allow-lists; the source API accepts
   `ready` and `test_candidate`. Retrieval, citation and viewer disagree about which
   generation is visible.
4. **Defensive patches are present but are not generation primitives.** The
   page-first INSERT-collision guard, the cleanup status preflight and the hybrid
   hydration hardening reduce damage; they provide no isolation, no active pointer,
   no atomic switch, no rollback and no retry/cleanup ownership proof.

## Capability conclusion

See `generation-capability-matrix.json`. Identity EXISTS; region-level status
EXISTS; parallel inactive generation, generation identity, old-generation retention,
rollback, source durability, chunk/vector generation isolation, citation generation
identity and generation-safe retry/cleanup are PARTIAL; the active-generation
pointer, unified visibility, page-publication isolation, controlled same-source
admission, the atomic switch and the reconciliation harness are MISSING. Source
durability exists in the new pipeline but not in OLD data. No parallel versioning
model is introduced here: reuse the safest existing abstractions and let the
prerequisite decide between logical identity + generation rows and generation-scoped
chunks inside one document row.

Blocking gaps:

- MISSING_LOGICAL_IDENTITY_AND_ACTIVE_GENERATION_POINTER
- MISSING_SAME_SOURCE_GENERATION_ADMISSION_UNDER_LIVE_UNIQUENESS_INDEX
- MISSING_UNIFIED_ACTIVE_GENERATION_VISIBILITY
- MISSING_PAGE_PUBLICATION_GENERATION_ISOLATION
- MISSING_ATOMIC_ACTIVE_GENERATION_SWITCH
- MISSING_GENERATION_SAFE_RETRY_AND_CLEANUP
- MISSING_RECONCILIATION_HARNESS
- CURRENT_C_DURABLE_SOURCE_REFERENCE_MISSING

Recommend **TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1**, not full reingestion
yet. The prerequisite must include the actual reconciliation tooling, the
fault/retry/reverse tests and the generation-identity decision, with no current-C
ingestion side effects.

## Planned strategy and invariants

CURRENT remains active → separate NEW generation (inactive) → regional pipeline →
exhaustive region/page/document reconciliation → retrieval/citation checks →
separate GO → atomic visibility switch → immediate verification → stabilization
with OLD retained → eventual separate cleanup. NO DELETE-FIRST /
NO OVERWRITE-FIRST. Never both generations normal-visible for the same logical
evidence. No reembedding at cutover or rollback.

Expected quarantine removals are explicitly distinguished from unexpected
good-content loss/gain. Reconciliation checks pages, regions, accepted/quarantined
status, partial/unusable pages, chunks/vectors, source/page lineage, retrieval,
citations and visual availability. Allowed unexpected losses/gains, bad searchable
leaks, good-neighbor loss, missing pages, source unavailable, active duplicate
evidence and cross-generation contamination: **0**. OLD/NEW chunk/vector count
equality is not a criterion. Rollback is conceptually possible with retained OLD,
but is not an available production operation until the prerequisite passes.

## Validation and limitations

See `focused-tests.txt`, `secret-scan.json`, `final-validation.json` and
`git-diff-check.txt`. Offline tests validate report consistency, read-only helper
safety and the existing publication-consumer contracts, not full-C
extraction/retrieval quality. Planning inventories capture ordered content hashes
before/after and Strong Milvus record/vector digests. They demonstrate unchanged
inspected data; connection-level read-only plus a query/method audit establishes
this agent's zero-write behaviour. They are not a global audit of unrelated
concurrent processes, nor a full restorable backup. Vector reports contain digests,
not actual float exports. Tests/models/source viewer/full-C publication dry-run were
not executed against external services; the future contracts explicitly require them.

The pre-existing dirty worktree was preserved, not staged or included. In
particular, the uncommitted extractor/font/reconstruction/visibility dependencies
mean this documentation commit alone cannot reproduce their future runtime
behaviour; freeze and approve them separately before execution. No LAT/runtime
status file was changed, so `lat check` / frontend build / full backend suite are
not applicable to this report-only gate. Production ingestion code unchanged.

## Git

Branch `feature/console-backend-core`. The brief expected HEAD
`49b1674674316b4696529b4491d5010552fd3ef4`; the remote now points at
`490be6748fdb90ad644b9a6296faa5d1c33ea4e1`, which is the **previous execution of
this same gate** (commit `docs(breslov): plan controlled C reingestion`). Local ==
tracking == ls-remote, so there is no divergence and publication remains a
fast-forward; an unrelated remote movement would have blocked the push. No merge,
rebase, force, reset, clean, stash or checkout was performed.
