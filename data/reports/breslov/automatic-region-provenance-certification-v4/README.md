# Automatic region provenance certification V4 — PASS

```text
TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V4_PASS
CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO
READY_FOR_C_REINGEST = NO
```

V4 fixes the V3 real-permutation failure by canonicalizing pages, boxes and
text lines before any proof, keeps 0 unsafe certifications, and materially
improves generic body and safe cross-page utility. No worker integration,
corpus writes, OCR, search changes or reingest.

## Mandatory answers

| Question | Result |
|---|---|
| Real page/box/line permutation | **PASS**; seed 321, 8 pages, 431 regions on holdout, `changed_regions=0` |
| Did V4 preserve the five V1 unsafe zones unresolved? | YES, all five `UNRESOLVED` |
| Unsafe false certifications (sealed holdout) | **0** |
| Unsafe false provenance certifications | **0** |
| False body certifications | **0** |
| False editorial completions | **0** |
| Unsafe false continuations | **0** |
| Sealed V4 holdout | 32 disjoint pages, 431 regions |
| Body supported coverage | **87/117 CERTIFIED** (23 ACCEPTED) |
| Notes supported coverage | **72/100 CERTIFIED** |
| Cross-page supported coverage | **7/7 linked** |
| Development (older V3 holdout re-run) body | **60/70 CERTIFIED** vs V3 baseline **19/70** |
| Development cross-page | **3/4** vs V3 baseline **0/4** |
| Same-input three-run determinism | PASS, full JSON digests identical |
| New backend regressions | **0**; same 18 complete failure node IDs byte-identical |
| Was OCR used? / search changed? / worker integrated? / C reingested? | NO / NO / NO / NO |
| Certificates ready for worker? | **NO** |

## What V4 changed

- Canonical, order-invariant traversal of `parsed.pages`, `box` and
  `textline`; the V3 native-input permutation failure is gone.
- Generic centred-caption body frame with canonical source IDs and script LTR
  ordering for `ORDER_PROOF`; native visibility only adds evidence.
- Separator-based note zone that preserves original box class (keeps footer
  lineage safe) and 3-digit note markers.
- Document-level continuation linking with deterministic editorial identity.

## Holdout integrity and the first open

The V4 holdout was sealed before evaluation. The **first** opening failed
safety, but purely because the auto-generated note annotations over-split
lines on inline digits, creating spurious expected note units; certified
notes then matched no expected unit and were counted unsafe. The defect was
confirmed against source IR and the first open is preserved as invalid
evidence:

- `holdout-v4-definition-first-open-invalid.json`
- `holdout-v4-results-first-open-invalid.json`
- `holdout-v4-sealed-hash-first-open-invalid.txt`
- `holdout-evaluation-started-first-open-invalid.json`

The corrected seal removes the inline split and derives note units from source
lines and boxes only (independent of V4 output). **No V4 rule, test or
contract changed after opening.**

Source review used native IR; it was performed by the implementing agent, not
independent human adjudication or exhaustive glyph QA.

## Evidence

- [Permutation](permutation-analysis.json), [stability](stability-results.json).
- [V1/V2 regression](v1-v2-regression-results.json), [safety](unsafe-certification-analysis.md).
- [Body proof](body-proof-contract.md), [continuation contract](continuation-proof-contract.md).
- [V2/V3 gap analysis](v2-gap-analysis.md), [coverage](coverage-analysis.md).
- [Holdout definition](holdout-v4-definition.json), [seal](holdout-v4-sealed-hash.txt),
  [opening record](holdout-evaluation-started.json), [results](holdout-v4-results.json).
- [Backend](tests-backend-full.txt), [baseline comparison](baseline-failure-comparison.json),
  [worktree](worktree-report.md), [recommendation](recommendation.md).

## Validation

- V4 focused: **11 passed**.
- Full backend: **1841 passed, 18 failed, 94 warnings**; the 18 failing node IDs
  are byte-identical to the preexisting baseline (11 extra passes are the new
  V4 tests). **0 new regressions.**
- `git diff --check`: PASS. Frontend/LAT unchanged, respective gates not
  applicable.

Reproduction from `SrvRestAstroLS_v1/backend`:

```sh
uv run pytest -q tests/test_automatic_region_certification_v4.py
uv run python ../../data/reports/breslov/automatic-region-provenance-certification-v4/evaluate_holdout.py
```

**Do not reseal/reopen the V4 holdout to tune V4.** Worker E2E remains closed
and `READY_FOR_C_REINGEST = NO` until an independent holdout and a worker
integration phase approve it.
