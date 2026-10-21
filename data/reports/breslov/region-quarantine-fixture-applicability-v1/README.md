# Region quarantine fixture applicability V1

Scope: fixture contracts and worker metric only; no product logic changes.

- [REPORT.md](REPORT.md): verdict, validation and limits.
- [responsibility-contract.md](responsibility-contract.md): certifier vs worker.
- `previous-fixture-reconstruction.json`: exact A/C/D inputs, IDs and verdicts.
- `full-pipeline-fixture-analysis.json`: intent/actual/worker counters separated.
- `real-breslov-evidence.json`: frozen prior actual E2E, not a fresh store run.
- `metric-contract.json`, `metric-negative-controls.json`: metric and controls.
- `harness-frozen-*`: pre-run contract/test hashes (no post-result adjustments).
- `protected-production-hashes-*.json`: all backend production Python plus every
  prior worker-E2E report artifact, compared before/after.
- `worktree-before.json`: preexisting dirty worktree and file hashes.
- `baseline-failure-comparison.json`: exact full-suite failing-node comparison.

Reproduce from repository root:

```bash
cd SrvRestAstroLS_v1/backend
uv run pytest tests/test_region_publication.py tests/test_region_worker_enforcement.py tests/test_region_fixture_applicability.py tests/test_region_source_access.py -q
uv run pytest -q
```

Preserved earlier gate: `../region-quarantine-worker-e2e-v1/`, still FAIL.
No actual certifier rerun, reingest, service management, migration, or controlled
E2E store writes. New contract tests use declared certificates and in-memory I/O.
Full-suite live retrieval tests retain their existing behavior and baseline.
