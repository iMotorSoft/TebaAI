# Region Quarantine Worker E2E V1

**TEBAAI_BRESLOV_REGION_QUARANTINE_WORKER_E2E_V1_FAIL**

Read [REPORT.md](REPORT.md), [gate.json](gate.json), and [architecture-decision.md](architecture-decision.md).

Real targeted worker + PostgreSQL + LiteLLM + Milvus were exercised. Quarantined text never reached chunks/vectors; authenticated original PDFs survived upload cleanup. The real Breslov subset retained all three certified accepted units through retrieval and citation construction. However, actual synthetic PDFs A/C/D lost four expected GOOD units because unchanged V5 returned UNRESOLVED for their layouts. Frozen expected labels were **not** changed. This is not PASS.

## Evidence

- `worker-integration-results.json`: six final actual-worker jobs.
- `controlled-test-cases.json`: original expected GOOD/BAD labels and final fixture hashes.
- `real-source-case.json`: original pages 54–56, isolated physical pages 1–3 (p55 = isolated p2).
- `dev-store-*.json`: full-row corpus fingerprints, including existing vector values.
- `*-results.json`: per-boundary results; `cleanup-results.json`: two normal manifest cleanups per job.
- `focused-tests.txt`: 248 passed. `tests-backend-full.txt`: 1926 passed, same 20 baseline failures, zero new failures.
- `attempt-1/`: API-limit harness failure, followed by normal cleanup.
- `attempt-2/`: complete worker run; raw accented phrase probes missed. Expectations unchanged.
- `attempt-3/`: complete run with ASCII phrase selection and actual hybrid vector signals.
- Root outputs: final run after separating the mandatory worker extractor from the unchanged legacy extraction API.

## Reproduction (DEV writes; explicit authorization required)

From backend, with canonical DEV configuration and an authorized active admin membership in `breslov_e2e`:

```sh
uv run python ../../data/reports/breslov/region-quarantine-worker-e2e-v1/prepare_fixtures.py --run-id UNIQUE_RUN_ID
uv run python ../../data/reports/breslov/region-quarantine-worker-e2e-v1/run_e2e.py
```

Archive evidence before rerunning. Fresh run metadata gives unique source hashes; it never changes expected GOOD/BAD labels. The worker child receives only scoped E2E enablement, exact authorized fixture hash and auto-migrate=false. No PostgreSQL/Milvus/LiteLLM lifecycle action or migration is performed. Original PDF and DejaVuSans font must be locally available; fixture binaries are ignored, hashes and generator are versioned.

Cleanup intentionally retains normal controlled upload/job/attempt audit records, but removes controlled document/text/page/chunk/embedding/vector/source artifacts. Existing corpus snapshots are identical. No full C reingest or production action occurred.
