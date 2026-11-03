# Foundation V2 publication attempt

**FAIL — no commit/push.** Direct rollback rejects the old INACTIVE generation.

See [REPORT.md](REPORT.md), [rollback-results.json](rollback-results.json) and [final-validation.json](final-validation.json).

Reproduce offline:

```bash
cd SrvRestAstroLS_v1/backend
PYTHONPATH=. .venv/bin/python ../../data/reports/breslov/parallel-generation-foundation-v2-publication-v1/reproduce_rollback.py
```

Expected current exit: 1 (contract defect reproduced). No database or vector service access.

Inventory/hash scripts are attempt-local evidence tools, not production code. Do not rerun capture_inventory.py over this attempt: that would replace its original snapshots.
