# TEBAAI_BRESLOV_V5_EVALUATOR_CORRECTION_V1_PASS

Evaluator-only gate. Branch `feature/console-backend-core`; local/upstream HEAD
`704ae24597e916b56ddec8a71fd0a30d34793aab` at start. COMMIT=NO; PUSH=NO.

## Reproduction → correction

Both defects reproduced on the unchanged original function before editing.
The original function was AST-extracted without importing run_gate or V5 and is
archived in legacy_evaluator.py. Identity proof is PASS in synthetic fixtures.

| Defect | Before | After | Negative control |
|---|---:|---:|---|
| Valid reciprocal relation: false_cross_page_links | 1 | 0 | wrong target detected |
| Valid continuation: false_editorial_completions | 1 | 0 | false COMPLETE_LOCAL detected |

Corrected evaluator is standalone, version `v5-evaluator-correction-v1`.
run_gate.source_audit now imports it; V5 import is deferred to main(), which was
NOT called. Tests exercise the real audit entrypoint via a non-main import.
See evaluator-inventory.md and evaluator-semantics-contract.md.

## Synthetic before/after matrix

Columns show false links / false local completions. The JSON artifacts additionally
assert misses, reciprocal misses, unsafe identity and unique valid relations.

| Case | Before | After | Verdict |
|---|---|---|---|
| same-page complete | 0 / 0 | 0 / 0 | PASS |
| boundary open | 0 / 0 | 0 / 0 | PASS |
| forward continuation (missing reciprocal tracked separately) | 1 / 1 | 0 / 0 | PASS |
| valid reciprocal relation | 1 / 1 | 0 / 0 | PASS |
| wrong target, two distinct conflicting claims | 2 / 1 | 2 / 0 | PASS |
| explicit no-link, reciprocal invalid claim | 2 / 0 | 1 / 0 | PASS |
| missing expected relation | 0 / 0 | 0 / 0 | PASS; missed_true_links=1 |
| valid CROSS_PAGE_COMPLETE | 1 / 1 | 0 / 0 | PASS |
| false COMPLETE_LOCAL | 1 / 1 | 0 / 1 | PASS |
| unresolved without link | 0 / 0 | 0 / 0 | PASS |
| unresolved incorrectly proven/linked | 2 / 0 | 1 / 0 | PASS; unsafe identity=2 |
| conflicting editorial IDs | 2 / 1 | 1 / 0 | PASS |
| duplicate relation representations | 1 / 1 | 0 / 0 | PASS; one valid relation |
| dangling link | 1 / 1 | 1 / 0 | PASS |
| existing wrong region, same note | 1 / 1 | 1 / 0 | PASS |

Full six-counter matrix: before 3/15 pass; after **15/15 pass**, 0 failed,
0 evaluator false negatives and 0 evaluator false positives across those assertions.
The wrong-target synthetic expectation was clarified from one to two false
relations because it contains A→absent AND B→A with conflicting A output. Both
baseline and corrected evaluator were compared to that same clarified truth;
no corpus/development expected label was changed. Original bug reproduction
artifacts were not rewritten.

Six deliberate negative controls all detected: wrong target, missing reciprocal,
conflicting editorial IDs, explicit no-link violation, false local completion,
unsafe proven identity on unresolved truth. Duplicate/order tests, second-target
mutation, failed proof, duplicate region IDs and unrelated-note completion are
covered by focused tests.

## Legacy regression and safety

The previous stored resume-evaluator-audit.json is synthetic, not corpus output.
Original counters match it exactly. Corrected deltas: false links -1, false
completions -1; ALL other existing counters unchanged. No unsafe provenance,
body-certification or legacy identity counter drift. Additional synthetic
ownership/body/identity safety mutations preserve positive detections. New unsafe
identity counters intentionally detect proven invalid relations the old evaluator
missed; they are not evidence of V5 defects.

## Validation

- Focused evaluator: **31 passed**, 0 failures; V5 import guard PASS.
- Related backend provenance/quality/preseal: **95 passed**, 0 failures;
  V5 import guard PASS.
- Existing source_audit tests: none found; archived audit regression included.
- Full backend: not run, optional here. Evaluator lives under reports and no
  production module imports it; full collection would unnecessarily include V5
  certifier/consumer tests. No frontend/LAT changes, no services used.
- Synthetic validation has guards rejecting V5 imports and holdout/PDF reads.
- git diff --check: PASS (tracked worktree plus explicit authored/untracked checks).
- Four protected hashes identical; preexisting unrelated file hashes preserved.
- Corrected evaluator/test/fixture/contract hashes frozen in evaluator-freeze.json.

## Scope and impact

Authored code: evaluator.py, run_gate.py audit wiring/dependency isolation, and
backend/tests/test_v5_evaluator_semantics.py. Other authored files are confined
to this evaluator evidence directory. Existing INVALID report/manifest and input
artifacts stay unchanged, except the explicitly corrected evaluator runner source.
Old frozen hashes remain historical; they must NOT be reused for a future run.
No certifier, consumer, worker, source inventory, corpus labels or coverage/utility
thresholds changed. No 85-page/12-positive set was parsed, evaluated or modified.
Baseline inventory hashes were preservation-only, never dataset evaluation.

V5_CHANGED=NO; CONSUMER_CHANGED=NO; V5_EVALUATED=NO;
V5_DEFECT_DEMONSTRATED=NO. PREOBSERVED_V5_UNEXPOSED remains 85 pages / 12 pairs.
CERTIFICATES_READY_FOR_WORKER_INTEGRATION=NO; READY_FOR_C_REINGEST=NO.

## Limits / next step

This PASS proves only the evaluator's tested semantics, not V5 readiness or
complete independent lineage eligibility. Canonical input/row ownership must be
available; missing output endpoints remain the positive-pair missed_links
responsibility. Unresolved/incomplete context is not inferred as valid identity.
Runner Parts A/B/C are deliberately unexecuted. Review this correction and freeze
before `TEBAAI_BRESLOV_V5_HYBRID_CONFIRMATION_RESUME_V2`; a fresh manifest must
include corrected evaluator.py. Do NOT execute that next gate here.
