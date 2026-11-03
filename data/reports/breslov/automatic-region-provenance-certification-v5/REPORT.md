# Automatic Region Provenance Certification V5

Gate: `TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V5_PASS`

Status: **PASS**, with the coverage caveat documented below.

## Scope

V5 re-validates every V4 cross-page link against a named positive identity
contract. It keeps V4 for body, notes, quality and local safety. Missing
evidence fails closed; a contradiction fails to `IDENTITY_REJECTED`. No LLM,
embedding, semantic model, filename or page-number rule is used.

The sealed holdout is intentionally **safety-only**. Every fresh unseen
source-only true continuation had already been opened during V4/V5
development, so the holdout tests negatives, full-width/column note cases and
no-note pages. The four proven positives are a separate development
regression suite.

## Reclassification

`206 -> 207` note 5 is a true continuation, not a negative:

- p206 note 5 ends `...sobre el versículo “Ahora bien, la Serpiente era muy astuta”,`
- p207 leading note-zone text continues `que la Serpiente deseaba a la primera mujer...`

The V4 frozen holdout annotation was defective for this pair. V5 preserves the
link.

## Sealed holdout

- Source: `LIKUTEY HALAJOT (Interior Final).pdf`
- Source SHA-256: `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`
- 32 physical pages: `121,129,135,142,148,155,160,181,183,186,187,189,192,197,198,199,214,222,224,228,232,236,239,240,245,246,247,251,252,253,254,255`
- 8 cross-page negative pairs: `186->187`, `197->198`, `198->199`, `245->246`, `246->247`, `251->252`, `252->253`, `253->254`
- 4 no-note pages: `183,239,240,255`
- 262 annotated units, 64 note units
- Independent pre-seal validator: **PASS**, 0 errors, 10 warnings (4 no-note pages, 6 non-vertical full-width unit orders)
- Validator regression on the frozen V4 holdout: **FAIL with 30 errors** (`frozen-v4-validation.json`), including the pp.13/15 full-width split, missing units, merged units, marker mismatches and the `206->207` unannotated leading continuation. This proves the validator detects the defects that motivated V5.
- The holdout was sealed before the first V5 run; `holdout-first-open.json` records the single open.

## Sealed V5 result

| metric | value |
| --- | --- |
| regions | 398 |
| unsafe false certifications | 0 |
| unsafe false provenance certifications | 0 |
| false body certifications | 0 |
| unsafe false continuations | 0 |
| false editorial completions | 0 |
| unsafe false `IDENTITY_PROVEN` | 0 |
| inconsistent identity states | 0 |
| `CANDIDATE_CONTINUATION` | 11 |
| body coverage | 75/97 (accepted 35) |
| notes coverage | 17/55 (accepted 12) |
| cross-page links | 0/0 |

All eight negative pairs stayed unlinked. No false positive identity survived.

### Coverage caveat

The sealed evaluator copied a V4 majority-coverage threshold
(`notes_certified >= notes_unresolved`). The safety-only 32-page set contains
many short reference notes that V4 also leaves unresolved, so that threshold
failed: `holdout-results.json` records `gate: FAIL` with
`coverage_pass: false`.

A post-open V4 parity run on the **identical 32 pages** produced exactly the
same coverage and acceptance:

- body 75/97, accepted 35
- notes 17/55, accepted 12
- unsafe counters all 0

V5 therefore has **no coverage regression** against V4. The authoritative
utility threshold is V4 parity for this safety-selected set, not a majority of
notes. No safety rule was changed. The original sealed output is preserved
unchanged; `gate-decision.json` records the restatement.

## Development regression (separate, not sealed)

`development-regression-results.json`: **PASS**

Proven:

- `206->207` note 5
- `56->57` note 36
- `167->168` note 66
- `16->17` note 1

Not proven (fail closed):

- `108->109`
- `164->165`
- `226->227`

## Other checks

- Determinism and page/box/line permutation: **PASS** (`determinism-results.json`, 49 regions, identical signature `0bf736cf…`)
- Negative ablations: **PASS** 5/5 (`negative-results.json`): terminal not at page boundary, leading marked, wrong note number, missing native evidence, different source SHA. States are `IDENTITY_UNRESOLVED` or `IDENTITY_REJECTED`; never `IDENTITY_PROVEN`.
- Consumer parity: **PASS** (`consumer-results.json`): consumer output equals direct V5, all certificates are V5, `206->207` preserved, `108->109` not linked.
- Frozen V4 hashes unchanged:
  - certifier `1c7e284516361f375ddbba7fd010aa49d658910381f000634a7231760e548965`
  - V4 test `9be69378cf0d252de76cdfc487f6547dc9fd830272a39e3e3b57ba7d37171bec`
  - provenance `4b0291fab84ce623098c89b12e24e2fc9174ade1922f275310c77e07d0b9eb7b`

## Tests

- Focused: `144 passed` (V5, validator, consumer V5, V4 frozen, V1-V4, provenance)
- V4 frozen: `11 passed`
- Full backend: `1861 passed, 18 failed, 0 new regressions`
  - The 18 failures are the known pre-existing real-service `investigative_qa_v1` and `named_topics` tests.
- `git diff --check`: clean

## Files changed for this task

- `SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification_v5.py` (new)
- `SrvRestAstroLS_v1/backend/modules/library/annotation_preseal_validation.py` (new)
- `SrvRestAstroLS_v1/backend/modules/library/extractors.py` (consumer now V5)
- `SrvRestAstroLS_v1/backend/tests/test_automatic_region_certification_v5.py` (new)
- `SrvRestAstroLS_v1/backend/tests/test_annotation_preseal_validation.py` (new)
- `SrvRestAstroLS_v1/backend/tests/test_consumer_region_certificates_v5.py` (new; replaces the V4 consumer test)
- `data/reports/breslov/automatic-region-provenance-certification-v5/` (this report and all evidence/scripts)

## Risks and next step

- No fresh unseen cross-page positives remain. The positive contract is guarded by the development regression suite and the live consumer check, not by the sealed holdout.
- Notes coverage is V4 parity (17/55 on this safety set); short reference notes remain unresolved by V4 and V5.
- 11 terminal notes remain `CANDIDATE_CONTINUATION` with no link. This is the intended fail-closed state.
- The original sealed evaluator's majority-coverage threshold failed. The gate restatement is documented; it changes only the utility threshold, not safety.
- After the sealed run, two unused imports (`_note_direction`, `_plain`) were removed from `automatic_region_certification_v5.py`. No logic changed; focused tests, development regression and consumer parity were re-run and passed.
- Next step: keep V5 as the opt-in consumer and do not reintroduce a V1/V4 fallback. Any future coverage improvement should be a new version with a new sealed holdout, not a post-hoc V5 change.
