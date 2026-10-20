# Automatic region provenance certification V1 — FAIL

```text
TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V1_FAIL
READY_FOR_C_REINGEST = NO
```

**Experimental opt-in candidate, NOT a trustworthy worker certificate issuer.**
No default extraction path or worker was connected. No manual certificate,
direction, zone geometry or note boundary is supplied to the candidate.

## Delivered / reused

`backend/modules/library/automatic_region_certification.py` parses the actual
PDF through PyMuPDF4LLM (`use_ocr=False`), discovers explicitly labelled note
flows, reuses `region_markdown_provenance.map_layout_page`, preserves forward
source identity and Markdown ranges, and emits JSON-ready certificates. Quality
uses the existing `RegionState` vocabulary and aggregation. Only exact
historical notes-heading recognition is reused; no fuzzy mojibake detector,
SI-960, font correction, reverse matching or offline positive flags.

`backend/modules/library/extractors.py::extract_pdf_with_region_certificates`
is an **opt-in extraction API**. The existing worker/default extractor does NOT
call it. Do not connect it: V1 failed its acceptance criteria.

## Real-source results

Exact SHA `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.

### 167 / printed 149 (printed number from previous visual golden)

| Required field | Actual |
|---|---|
| Body discovered automatically | NO — five separate text boxes, not certified body zones |
| Body provenance certified | NO |
| Body quality | all five UNRESOLVED |
| Notes 60–66 discovered | YES, without input boundaries |
| Note boundaries | page-local PASS; full cross-page end FAIL |
| Column ownership / note order | PASS / PASS |
| Note provenance | all seven CERTIFIED |
| Note quality | 61,62,63,64,66 ACCEPTED; 60,65 UNRESOLVED |
| Hebrew regions discovered / independent | YES / YES (two boxes) |
| Hebrew RTL direction certified | NO — strong script evidence destroyed in extracted text |
| Hebrew quality | UNRESOLVED, not language-based rejection |
| Aggregate | PARTIAL (five accepted note fragments); NOT the requested complete Spanish-body/notes result |

### 55

Corrupt notes-heading region auto-detected: YES. Quality:
PLATFORM_EXTRACTION_ERROR, based on visible native-trace → layout replacement
differential, not coordinates or fixture text supplied to extraction.
Previous neighbor auto-certified: NO / UNRESOLVED. Next neighbor (note33):
YES / ACCEPTED. Neighbor sequence retained: YES.
The old offline fixture certified a selected good tail, not the whole live
preceding box. This implementation does NOT silently trim that box.

### 56

35/36 auto-discovered: YES/YES. Complete **page-local** boundaries, columns,
order and stable offsets: PASS. Complete editorial boundary of35: PASS (before
36). Complete editorial boundary of36: FAIL (no automatic identity/end on57).
Cross-page continuation supported automatically: NO. Both note qualities:
UNRESOLVED. A page boundary is explicitly NOT an editorial end.

## Sealed holdout / decisive failure

12 pages, 148 regions. Rules and independent source-IR zone annotations were
sealed before running the automatic holdout evaluation. No post-evaluation
rule tuning. Hashes: `holdout-seal.json`.

| Metric | Actual |
|---|---:|
| Provenance certified / unresolved | 44 / 104 |
| Correct certifications | 39 |
| Correct unresolved | 28 |
| Good certifiable regions left unresolved | 76 |
| ACCEPTED / platform errors / source errors | 2 / 8 / 0 |
| Quality UNRESOLVED | 138 |
| **Unsafe false certifications** | **5** |

Those five are incorrect zone certificates (80: two notes→footer; 140: one
note continuation→editorial_heading; 200: two notes→footer). All five quality
statuses remain UNRESOLVED; **that does not excuse false provenance**.
Annotations review structural source-IR ownership/zones, not exhaustive rendered
glyph fidelity. Five is the observed count on that annotated scope, not a claim
that no additional visual defects exist. The goldens' checked note ownership
has no observed false certification, but good coverage/end-to-end criteria fail.

## Required answers (supported subset distinguished from gate success)

| Question | Answer |
|---|---|
| Can real extraction automatically discover regions? | YES, layout blocks and explicitly labelled note flows |
| Automatically certify provenance? | YES, subset; issuer NOT safe overall (5 false zones) |
| Automatically certify body zones? | NO |
| Automatically certify note zones? | YES, labelled subset; not unlabelled continuations |
| Automatically preserve column ownership? | YES, supported disjoint note columns |
| Automatically identify corrupt regions? | YES, visible native/layout replacement differential subset |
| Distinguish ACCEPTED / PLATFORM_EXTRACTION_ERROR? | YES, narrow computed evidence subset |
| Do ambiguous cases fail closed? | NO globally: text/direction/unsupported cases do, but 5 erroneous zone certificates escaped |
| Does167 become PARTIAL automatically? | YES, but required body/all-notes certificates FAIL |
| Are55 good neighbors certified automatically? | NO — next only |
| Are56 full note boundaries certified automatically? | NO — page-local only |
| Unsafe false certifications | 5 in annotated holdout |
| OCR used? | NO |
| Worker enforcement integrated? | NO |
| C reingested? | NO |
| Certificates ready for worker consumption? | NO |

## Validation / reproduction

From `SrvRestAstroLS_v1/backend`:

```sh
uv run python ../../data/reports/breslov/automatic-region-provenance-certification-v1/evaluate.py
uv run pytest -q tests/test_automatic_region_certification.py tests/test_region_markdown_provenance.py tests/test_region_quality.py
uv run pytest -q
```

- Focal **91 passed**, including28 new tests.
- Related extraction/editorial/library/content-ingestion **613 passed**.
- Initial full suite, before implementation: **1747 passed,18 failed,94 warnings**.
- Final full suite: **1775 passed,18 failed,94 warnings**.
- All18: PREEXISTING_BASELINE_FAILURE, byte-identical complete failure details
  before/after; **new backend regressions = 0**. Not assumed environment failures.
- Three fresh real-PDF parses: identical IDs, boundaries, ranges and statuses.
- Full box/line permutations on the existing small real-IR goldens pass.
- `git diff --check` and explicit new source/docs/JSON whitespace check: PASS.
  Raw pytest logs retain their original diagnostic whitespace (not rewritten).
- LAT/frontend unchanged by this phase; no LAT/frontend gates claimed.

Passing unit tests validate the limited implementation, **not** the requested
gate. FAIL is not BLOCKED: geometry/identity is available, but the implemented
zone/direction/end-boundary proof is insufficient and demonstrably unsafe.

## Operations / git

Branch `feature/console-backend-core`; initial/final HEAD
`1fa9290bdc7840e7277a998aa3ca66345c6080ee`. Existing worktree hashes preserved.
Changes by this phase: new certification module, new tests, one opt-in function
in `extractors.py`, and this report directory only. No status/LAT/UI rewrite.
Commit = NO; push = NO. PostgreSQL writes = NO; Milvus writes = NO;
C reingest = NO; publication = NO; production changes = NO;
service management = NO; embeddings/LiteLLM = NO.

**Next: V2 automatic zone/continuation certification with a NEW sealed holdout.**
Do NOT reopen worker enforcement yet. Details: [recommendation](recommendation.md).
