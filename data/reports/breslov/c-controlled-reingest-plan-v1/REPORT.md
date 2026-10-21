# C controlled reingest plan V1 — inventory and design

## Result

**TEBAAI_BRESLOV_C_CONTROLLED_REINGEST_PLAN_V1_PASS** — PLAN_READY=YES, PREREQUISITE_IMPLEMENTATION_REQUIRED=YES, READY_FOR_C_REINGEST_EXECUTION_GATE=NO, C_REINGEST_EXECUTED=NO.

Planning PASS establishes identity and deterministic safety prerequisites; it is not implementation readiness or authorization to migrate C. No production behavior changed. PostgreSQL/Milvus data writes, new worker jobs, document/chunk/vector modifications by this gate: **0**. No embedding or generative service calls, worker execution, reset, cleanup, cutover or source-preservation write occurred. All runtime database connections were local DEV read-only. Git remote precheck matched expected `49b1674674316b4696529b4491d5010552fd3ef4` on local, tracking ref and ls-remote.

## Exact current C

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
| manifest | `445e33ee-b352-5191-aa20-a13208695442` |
| text | `8be8899c-07e4-54b7-954f-d719ce217af4` |
| organization | `9b6406e1-66c1-49ae-80e0-0e4a6ccb324f` |
| workspace | `b4a32c1c-dcdc-486e-86e7-51714f9a45f4` |
| project | `2a95333c-fe1c-4f3d-83b8-5f2411ab0160` |
| scope / legacy collection | breslov_primary / breslov |
| Milvus collection | tebaai_breslov_chunks_v1 (2146 live total, C 942) |
| chunks / embeddings / vectors | 942 / 942 / 942, exact PK/chunk/content/source/page/dimension mappings verified |
| visibility | ready; sole live C document + sole C ingestion run, no active-run pointer |
| citation identity | document/chunk/editorial entity, evidence ID v2 derived from chunk+entity, physical page |
| durable source today | **NO**: source_path/source_uri NULL, deterministic durable file absent |
| original source available | **YES**: 4550267-byte PDF readable, exact approved SHA, 284 pages |
| persisted regional status OLD | none; legacy page metadata, not retroactive FULL/ACCEPTED |

Do not conflate filesystem original availability with working authenticated source viewer. No current-C browser/source API success is claimed; NULL source reference proves a prerequisite gap. The newer worker has durable preservation implemented, but it did not retroactively populate OLD. This does not make source identity ambiguous: external original matches PG and historical source manifests exactly.

## History and anomalous runs

Live PG has one C run, no hidden/failed/cancelled C runs, one active generation. Current C chunks carry the exact job/attempt; pages carry run_id, manifest links both, embeddings/vectors match. No orphan chunks/pages in queried live tables or orphan vectors in loaded TebaAI collections. Raw snapshots and mappings permit independent audit, not counts alone.

Archived reports identify:

- Page-first `132a791a-d12b-45bc-9b34-dd143605de12`, run `a5220a7c-11f8-40ac-a1fd-0ca6732f0508`, completed, 284 pages, 268 chunks/vectors, test_candidate historically; absent after later DEV reset.
- Earlier same-source documents `37b5842d-517d-49d1-bab0-3584f409f355` (268 structural nodes, 0 chunks) and `47768aac-704e-4296-9649-53b9ea037096` (2652 chunks, 2222 embedding tracking rows, 0 Milvus vectors reported), removed in the July 30 historical purge. The backup had zero ingestion-run rows for them: run IDs/timestamps cannot honestly be reconstructed; recorded null, not invented. This plan does not repeat that delete-first strategy.
- 19 cleaned regional E2E jobs retain now-absent document IDs, with completed cleanup manifests; these include subset-source and synthetic case C fixtures, not full-C generations. Do not mistake glyph/text runs (671 visibility runs) for ingestion runs.

Historical incompleteness does not obscure current authority; source/hash/current job/run/PK sets are unambiguous. Related titles with different source hashes are not generations of C. historical-report-index.json records report search scope; current-c-run-inventory.json and current-c-historical-anomalies.json distinguish current facts, archived observations and unrecoverable historical IDs.

One unloaded bm25 test collection reports stats row_count=0; no load/flush was performed and no Strong live-empty proof is asserted for that collection. Loaded collections were fully enumerated, including primary and E2E; execution preflight must resolve any residual cross-collection attribution uncertainty. No access failure was encountered for required current C data.

## Capability conclusion

See generation-capability-matrix.json. Identity EXISTS; parallel inactive generation, retention, rollback, source durability, chunk/vector isolation and regional reconciliation are PARTIAL; unified normal-retrieval isolation and atomic OLD/NEW switch are MISSING. Source durability exists in the new pipeline but not OLD data. No parallel versioning model is introduced: reuse separate document UUIDs from approved pipeline_version, existing runs/jobs/manifests and document statuses.

Specific blockers:

- MISSING_CONTROLLED_SAME_SOURCE_NEW_VERSION_ADMISSION (ordinary upload rejects exact source duplicate).
- MISSING_UNIFIED_ACTIVE_GENERATION_VISIBILITY (status-only isolation is false for text_search/hybrid; research candidate opt-in can expose candidates).
- MISSING_ATOMIC_ACTIVE_GENERATION_SWITCH (and audited atomic reverse, request/cache coherence).
- MISSING_GENERATION_SAFE_RETRY_AND_CLEANUP (current manifests do not establish safe preexisting-resource ownership on collision).
- CURRENT_C_DURABLE_SOURCE_REFERENCE_MISSING (repair OLD and verify storage lifecycle in a separate authorized prerequisite).

Recommend **TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1**, not full reingestion yet. Prerequisite includes actual reconciliation tooling and fault/retry/reverse tests, no current-C ingestion side effects.

## Planned strategy and invariants

CURRENT remains active -> separate NEW document/version (inactive) -> regional pipeline -> exhaustive region/page/document reconciliation -> retrieval/citation checks -> separate GO -> atomic visibility switch -> immediate verification -> stabilization with OLD retained -> eventual separate cleanup. NO DELETE-FIRST / NO OVERWRITE-FIRST. Never both generations normal-visible for the same logical evidence. No reembedding at cutover or rollback.

Expected quarantine removals are explicitly distinguished from unexpected good-content loss/gain. Reconciliation checks pages, regions, accepted/quarantined status, partial/unusable pages, chunks/vectors, source/page lineage, retrieval, citations and visual availability. Allowed unexpected losses/gains, bad searchable leaks, neighbor loss, missing pages, source unavailable, active duplicate evidence and cross-generation contamination: **0**. OLD/NEW chunk/vector count equality is not a criterion. Rollback is conceptually possible with retained OLD, but not an available production operation until prerequisite PASS.

## Validation and limitations

See focused-tests.txt, secret-scan.json, final-validation.json and git-diff-check.txt. Offline tests validate report consistency/read-only helper safety and existing publication-consumer contracts, not full-C extraction/retrieval quality. First safety test attempt falsely flagged Python sys.path.insert as a store insertion; test corrected narrowly and initial failure retained in focused-tests-initial.txt. No runtime mutation resulted.

Planning inventories capture ordered content hashes before/after and Strong Milvus record/vector digests. They demonstrate unchanged inspected data; connection-level read-only plus query/method audit establishes this agent's zero-write behavior. They are not a global audit of unrelated concurrent processes or a full restorable backup. Vector reports contain digests, not actual float exports. Tests/models/source viewer/full-C publication dry-run were not executed against external services; future contracts explicitly require them.

Preexisting dirty worktree preserved, not staged or included. In particular uncommitted extractor/font/reconstruction dependencies mean the docs commit alone cannot reproduce their future runtime behavior; freeze/approve those separately before execution. No LAT/runtime status file was changed, so lat check/frontend build/backend full suite are not applicable to this report-only gate. Production ingestion code unchanged.
