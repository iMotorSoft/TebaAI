# C parallel-generation safety V1

**TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1_BLOCKED**

`PARALLEL_GENERATION_SAFE=NO`; `READY_FOR_C_REINGEST_EXECUTION_GATE=NO`; **`C_REINGEST_EXECUTED=NO`**.

This gate made narrow defensive changes and reproduced real defects, but did **not** implement the requested complete generation infrastructure. It must not be used as approval to execute C or the next gate.

## Structural finding: stop before admitting NEW

The prior [plan](../c-controlled-reingest-plan-v1/README.md) prescribes separate document UUIDs per approved pipeline version, retaining the same source and scope. Inspection discovered an additional blocking invariant: migration 042's **live DEV** unique index on `(knowledge_scope_id, collection_id, source_sha256)` prevents the planned parallel NEW document even with a distinct UUID. See [live index evidence](schema-index-inventory.json), [probe result](indexes-probe.txt), [generation contract](generation-contract.md).

No duplicate check/index was dropped, no source hash changed and no scope/collection substituted to evade it. A safe implementation needs explicit reviewed schema evolution coordinated with logical identity, explicit active identity, readers, admission and retention—not an isolated duplicate-protection removal. No migration or backfill was performed. Unknown historical active identity must fail closed, not select latest.

## Problems reproduced and changes implemented

Before production edits: existing focused baseline **55 PASS**. Nine new deterministic cases failed on original production code; after the patch they pass. The final selected relevant suite is **260 PASS**, four warnings. Tests use fakes/synthetic data, not C writes.

1. `page_first_gateway.persist_document_and_pages`: `ON CONFLICT(id) DO NOTHING` previously continued and registered preexisting resources as owned by a new manifest. INSERT now returns its new ID; collision aborts before creating run/text/pages/manifest resources. This intentionally refuses unsafe resume, not a complete retry implementation.
2. `content_manager_cleanup`: published vectors could be removed before the final document DELETE noticed status `ready`. New status preflight rejects already-ready/archived/unknown documents before any cleanup side effect. **A concurrent publication/cleanup race and retained-generation hold are still unresolved.**
3. `hybrid_search`: missing PG hydration could still emit Milvus identity/title; mismatched document identity could be attributed incorrectly. Those hits are now discarded. Emitted identity/title/index use canonical PG fields, including index zero. A real HTTP handler + hybrid orchestration regression confirms missing-PG `NEW_ONLY_MARKER` is not serialized. This is not complete candidate isolation: valid inactive PG candidate rows are not filtered yet.

No second ingestion stack, vector abstraction, retrieval engine or permanent C-specific production logic was introduced.

## Active / candidate / cutover / rollback status

| Capability | Result |
|---|---|
| Parallel inactive generation | BLOCKED by live uniqueness; no candidate admitted |
| Generation identity | Existing document/run/job/attempt identity inventoried, active pointer absent |
| Candidate retrieval isolation | MISSING across all routes; hybrid hydration hardened only |
| Controlled cutover / stale-switch protection | NOT IMPLEMENTED / NOT DEMONSTRATED |
| Rollback without reingest | Required contract preserved, primitive NOT IMPLEMENTED |
| OLD retention after cutover | Required hold not implemented, no cutover executed |
| Retry / exact-generation cleanup | Partial defensive guards; concurrency/ownership proof missing |
| Source durability | **NOT RESOLVED for OLD C** |
| Current C content unchanged | **YES**, document metadata, runs/pages/text/chunks/embeddings and vector digests equal |

Active identity currently remains implicit: one ready C document plus one completed run. That observed state does not satisfy an explicit pointer or atomic single-active invariant. No candidate-only API was added. Normal literal, assistant/relation, Book QA, source and viewer paths still need common active/candidate/historical authorization and epoch consistency. [Implementation map](implementation-map.md) inventories their real paths/symbols/limitations.

Cutover must be one PG expected-OLD CAS transaction with shared lifecycle locking, source/reconciliation seals, audit, active identity/epoch and reader coherence. Milvus keeps both generations and is filtered by PG-selected document IDs, before top-k and on hydration. Rollback must reverse the same primitive without any model call or regeneration, preserving OLD and NEW physical data. Neither operation exists in this patch; do not replace them with two publication calls. [Cutover](cutover-contract.md), [rollback/retention](rollback-contract.md).

## Current C and source safety

- Document `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`.
- Sole observed completed run before/after: `6c1a19b8-b60b-52de-b709-5496f4c6e937`.
- One document generation, one run; chunks **942→942**, vectors **942→942**.
- Source exists, **4,550,267 bytes / 284 pages**, SHA256 matches `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.
- `source_path=NULL`, `source_uri=NULL`; deterministic durable copy absent. Original availability is **not** durability or viewer success. No source copied into Git, no source repair or source metadata write performed.
- Existing `durable_source.preserve_source` is the required reuse path for a continuation; storage persistence/backup/retention and authenticated access still need proof.

Service-connected probes are restricted to local DEV, server-enforced PG read-only, SELECT-only query wrappers and exact read-only Milvus methods. Static guard tests cover both probes. There is no mutating runner for this gate, so C is not merely a name-based exception to a generic writer. Before/after source and content fingerprints match. No worker, cleanup, retry, source extraction, embedding, cutover or generation activation ran. No production host/service/configuration was accessed or changed.

[Before inventory](before-inventory.json), [after inventory](after-inventory.json), [integrity comparison](integrity-verification.json), [source verification](source-verification.json). Raw sanitized PG/Milvus/query/source reports are retained beside summaries. Vector digests are integrity evidence, **not** restorable vector backups. No assertion about unrelated concurrent writers or unloaded collections is made.

## Retry / failure / reconciliation

The new collision guard protects preexisting generation ownership at the document INSERT. It does not supply sealed idempotent resume. Cleanup still lacks common publication locking and retained ownership, so interrupted/failed candidates are **not** certified invisible or cleanup-safe across all routes. [Retry/cleanup](retry-cleanup-contract.md).

Regional publication semantics remain generation-owned: ACCEPTED+CERTIFIED only, partial/unusable pages preserved, quarantined content nonsearchable. No real NEW regions were produced or reconciled. Required future counters remain zero unexpected losses/gains, bad searchable leaks, good-neighbor loss and active duplicate evidence. OLD/NEW chunk/vector counts need not match. The prior reconciliation contract was neither weakened nor replaced.

## Validation and evidence

- [A–L matrix and cross-route limits](test-matrix.md).
- [Final selected suite](test-results.txt): 260 PASS / 4 warnings; no unrelated failures in executed baseline or final selected suite.
- [Red reproduction](regressions-before.txt): 9 expected failures before fixes (not historical suite failures).
- [Commands](validation-commands.txt), [files](changed-files.txt), secret-scan.json and git-diff-check.txt.
- Full repository/service-dependent suite, real transaction concurrency, browser E2E, migration tests and real candidate retrieval: **NOT RUN / NOT CERTIFIED**. No silent fallback promoted a missing critical guarantee to PASS.
- No LAT/reference/frontend modifications; `lat check`, `pnpm check/build` not applicable. Existing extractor/font/reconstruction/UI/status/reset/report changes were preserved outside this gate's file scope.

## Git and continuation

Branch: `feature/console-backend-core`. **No commit/push**: the complete requested gate is blocked and not validated as safe. The narrow patch and evidence remain reviewable, with no unrelated files staged. No reset/stash/checkout/merge/rebase/force push occurred. HEAD/tracking/ls-remote observations are in git-close.json; equality alone does not mean publication occurred.

Next action is **continue this prerequisite**, not C ingestion: review schema/admission/active-identity migration, implement unified read visibility + request epochs, atomic/reversible CAS, shared cleanup/publication/retention fence, durable OLD source repair, and deterministic A–L/cross-route/PG concurrency tests on isolated stores. Preserve OLD throughout. Only a later successful prerequisite gate and explicit user authorization may open `TEBAAI_BRESLOV_C_CONTROLLED_REINGEST_EXECUTION_V1`.

**Next execution gate AUTHORIZED_NOW=NO; READY_TO_DESIGN_OR_EXECUTE_NEXT_GATE=NO.**
