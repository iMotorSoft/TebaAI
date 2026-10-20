# Automatic region provenance certification V3 — FAIL

```text
TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V3_FAIL
CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO
READY_FOR_C_REINGEST = NO
```

**Safety preserved; generic-body and cross-page utility insufficient. Native-backed permutation also FAILS.** No post-holdout tuning, worker integration or corpus writes.

## Mandatory answers

| Question | Result |
|---|---|
| Did V3 preserve 0 unsafe V2 certifications? | YES on five V1 exact negatives, V2 regression annotations and new holdout |
| Generic body proof implemented? | YES, restricted two-rule editorial-panel family |
| Page 167 Spanish body | **UNRESOLVED as a whole**: 4/5 provenance CERTIFIED, only 1/5 ACCEPTED |
| Does body proof avoid headers/notes/footers? | YES on evaluated negatives/regressions/holdout, not a universal guarantee |
| Cross-page editorial model implemented? | YES, separate physical segments and deterministic editorial identity |
| Page 56 note 36 linked safely to 57? | UNRESOLVED |
| Page 167 note 66 linked safely forward? | YES, to 168; next segment's quality independently UNRESOLVED |
| False editorial completions | **0** |
| Unsafe false continuations | **0** |
| New holdout pages | **30** |
| New holdout emitted regions | **366** (360 independently annotated source units) |
| Unsafe false certifications | **0**; also 0 incorrect provenance certifications regardless of quality |
| False body certifications | **0** |
| Good body regions unresolved | **51/70 provenance**; 60/70 not ACCEPTED |
| Body supported/source-certifiable coverage | **19/70 (27.1%) CERTIFIED; 10/70 (14.3%) ACCEPTED** |
| Cross-page supported coverage | **0/4 linked**, all four unresolved |
| Was holdout sealed before evaluation? | YES, source annotations, dependencies, evaluator, tests, contracts and contact sheets hashed |
| Were rules changed after evaluation? | **NO**; sealed hashes reconfirmed |
| Ambiguous layouts fail closed? | YES on evaluated evidence |
| Same-input three-run determinism | PASS, full JSON digests identical |
| Real page/box/line permutation | **FAIL**; V2 delegated selected-line order changes native proof and continuation discovery |
| New backend regressions | **0**; same 18 complete failure blocks byte-identical |
| Was OCR used? | NO |
| Was orthographic search changed? | NO |
| Was worker integrated? | NO |
| Was C reingested? | NO |
| Certificates ready for worker? | **NO** |

## Evidence and contracts

- [V2 reused / strengthened / V3 new](v2-gap-analysis.md).
- [Body proof](body-proof-contract.md), [negative cases](body-negative-cases.json).
- [Editorial model](cross-page-model.md), [continuation proof](continuation-proof-contract.md), [development cases](cross-page-development-cases.json).
- [167](page167-results.json), [55](page55-results.json), [56–57](page56-57-results.json), [66 on 167–168](page167-168-note66-results.json).
- [V1/V2 regressions](v1-v2-regression-results.json): all five false zones remain safe; former V2 holdout now development/regression, 20 correct V3 certifications and zero source-annotation mismatches.
- [Holdout definition](holdout-v3-definition.json), [seal](holdout-v3-sealed-hash.txt), [opening record](holdout-evaluation-started.json), [results](holdout-v3-results.json).
- [Safety](unsafe-certification-analysis.md), [continuation analysis](false-continuation-analysis.md), [coverage](coverage-analysis.md).
- [Stability](stability-results.json), [permutation investigation](permutation-analysis.json).
- [Backend](backend-results.json), [baseline comparison](baseline-failure-comparison.json), [worktree](worktree-report.md), [recommendation](recommendation.md).

### Development targets

167 remains PARTIAL. Notes 61–64 remain CERTIFIED+ACCEPTED; 60/65 unresolved; 66 origin segment CERTIFIED+ACCEPTED and safely linked before 67 on 168. RTL remains unresolved. Whole body is not called accepted merely because four units have structural provenance. 55 bad heading and previous whole interleaved body box remain unresolved; next note 33 is CERTIFIED+ACCEPTED. 36 on 56 has a known physical boundary but no identity link to 57; neither 36 nor 66 is falsely declared locally complete at the page cut.

### Holdout integrity and limits

30 final pages are disjoint from V1/V2 holdouts, the five V1 false certifications, and development target pages 55/56/57/167/168. Four actual consecutive-page editorial units were source-observed before evaluation. `inspect_source.py` imports no certifier. `seal_holdout.py` records manually reviewed source roles/boundaries independently of V3 output. One-shot `evaluate_holdout.py` verifies hashes before opening and does not change rules or annotations. No second opening or post-evaluation rule/test/contract changes.

Source review used native IR plus five rendered source contact sheets. It was performed by the implementing agent, **not independent human adjudication or exhaustive glyph QA**. Early source exploration files for discarded pages 49/50/175/176/219/220 are retained as exploratory evidence only; the sealed definition/inventory and contact sheets identify the actual final 30 pages.

The coverage denominator includes independently source-certifiable target units that discovery does not yet separate/support. It is not restricted to already successful candidate profiles. Thus 51/70 unresolved good bodies and 0/4 links cannot be disguised as useful coverage. This is **FAIL, not BLOCKED**: useful native geometry and markers exist; remaining gaps are in proof/implementation.

## Validation

- Focal certification/body/continuity/provenance/quality: **146 passed** (28 new V3 tests).
- Related library/PDF/Markdown/layout/notes/quality: **692 passed**, 10 warnings.
- Full backend: **1830 passed, 18 failed, 94 warnings**. All 18 node IDs and complete failure-detail blocks are byte-identical to V2's 1802/18/94 log. **0 new regressions**; baseline failures untouched.
- Three fresh eight-page development extractions: identical complete JSON/IDs/statuses/proofs. Real native-backed permutation **FAILS**, unlike the narrower synthetic permutation control. Investigation is preserved rather than fixed after holdout.
- `git diff --check`: PASS; new-file whitespace validation and final source/diff review PASS. Frontend/LAT unchanged, respective gates not applicable.

Reproduction from `SrvRestAstroLS_v1/backend`:

```sh
uv run pytest -q tests/test_automatic_region_certification_v3.py tests/test_automatic_region_certification_v2.py tests/test_automatic_region_certification.py tests/test_region_markdown_provenance.py tests/test_region_quality.py
uv run python ../../data/reports/breslov/automatic-region-provenance-certification-v3/development.py
```

**Do not reseal/reopen the V3 holdout to tune V3.** Future work requires V4 plus another independent holdout. Worker E2E remains closed.

## Git / data / production

Branch `feature/console-backend-core`. HEAD initial/final:
`1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Added: isolated `backend/modules/library/automatic_region_certification_v3.py`,
`backend/tests/test_automatic_region_certification_v3.py` and this report directory.
Existing files modified by this phase: **none**. All **713** preexisting changed/untracked files preserved by SHA-256.

Commit = NO; push = NO; branch changes = NO; services managed = NO.
PostgreSQL writes = NO; Milvus writes = NO; C reingest = NO;
publication changes = NO; production changes = NO; OCR = NO;
orthographic search changes = NO; worker enforcement = NO.
