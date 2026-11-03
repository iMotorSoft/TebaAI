# Gateway FK order remediation V1

**PASS, limited to gateway registration ordering.**

See [REPORT.md](REPORT.md), [gate.json](gate.json) and [final-validation.json](final-validation.json).

- Only `page_first_gateway.py` product ordering changed; two direct tests added.
- Real synthetic PostgreSQL: immediate parent FKs, retry, transaction failures, lifecycle and cleanup verified.
- Full backend: 1985 PASS / 20 known FAIL / 13 known JSONB fixture ERROR; no new failing/error node IDs.
- Foundation remains unpublished; C untouched; no commit/push.
- Next permitted gate: publication preflight remediation V2, not publication or C ingestion.
