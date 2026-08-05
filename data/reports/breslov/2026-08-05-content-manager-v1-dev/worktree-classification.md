# Worktree classification — PageFirstPipeline continuation

HEAD inicial real: `8b64455fd3e50951b665e0212a5266a1c28bd156`.

## Files in this cycle

| Paths | Classification | Purpose / state / tests |
|---|---|---|
| `backend/modules/library/page_first_pipeline.py` | pipeline reusable | Typed document-agnostic contract, PyMuPDF4LLM physical pages, Unicode/ligatures, conservative headings/footnotes/references and stage orchestration. Unit and real E2E PASS. |
| `backend/modules/library/page_first_gateway.py` | pipeline adapters + reconciliation | PostgreSQL manifests, chunks/embeddings, isolated attempt-keyed Milvus adapter and exact reconciliation. Unit and real E2E PASS. |
| `backend/modules/library/content_manager_cleanup.py` | cleanup | Milvus-first manifest compensation, exact PG IDs, audit events and repeat-safe outcomes. Unit and real twice-run cleanup PASS. |
| `backend/modules/library/content_manager_runtime.py` | worker wiring | Psycopg store, pipeline result/diagnostic and failure compensation. Real worker PASS. |
| `content_manager_worker.py`, `content-worker-dev.sh` | DEV runner | Explicit DEV/E2E guards, PID/log ownership and one isolated worker. Active at close. |
| `prepare_content_manager_e2e_scope.py` | isolation setup | Explicit dry-run/apply for `breslov_e2e`; primary is never updated. |
| `generate_content_manager_e2e_fixture.py` | fixture generator | Generates an authorized temporary 3-page ES/HE/empty PDF; PDF is excluded. |
| `core/config.py`, `globalVar.py` | configuration | Default-off E2E flag, exact scope/collection/hash and worker polling. |
| `migration 041` | migration | Reviewed before first application; adds cleanup audit and `ingestion_failed`, then applied with the official runner. |
| existing Content Manager modules/routes/schemas/audit | existing orchestrator integration | Durable design preserved; minimally extended for real stages, diagnostics and E2E routing. |
| `tests/test_page_first_pipeline.py`, `test_content_manager_cleanup.py`, `test_content_manager_e2e_isolation.py` | tests | Pipeline/reconciliation/cleanup/isolation coverage; focused 61 PASS, full backend 1555 PASS. |
| current ADR/status/conventions/report | documentation/report | Records reproducible gates and evidence. |

## Existing scripts inventoried, not copied into the worker

The `ingest_*page_first*.py` scripts mix reusable page concepts with hardcoded document IDs, titles, paths, page ranges, edition IDs and direct SQL. Only conservative document-agnostic concepts were extracted. Existing scripts were preserved unchanged and the worker never invokes shell or subprocess.

## Pre-existing unrelated files preserved and excluded

- Modified `astro/src/components/global.js`, `global.test.ts`, `layouts/PublicLayout.astro`.
- Modified `backend/tests/test_simple_research_rag.py`.
- Modified `docs/manual-dev-pro-configuration.md`, `docs/adr/ADR-013-*`, `lat.md/frontend-implementation-policy.md`.
- Modified historical screenshots under 2026-07-16 and 2026-07-26 reports.
- Untracked social assets/rendering scripts, historical backend probes and report trees dated 2026-07-09 through 2026-07-31.

They were not restored, edited or staged. PID files, logs, local E2E settings and generated PDFs are runtime artifacts and are excluded from commits. No `git add .` is used.
