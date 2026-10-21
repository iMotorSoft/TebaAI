# C controlled reingest plan V1

**PLAN / INVENTORY / PREFLIGHT ONLY — no C reingestion.**

Planning PASS; execution NOT READY. Required next gate: `TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1`.

- [Report and current C identity/history/gaps](REPORT.md)
- [Future execution phases 0–9](C_CONTROLLED_REINGEST_EXECUTION_PLAN.md)
- [Semantic reconciliation and exact PASS/FAIL contract](C_RECONCILIATION_CONTRACT.md)
- [Rollback runbook](C_ROLLBACK_RUNBOOK.md)
- [Snapshot contract and read-only queries](current-c-snapshot-contract.md)
- [Cutover design](cutover-design.md)
- [Post-cutover verification](post-cutover-validation-plan.md)
- [Separate ingestion/cutover GO checklists](future-go-no-go-checklist.md)
- [Capability matrix](generation-capability-matrix.json)
- [Recommendation](recommendation.md)

Evidence: current-c-*.json summaries; postgres-before/after.json, milvus-before/after.json, source-before/after.json raw sanitized inventories; queries-before/after.json exact bound SELECTs; historical-report-index.json; worktree-before.json; gate.json; focused-tests*.txt; final-validation.json; secret-scan.json; git-diff-check.txt. git-close.json, if present, records verified Git publication (post-commit evidence, not part of that commit).

Safe inventory command (no worker/lifecycle, local DEV guards, server-enforced read-only):

```bash
cd SrvRestAstroLS_v1/backend
.venv/bin/python ../../data/reports/breslov/c-controlled-reingest-plan-v1/inventory_readonly.py before
```

It only writes local evidence files and must not be confused with an ingestion command. Do not overwrite sealed evidence for a future execution: use a new report directory/version. Offline regression command:

```bash
cd SrvRestAstroLS_v1/backend
uv run --no-sync pytest ../../data/reports/breslov/c-controlled-reingest-plan-v1/test_plan_contracts.py tests/test_region_publication.py -q
```

Git inventory preserved preexisting work; no production code or current C data changed. Original PDF available and hash verified, but OLD durable source reference missing. No normal-retrieval isolation or atomic switch claim is made for today's implementation.
