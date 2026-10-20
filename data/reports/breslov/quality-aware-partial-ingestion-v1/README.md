# Quality-aware partial ingestion V1 — BLOCKED

## Verdict

`TEBAAI_BRESLOV_QUALITY_AWARE_PARTIAL_INGESTION_V1 = BLOCKED`

`TEBAAI_BRESLOV_QUALITY_AWARE_PARTIAL_INGESTION_OFFLINE_V1_PASS`: **NOT EMITTED**.
Contract implementation/tests pass; full requested offline goldens do not yet
pass. Phases B/integration and small real E2E NOT started, respecting their
prerequisite. This is not PASS_ARCHITECTURE_NOT_READY_FOR_C: no full offline
acceptance or integration was proved. Not FAIL_UNSAFE_INDEXING either: no new
corpus indexing occurred; existing corpus was not audited in this phase.

Required final verdict vocabulary:

```text
QUALITY_AWARE_PARTIAL_INGESTION_FAIL (gate incomplete / BLOCKED, not failing tests)
READY_FOR_C_REINGEST = NO
```

## Implemented, isolated offline

- `backend/modules/library/region_quality.py`: generic region-quality contract,
  fail-closed deterministic rejection, explicit positive verification, separate
  remediation, page/document aggregate, complete supplied-region metadata,
  accepted-only evidence units; quality_policy_version=region-quality-v1.
- Markdown numbered-note-start adapter retains original offsets and text;
  recovers both35/36 on the existing real canonical56 audit fixture.
- `backend/tests/test_region_quality.py`: synthetic contract + existing real
  goldens, encoding/script-independent rejection, no unsupported/OCR acceptance,
  source error vs insufficient evidence, idempotence, no gap-bridging chunks.

Paths above are relative to `SrvRestAstroLS_v1/`. Production pipeline unchanged.
A certificate-consuming contract is NOT a general automatic quality detector.
It does not prove all corrupt text detectable nor inventory complete.

## Real evidence, exact SHA

SHA-256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.
Source read-only; source not modified, font maps/visibility candidates not used.
Fresh PyMuPDF4LLM canonical output saved for55/56/167. Closed OCR/search studies
not reopened; earlier native/source diagnostics reused.

| Required page167 field | Result |
|---|---|
| physical page |167|
| printed page |149 (prior visual golden, not newly extracted metadata)|
| Spanish body |ACCEPTED, selected offline Markdown region|
| Spanish notes |PLATFORM_EXTRACTION_ERROR in CURRENT MARKDOWN; native columns reliable|
| Hebrew body |PLATFORM_EXTRACTION_ERROR|
| page aggregate |PARTIAL, supplied offline inventory|
| corrupt Hebrew indexed |NO new indexing; absent from candidate chunks|
| good Spanish indexed |YES offline body chunks; NO real PG/Milvus index run|

**Newly reproduced material blocker:** current Markdown emits continuation of65
and note66 before64 and65. Therefore native-good notes cannot be published as
current literal Markdown. Quarantine is not a permanent solution to that known
structure error. Header/transition/notes heading also contain U+FFFD; do not
silently suppress those artifacts or invoke white-overlay filtering.

Page55: current corrupt paragraph excluded by policy. Existing audit identifies
Cc→U+FFFD first divergence in raw layout. No region repair attempted; full
neighbor preservation not yet validated. Page56: SAFE_RECONNECT, starts35/36
recovered; complete body termination/anchors/roles/chunk citations **PARTIAL**,
not ACCEPTED or permanently quarantined merely to avoid the reconnect.
Source-error/unresolved fixtures are **synthetic only**, explicitly labeled.

## Safety counters and quality counts

[indexing-safety.json](indexing-safety.json): candidate-only counters:

```text
known_bad_text_indexed = 0
known_bad_text_embedded = 0
known_bad_text_citable = 0
good_text_lost_due_neighbor_failure = 0
quarantined_regions_untracked = 0
```

No real embeddings/citations/vector writes evaluated. These zeroes must NOT be
reported as a real worker or existing-corpus guarantee. Worker is NOT protected
by this new policy yet. Good167 notes are blocked by their OWN order defect,
not the neighboring Hebrew failure.

Sample matrix: accepted_regions=3, platform_extraction_errors=5,
source_pdf_errors=1, unresolved_regions=1; full_pages=1, partial_pages=2,
unusable_pages=2. These are selected sample-page inventories (including
synthetics), NOT counts for the full real PDF; E2E fixtures=0.

## Validation / reproduction

Run from `SrvRestAstroLS_v1/backend`:

```sh
uv run python ../../data/reports/breslov/quality-aware-partial-ingestion-v1/validate_offline.py
uv run pytest -q tests/test_region_quality.py tests/test_content_manager_*.py tests/test_page_first_*.py tests/test_editorial_*.py tests/test_simple_research_rag.py tests/test_canonical_editorial_evidence_selection.py tests/test_pdf_*.py tests/test_hebrew_lexical_normalizer.py tests/test_hebrew_pipeline_contract.py tests/test_hebrew_tex_decoder.py tests/test_likutey_moharan_ii_layout.py
```

**555 passed, 0 failed**. [tests.txt](tests.txt). Related backend suites rather
than unrelated full suite; no service connections. `git diff --check` PASS,
new-file whitespace checks PASS; final new files reviewed. LAT/@lat unchanged:
lat check not applicable. Frontend unchanged by this phase: no UI gate claimed.
Offline report generator repeated with identical hashes of all12 JSON artifacts
(including exact original Markdown strings; source whitespace preserved).

## Persistence / integration design

See [quality-contract.md](quality-contract.md), [region-policy.md](region-policy.md),
[page-aggregation.md](page-aggregation.md), [document-aggregation.md](document-aggregation.md),
[quarantine-contract.md](quarantine-contract.md). Existing JSONB metadata is the
proposed durable PostgreSQL home; no new runtime storage/migration implemented.
Existing draft/test_candidate/ready + completed_with_warnings can represent
partial readiness without proliferating lifecycle states. Keep partiality
explicit in page/document responses; chunks cannot bridge quarantine gaps.
Future regional reprocess also requires durable approved source retention:
current worker removes temporary uploads after success.

Next step: [recommendation.md](recommendation.md). Certify generic converter
region association/order/coverage and full note contracts before offline PASS;
then worker integration + official isolated DEV E2E. C reingest remains separate.

## Required answers (scope explicit)

| Question | Answer |
|---|---|
| Can a page be PARTIAL? |YES, implemented offline|
| Can a document remain usable with quarantined regions? |YES in contract; worker not integrated|
| Can known bad text reach chunks? |NO through candidate evidence_units; current worker NOT guaranteed|
| Can known bad text reach embeddings? |NO under contract; real pipeline enforcement NOT validated|
| Can known bad text be literal citation? |NO under contract; real citation gate NOT validated|
| Does source error block whole document? |NO unless no useful accepted evidence remains|
| Does platform error block whole document? |NO if isolatable; generic isolation still unproved|
| Do good neighboring regions remain usable? |YES offline167 body; full55 neighbor gate pending|
| Can167 Spanish remain usable? |YES body; current note ordering must be fixed|
| Can167 Hebrew be quarantined? |YES offline, traceable and outside candidate chunks|
| Can56 recover via safe historical capability? |PARTIAL: numbered starts restored, editorial boundaries pending|
| Automatic OCR integrated? |NO|
| Orthographic expansion integrated? |NO|
| Ready to reingest C with quarantine? |NO|

## Git / operations

Branch `feature/console-backend-core`.
HEAD initial/final `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Tracked changes by this phase: **none**. The9 pre-existing tracked modifications
(UI, fidelity module/tests, status) preserved. New files by this phase: only
region_quality.py, test_region_quality.py, and this report directory. All other
pre-existing untracked experiments/reports preserved. No status rewrite of the
user's already modified file. No commit, push, reset, clean, stash, rebase,
branch switch, manual SQL/vector/chunk/publication patch, or C reingest.

Production modified = NO; production services touched = NO.
PG writes = NO; Milvus writes = NO; LiteLLM calls = NO.
Services started/stopped/reconfigured/migrated = NO.

Impact: independently testable contract and honest evidence of missing quality
boundaries, not a runtime change. Main risk: treating positive input flags or
zero offline counters as an end-to-end guarantee. This report explicitly denies
that inference.
