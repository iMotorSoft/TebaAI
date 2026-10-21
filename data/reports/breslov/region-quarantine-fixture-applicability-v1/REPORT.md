# Region quarantine fixture applicability V1 — PASS

**TEBAAI_BRESLOV_REGION_QUARANTINE_FIXTURE_APPLICABILITY_V1_PASS**

Branch: `feature/console-backend-core`. Initial local/origin/ls-remote:
`1103948c462aceac3bf38100958ac091649c8f8c`.

## Prior gate remains FAIL

PREVIOUS_GATE_REINTERPRETED = NO. PREVIOUS_GATE_REMAINS = FAIL.
Its frozen expectations were not met. Its report/results/labels/raw evidence
remain byte-identical. This gate answers a narrower responsibility question:
A/C/D author-intended GOOD labels were inappropriate as worker-only publishing
obligations because the upstream certifier never authorized those regions.
The worker must obey certificates, not compensate for certifier recall.

| Case | Author intended GOOD | Actual ACCEPTED+CERTIFIED | Actual UNRESOLVED (all regions) | Worker published from accepted | Worker dropped from accepted | Published from unresolved |
|---|---:|---:|---:|---:|---:|---:|
| A | 1 | 0 | 1 | 0 | 0 | 0 |
| C | 2 | 0 | 3 | 0 | 0 | 0 |
| D | 1 | 0 | 3 | 0 | 0 | 0 |

Exact inputs/texts, original fixture hashes, intended labels, actual region IDs,
bboxes, candidate hashes, quality/provenance and publication decisions are in
`previous-fixture-reconstruction.json`. Each A/C/D region is QUARANTINED and
NOT_SEARCHABLE. No certifier was rerun or investigated.

CERTIFIER_RECALL_MISS = 4 (intent-relative mismatch, not a determination that
those sources should have been certified).
WORKER_GOOD_NEIGHBOR_LOSS = 0. WORKER_BAD_REGION_LEAK = 0.

## Corrected contracts

`responsibility-contract.md` and `metric-contract.json` define two fixture types:
preclassified policy/worker fixtures vs full-pipeline source fixtures.
GOOD_NEIGHBOR_LOSS counts distinct boundary ACCEPTED+CERTIFIED region IDs lost
at any required downstream stage, never intended GOOD that arrived UNRESOLVED.

The new tests execute actual ContentManagerWorker → ConcretePageFirstPipeline,
publication policy, publication validation and production region chunk builder.
Upstream certificates and persistence/embedding/vector I/O alone are doubles.
Mixed accepted/quarantined/accepted preserves 2/2; all-good preserves 3/3;
all-bad publishes zero, with no false good-neighbor loss. ACCEPTED without
CERTIFIED is also excluded. Checks cover canonical, chunk, embedding input,
embedding record and vector region-ID sets; equal aggregate counts cannot hide
substitution. Existing source-copy and authenticated source-route tests pass.

Negative controls detect accepted loss at each required stage, bad publication,
equal-count good/bad substitution, and missing quarantined visual source.
`metric-negative-controls.json` records actual metric observations: deliberate
worker loss = 1, deliberate bad publication = 1, missing visual source = 1.
Production is never mutated. No fresh actual retrieval/citation claim is made
from the I/O doubles.

## Real Breslov product evidence retained

Frozen prior actual-worker E2E, original physical pages 54/55/56:

| Property | Result |
|---|---:|
| ACCEPTED+CERTIFIED regions | 3 |
| Survived chunks | 3 |
| Survived embeddings | 3 |
| Survived vectors | 3 |
| Survived retrieval | 3 |
| Survived canonical citations | 3 |
| REAL_ACCEPTED_LOSS | 0 |
| BAD_HEBREW_CHUNKS | 0 |
| BAD_HEBREW_EMBEDDINGS | 0 |
| BAD_HEBREW_VECTORS | 0 |
| BAD_HEBREW_RETRIEVAL_HITS | 0 |
| BAD_HEBREW_TEXTUAL_CITATIONS | 0 |

BAD_HEBREW_VISUAL_SOURCE_AVAILABLE = YES (verified during prior E2E before
authorized cleanup, not claimed currently stored). All three real pages had an
accepted searchable region and quarantined neighbors: REAL_PARTIAL_PAGE_SEARCHABLE
= YES. Whole document rejection from one bad region = NO.

Frozen real evidence is independently asserted by the new harness: accepted
region IDs match phrase-query probes, hybrid-query probes and actual citations.
Sources: prior `real-source-case.json`, `worker-integration-results.json`,
`chunk-results.json`, `embedding-results.json`, `vector-results.json`,
`retrieval-results.json`, `citation-results.json`, `partial-page-results.json`
and `source-preservation-results.json`. No source truth was changed.

Limits preserved: authenticated backend full PDF/page/bbox access, not browser
viewer certification; canonical citation builder, not generative answer E2E;
three physical pages, not full C quality. No reingest, PG/Milvus gate writes,
service restart, configuration change or migration.

## Freeze and validation

Contracts, fixtures, metric code, harness, expected synthetic analysis and test
helper dependencies were SHA-256 frozen before execution. All hashes remain
identical. No expected labels, metrics or harness were edited after results.
An initial invocation named a nonexistent route-test file and ran zero tests;
its output is retained in `focused-collection-not-run.txt`. Only the invocation
was corrected before the single actual focused final battery.

- Focused final battery: **57 PASS / 0 failures**.
- Full backend: **1947 PASS / same 20 known failures / 0 new failures**;
  exact node-ID comparison in `baseline-failure-comparison.json`.
- Prior full baseline: 1926 PASS / 20 failures; 21 added passing tests.
- Counts include preserved preexisting untracked tests, not a clean checkout.
- All backend production Python and all previous gate files: identical before/
  after hashes. Existing dirty production changes are preexisting and untouched.
- Preexisting worktree hashes preserved; no unrelated staging.
- `git diff --check`: PASS. New-candidate secret scan: PASS.
- Report-local `.gitattributes` exempts only raw full-suite assertion excerpts
  from blank-at-eol checks; generated evidence remains unedited.

## Readiness

FIXTURE_APPLICABILITY_CORRECTED = YES.
PARTIAL_PAGE_SEARCHABLE = YES.
FULL_DOCUMENT_REJECTED_DUE_TO_SINGLE_BAD_REGION = NO.
REGION_LEVEL_QUARANTINE_READY = YES.
WORKER_REGION_ENFORCEMENT_READY = YES.
DURABLE_VISUAL_SOURCE_READY = YES (scoped backend contract).
FULL_C_REINGEST_READY = NO.

No product code changes. Next step: design a separately authorized controlled C
reingestion; do not execute it under this applicability gate.
