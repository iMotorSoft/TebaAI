# Worktree report

- Repository: `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI`
- Branch: `feature/console-backend-core`
- HEAD: `704ae24597e916b56ddec8a71fd0a30d34793aab`
- Commit / push / merge / rebase / reset / stash / clean: **NO**
- Branch change: **NO**
- Services started, stopped or reconfigured: **NO**
- PostgreSQL / Milvus / LiteLLM writes: **NO**
- OCR / orthographic search changes: **NO**
- Worker integration / C reingest: **NO**

## Authored by this gate

Modified:

- `SrvRestAstroLS_v1/backend/modules/library/extractors.py`
  - `extract_pdf_with_region_certificates(...)` imports V4 explicitly.
  - No other behavior changed.

Added:

- `SrvRestAstroLS_v1/backend/tests/test_consumer_region_certificates_v4.py`
- `data/reports/breslov/v4-frozen-confirmation-consumer-boundary-v1/` (all
  holdout, consumer, validation and report artifacts)

## Preserved preexisting changes

The worktree already contained unrelated modifications and untracked files in
Astro components, Hebrew fidelity modules/tests, `status_actual.md`, development
reset scripts, font/reconstruction tests and other Breslov report directories.
They were not edited, staged, reverted or cleaned by this gate.

## Validation

- `git diff --check`: PASS.
- Frozen V4 module, provenance module and V4 test hashes: unchanged.
- V4 frozen tests: 11 passed.
- Consumer focused tests: 8 passed.
- Related tests: 137 passed.
- Full backend: 1849 passed, 18 failed, 94 warnings.
- Failure node IDs: identical to the preexisting 18-failure baseline; 0 new
  regressions. The 8 extra passes are the new consumer tests.
- Holdout: sealed before the single opening; FAIL; no reseal or tuning.
