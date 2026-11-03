# V4 frozen confirmation and consumer boundary V1 — FAIL

```text
TEBAAI_BRESLOV_V4_FROZEN_CONFIRMATION_AND_CONSUMER_BOUNDARY_V1_FAIL
CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO
READY_FOR_C_REINGEST = NO
```

Part A (frozen V4 confirmation) failed its sealed holdout. Part B (consumer
boundary) passed. The combined gate fails because both parts are required.

## Result

| Question | Result |
|---|---|
| Frozen V4 module/tests changed? | **NO** |
| Holdout sealed before first open? | **YES** |
| Single opening only? | **YES**; no reseal, no post-open tuning |
| Unsafe false certifications | **6** |
| Unsafe false provenance certifications | **6** |
| False body certifications | **0** |
| Unsafe false continuations | **2** |
| False editorial completions | **6** |
| Body coverage | **99/119** |
| Notes coverage | **44/103** |
| Cross-page coverage | **0/3** |
| Consumer now calls V4? | **YES**, explicitly |
| V1 fallback in consumer? | **NO**; fail-closed |
| Consumer output parity with direct V4? | **YES** |
| Worker integration added? | **NO** |
| New backend regressions | **0**; same 18 preexisting node IDs |
| `git diff --check` | **PASS** |
| Certificates ready for worker? | **NO** |

## Why Part A failed

1. **Annotation mapping defect on pages 13 and 15.** Full-width note lines
   were grouped by visual centre, so expected units did not map one-to-one to
   V4 regions. Five V4 note regions were counted unsafe even though their note
   numbers/text matched the source note column.
2. **Genuine V4 false continuation on pages 206–207.** V4 linked
   `p206 note 5` to leading body text at the top of p207 and certified that
   body region as `note 5`. The real p207 note 5 is a different unit and is
   not certifiable. This is a V4 continuation-proof defect, not an annotation
   artifact.

Neither cause may be repaired by resealing this holdout or changing frozen V4
inside this gate.

## Part B

`extract_pdf_with_region_certificates(...)` in
`SrvRestAstroLS_v1/backend/modules/library/extractors.py` now imports
`automatic_region_certification_v4` directly. The public page-dictionary shape
is unchanged. New tests prove explicit dispatch, no V1 call, no V1 fallback,
direct-V4 parity, V4 certificate version, cross-page propagation through the
consumer, unresolved output preservation, page validation, and that the worker
does not use the helper.

## Evidence

- [Holdout analysis](holdout-analysis.md)
- [Sealed definition](holdout-definition.json), [seal hash](holdout-sealed-hash.txt),
  [first-open record](holdout-first-open.json), [results](holdout-results.json)
- [Annotation sanity](holdout-annotation-sanity.json), [cross-page results](holdout-cross-page-results.json)
- [Before](consumer-boundary-before.md) / [after](consumer-boundary-after.md)
- [Consumer parity](consumer-parity-results.json), [consumer cross-page](consumer-cross-page-results.json)
- [Focused tests](focused-tests.txt), [related tests](related-tests.txt), [V4 tests](v4-frozen-tests.txt)
- [Full backend](backend-results.txt), [baseline comparison](backend-results.json)
- [V1 unsafe regression](v1-unsafe-regression-results.json)
- [Permutation](permutation-results.json), [stability](stability-results.json)
- [Hashes before](frozen-hashes-before.json), [hashes after](frozen-hashes-after.json)
- [Gate](gate.json), [validation](final-validation.json), [worktree](worktree-report.md),
  [recommendation](recommendation.md)

## Reproduce

From `SrvRestAstroLS_v1/backend`:

```sh
uv run pytest -q tests/test_automatic_region_certification_v4.py
uv run pytest -q tests/test_consumer_region_certificates_v4.py
uv run pytest -q tests/test_region_markdown_provenance.py tests/test_automatic_region_certification.py tests/test_automatic_region_certification_v2.py tests/test_automatic_region_certification_v3.py tests/test_page_markers_extraction.py
uv run python /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/data/reports/breslov/v4-frozen-confirmation-consumer-boundary-v1/run_v1_unsafe_regression.py
uv run python /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/data/reports/breslov/v4-frozen-confirmation-consumer-boundary-v1/run_consumer_checks.py
```

Do not reopen or reseal this holdout to tune V4. Do not integrate certificates
into the worker or reingest the corpus until a later phase passes an independent
holdout and worker integration review.
