# Audit input — V4 frozen confirmation and consumer boundary V1

## Identity

- Gate: `TEBAAI_BRESLOV_V4_FROZEN_CONFIRMATION_AND_CONSUMER_BOUNDARY_V1`
- Result: **FAIL**
- Repo: `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI`
- Branch: `feature/console-backend-core`
- HEAD: `704ae24597e916b56ddec8a71fd0a30d34793aab`
- Report directory:
  `data/reports/breslov/v4-frozen-confirmation-consumer-boundary-v1/`

## Scope

Part A: attempt to confirm frozen V4 on a new, disjoint, sealed holdout.
Part B: make the opt-in PDF consumer call V4 explicitly and fail closed, without
worker integration.

No V4 module, V4 test or provenance module change. No reseal after the first
open. No corpus, database, vector index or service mutation.

## Source

- PDF (outside repo):
  `/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf`
- SHA-256:
  `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`
- Physical pages: 284
- Holdout: 35 pages, 447 regions, 119 supported body units, 103 supported note
  units, 3 annotated cross-page units.
- Disjointness: excludes all 108 pages recorded in
  `previous-holdout-page-inventory.json` and `holdout-source-inventory.json`.

## Seal and open

- Definition SHA-256:
  `c7e696e60bca4163541006f548a34c996141fe3fc6963494b82097d8a1f1d18c`
- Seal SHA-256:
  `df571af2b9e6cfc445f8df036388b1c5a99cb1a259736dce7638b03613714118`
- Sealed before evaluation: YES
- Openings: 1
- Resealed or reopened: NO
- Post-open rule changes: NO

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `automatic_region_certification_v4.py` | `1c7e284516361f375ddbba7fd010aa49d658910381f000634a7231760e548965` |
| `region_markdown_provenance.py` | `4b0291fab84ce623098c89b12e24e2fc9174ade1922f275310c77e07d0b9eb7b` |
| `test_automatic_region_certification_v4.py` | `9be69378cf0d252de76cdfc487f6547dc9fd830272a39e3e3b57ba7d37171bec` |
| `extractors.py` before | `6520e0e9772db9862ffbe12e64ad9751290c3e94fae2ddb7492d65226bfa2bb1` |
| `extractors.py` after | `0a296dbbfd273d2c13db2963ba59ae65feccfed2634a89f58106900e91520bfb` |

## Holdout result

| Metric | Value |
|---|---:|
| Unsafe false certifications | 6 |
| Unsafe false provenance certifications | 6 |
| False body certifications | 0 |
| Unsafe false continuations | 2 |
| False editorial completions | 6 |
| Body coverage | 99/119 |
| Notes coverage | 44/103 |
| Cross-page coverage | 0/3 |

Failure causes:

1. Pages 13/15: annotation mapping defect from full-width note-line grouping.
2. Pages 206/207: genuine V4 false continuation; leading body text certified
   as p206 note 5. The real p207 note 5 is a different, non-certifiable unit.

## Consumer boundary

- File: `SrvRestAstroLS_v1/backend/modules/library/extractors.py`
- Change: explicit import of
  `modules.library.automatic_region_certification_v4`.
- No dynamic latest selection, environment switch or V1 fallback.
- Output remains `page.to_dict()` per requested page.
- Worker does not call `extract_pdf_with_region_certificates`.

## Tests

- V4 frozen: 11 passed.
- New consumer tests: 8 passed.
- Related tests: 137 passed.
- Full backend: 1849 passed, 18 failed, 94 warnings.
- Baseline: 1841 passed, 18 failed, 94 warnings.
- Failure node IDs byte-identical; new regressions 0.
- V1 unsafe regression: 5/5 remain `UNRESOLVED` under V4.
- Determinism: 2 runs identical; sorted/reversed page order identical.
- `git diff --check`: PASS.

## Safety declarations

- Commit / push: NO
- Branch change: NO
- PostgreSQL / Milvus / LiteLLM writes: NO
- C reingest: NO
- OCR: NO
- Search changes: NO
- Worker integration: NO
- Production changes: NO
