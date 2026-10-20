# Git / scope / operations

```text
Branch: feature/console-backend-core
HEAD initial: 1fa9290bdc7840e7277a998aa3ca66345c6080ee
HEAD final:   1fa9290bdc7840e7277a998aa3ca66345c6080ee
Preexisting worktree preserved: YES (627 dirty/untracked files hash-checked)
Commit: NO
Push: NO
```

The initial worktree already had9 tracked modifications and many untracked
experiments/reports. Their627 expanded file hashes are recorded in
`preexisting-worktree.json`; all remain identical. No branch switch,
reset/clean/stash/rebase/merge, deletion or service management.

## Files modified by this phase

- `SrvRestAstroLS_v1/backend/modules/library/extractors.py`:14 added lines,
  one opt-in callable only; existing paths unchanged, no default or worker import.

## Files added by this phase

- `SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification.py`
- `SrvRestAstroLS_v1/backend/tests/test_automatic_region_certification.py`
- `data/reports/breslov/automatic-region-provenance-certification-v1/`:
  README.md, pipeline-trace.md, certificate-contract.md, region-discovery.md,
  direction-certification.md, zone-certification.md, quality-certification.md,
  page167-results.json, page55-results.json, page56-results.json,
  supporting-pages-results.json, holdout-definition.json,
  holdout-annotations.json, holdout-seal.json, holdout-results.json,
  false-certification-analysis.md, stability-results.json,
  backend-failure-classification.md, backend-failure-classification.json,
  test-results.json, evaluation-summary.json, evaluate.py, evaluation.txt,
  tests-focused.txt, tests-related.txt, tests-baseline-full.txt,
  tests-backend-full.txt, baseline-exit.txt, preexisting-worktree.json,
  worktree-results.json, worktree-report.md, recommendation.md.

## Validation / review

Focal91 PASS; related613 PASS; full1775 passed/18 preexisting failed/94 warnings.
Baseline1747/18/94 BEFORE implementation, identical failure-detail bytes.
Three live golden extractions equal. Annotated holdout12 pages,148 regions,
5 unsafe false zone certificates: acceptance FAIL. Frozen V1 rules unchanged
after holdout. The unit suite is not represented as goal acceptance.

Final diff reviewed: only the opt-in14-line tracked addition and new module,
tests/report in this scope. Existing offline adapter/quality files were reused
without modification. Worker/default extraction untouched. AST checks find no
special golden page/note/filename constants in the new product module.
`git diff --check` PASS. New source/docs/JSON whitespace PASS; raw pytest logs
retain original whitespace for failure-detail byte comparisons. LAT/@lat and
frontend unchanged by phase, so no LAT/frontend gate claimed.

## Impact / risk / next step

Service-free, actual PDF→IR→forward Markdown/certificates experimental API and
reproducible evidence exist. The requested capability is NOT safely complete.
Known semantic-zone false certificates, missing body/RTL proofs and unsupported
cross-page identity prohibit worker consumption. Retain V1 as failed experiment;
V2 must use a fresh sealed holdout. Do not reopen worker enforcement or reingest C.

```text
PostgreSQL writes = NO
Milvus writes = NO
C reingest = NO
publication = NO
production changes = NO
OCR = NO
SI-960 full reactivation = NO
worker enforcement = NO
embeddings / LiteLLM calls = NO
```
