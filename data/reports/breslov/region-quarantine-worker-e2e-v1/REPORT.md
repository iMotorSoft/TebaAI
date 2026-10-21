# REGION QUARANTINE WORKER E2E V1 — FAIL

Branch: `feature/console-backend-core`.
Initial local/remote HEAD: `704ae24597e916b56ddec8a71fd0a30d34793aab`.

## Result

**TEBAAI_BRESLOV_REGION_QUARANTINE_WORKER_E2E_V1_FAIL**.

Infrastructure was available. The actual worker enforced regional publication safely and original PDFs remained accessible after completion. This is nonetheless a valid functional FAIL against the frozen five controlled PDF expectations, not BLOCKED or INVALID: A/C/D lost four expected GOOD regions because the unchanged certifier marked their simple synthetic layouts UNRESOLVED. No expected labels were changed, no ACCEPTED bypass was introduced, and certification/lineage/evaluator were not redesigned or edited.

The original five declared-certificate fixtures pass consumer/worker unit integration. That does not establish that the real PDF extractor will produce ACCEPTED certificates for arbitrary simple layouts. The PDF-level expectation failure is retained explicitly in `region-publication-results.json` and cannot be erased by the successful unit results.

## Final actual-worker run

| Case | Expected accepted units | Actual accepted/chunks/embeddings/vectors | Visual original | Result |
|---|---:|---:|---|---|
| A GOOD only | 1 | 0/0/0/0 | available | FAIL |
| B BAD only | 0 | 0/0/0/0 | available | PASS |
| C GOOD / BAD / GOOD | 2 | 0/0/0/0 | available | FAIL |
| D BAD / GOOD / BAD | 1 | 0/0/0/0 | available | FAIL |
| E all BAD | 0 | 0/0/0/0 | available | PASS |
| Real original p54–56 | Existing 3 ACCEPTED+CERTIFIED | 3/3/3/3 | available | regional enforcement PASS |

Across the six jobs: 43 quarantined metadata records, zero rejected-region chunks/embedding inputs/vectors/textual retrieval hits/textual citations. Quarantined raw text was excluded before canonical persistence. Every page retained source/page/region/bbox, explicit reasons, quality/provenance/publication status and candidate hash. No late vector deletion was used to enforce quarantine.

Real isolated physical pages 1/2/3 correspond to original p54/p55/p56. All three remain PARTIAL and their accepted notes are searchable. On isolated p2/original p55, unreliable regions include explicit INVALID_UNICODE_REPLACEMENT reasons, and an accepted neighboring unit remains indexed. No claim is made about original p167/p168 or p187/p416 in this gate.

Accepted regions: three successful phrase queries, three hybrid queries each returning real vector signals, and three citations built through existing canonical PG rehydration and `build_evidence_v1`, with region/source/publication references. Quarantined candidates were queried through the authenticated real `/library/search` path. No downstream records were inserted manually.

The existing phrase API applies accent normalization asymmetrically. Full raw accented probes missed in attempt-2. Final query selection uses the longest ASCII substring of accepted content, declared before the final execution; retrieval normalization, Hebrew tuning and expected labels were not changed. Both failed probes and subsequent successful probes are retained.

## Durable visual source

Existing configured local storage was reused; no second storage service or migration was added. Atomic, fsynced, hash-checked source copy precedes finalization/upload deletion. `library_documents.source_path` remains internal. Scope-authorized full-PDF responses return the exact fixture SHA-256 and expected physical page count after worker completion; anonymous access is 401. Page publication metadata exposes only protected references, not filesystem paths or rejected text. Unit regressions cover cross-scope 403 and arbitrary-path 404.

This proves authenticated backend access to a full original PDF plus page/bbox metadata, not browser rendering or a new frontend viewer. Existing token storage requires an authenticated fetch; bare unauthenticated URLs do not work by design. Generative QA rendering was not executed: citation validation exercised the actual canonical citation builder and source handlers.

## Idempotency, failure and cleanup

Each final upload/job was submitted twice through normal job creation. The same job returned; duplicate targeted delivery found the completed job unclaimable. Canonical page/chunk/vector identities did not duplicate. Crash/restart retry was not claimed as real E2E.

Unexpected publication exceptions were fault-injected in deterministic tests through the actual worker orchestrator and pipeline with FakeStore/FakeGateway: explicit failed transition, no persistence, embeddings, vectors or fallback. This failure job was not injected into real PostgreSQL. The real E2E never monkeypatched certification, extraction, publication or downstream adapters.

Normal manifest cleanup was run twice per final job. Controlled documents, pages, chunks, embeddings, vectors and durable PDFs were removed. Normal upload/job/attempt/cleanup audit rows intentionally remain with exact IDs in the report. All previous attempts were similarly cleaned. Before/after/after-cleanup fingerprints of all preexisting documents/texts/pages/chunks/embeddings and full Milvus rows (including vectors) match: 3 real documents, 896 pages, 2146 chunks/embeddings/vectors unchanged.

## Validation

- Focused: **248 PASS**.
- Full backend before: **1911 PASS / 20 failures**.
- Full backend final: **1926 PASS / same 20 failing node IDs / 0 new failures**.
- Four added Litestar inferred-path deprecation warnings are non-failing; existing token-length warnings were observed, without exposing/changing secrets.
- The suite ran in the preserved dirty worktree, including prior untracked tests. Not every historical experiment/evaluator test is included in this gate's staging allowlist; do not interpret the local count as the count of a clean remote checkout.
- Initial integration had three compatibility extraction regressions. Fixed by making the worker's regional extractor explicit and mandatory while keeping the legacy standalone API unchanged. Tests were not weakened; gateway rejection prevents that API from bypassing regional enforcement in the real worker.
- Diff/secret/final git evidence: corresponding files in this directory. Raw pytest console logs retain whitespace in assertion diff excerpts; report-local `.gitattributes` exempts only these three generated logs from blank-at-eol diagnostics. Authored code, tests and documentation remain fully checked.

## Readiness and impact

REGION_LEVEL_QUARANTINE_READY = NO.
WORKER_REGION_ENFORCEMENT_READY = NO (full gate not met; actual regional enforcement works for certified units).
DURABLE_VISUAL_SOURCE_READY = YES (backend full-PDF/page access).
FULL_C_REINGEST_READY = NO.

Production untouched; no full corpus/C reingest, service restart, migration, PR, tag, release, merge or deployment. Do not activate this failed gate as an unconditional ingestion-readiness claim.

See `architecture-decision.md` for implementation choices and unchanged necessary prior V5 dependencies, and `recommendation.md` for next steps. Commits/push are authorized by the user for a methodologically valid FAIL; see separate git-close evidence for actual SHAs and remote verification.
