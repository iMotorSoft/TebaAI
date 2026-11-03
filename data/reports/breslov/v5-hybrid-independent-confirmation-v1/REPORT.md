# V5 hybrid confirmation resume — INVALID

Branch: `feature/console-backend-core`. Local, fetched remote and ls-remote at start:
`704ae24597e916b56ddec8a71fd0a30d34793aab`.

## Stop reason

The current candidate and evaluator were cryptographically frozen before any V5
import/execution. Static contract audit found a frozen evaluator defect. An
isolated synthetic test of the unchanged `source_audit` function reproduced it
without importing or executing V5 (see `resume-evaluator-audit.json`).

* `run_gate.py:130–158` treats every linked row as a forward link to page +1.
  V5 explicitly emits reciprocal `CONTINUED_FROM_PREVIOUS` links to page -1
  (`automatic_region_certification_v5.py:520–530`). A valid reciprocal link is
  therefore falsely counted as `false_cross_page_links`.
* `run_gate.py:160–168` treats `CROSS_PAGE_COMPLETE` as local completion and
  counts it as false whenever canonical continuation exists on the next page.
  This penalizes the very continuation it should validate.

Synthetic evidence: one valid forward/backward pair produces one false-link
counter and one false-completion counter. These are evaluator audit results,
**not V5 corpus results**. No technical failure of V5 is asserted.

The frozen evaluator was not repaired. No seal was created, no V5 execution,
no certifier tests/full backend, no staging, commit or push.

## Preserved evidence

All 14 original artifacts remain byte-identical. Source-only prevalidation is
reused as historical evidence: PASS, 139 checks, 0 failures, 121 gate pages,
82 canonical structural errors retained. It is not a gate PASS. No rerun was
performed because its writer targets a frozen artifact.

85 safety pages and the 12 selected positive pairs remain preserved, with new
semantic classification `PREOBSERVED_V5_UNEXPOSED`. Inventory cross-check finds
no detected V5 influence on those 12 pairs; complete independent lineage audit
was not finished after evaluator invalidity, so final eligibility is not claimed.
Pairs: 42→43, 60→61, 64→65, 70→71, 73→74, 104→105, 122→123,
123→124, 130→131, 139→140, 149→150, 150→151.

Existing positive contract has minimum_correct_links=3 (not a majority rule);
frozen runner labels insufficient utility BLOCKED, unlike the resume FAIL
semantics. No threshold or expected label was changed. No majority rule found
in the reviewed safety/positive/development contracts.

All frozen hashes and all preexisting worktree file hashes remain identical.
`git diff --check` passed. Synthetic evaluator audit passed (defect reproduced).
Remaining requested execution artifacts intentionally do not exist: making
empty PASS/FAIL results would misrepresent an unexecuted gate.

## Result

`TEBAAI_BRESLOV_V5_HYBRID_CONFIRMATION_RESUME_V1_INVALID`

CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO
READY_FOR_C_REINGEST = NO
COMMIT = NO
PUSH = NO

No V6, worker, reingestion, database/vector writes or production actions.
