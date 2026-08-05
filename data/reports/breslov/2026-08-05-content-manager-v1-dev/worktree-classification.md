# Worktree classification — continuation baseline

HEAD inicial: `95e360a74d1c431cb62647e4ea6f82fde1819482`.

## Content Manager related

| Path | Class | Decision |
|---|---|---|
| `backend/modules/library/content_manager.py` | implementation | Hardened; retain. HTTP service still lacks real pipeline. |
| `backend/modules/library/content_manager_schemas.py` | contract | Hardened; retain and tested. |
| `backend/modules/library/content_manager_state.py` | implementation | New canonical graph; retain and tested. |
| `backend/modules/library/content_manager_repository.py` | repository | New claim/lease/recovery SQL; retain and source-audited. |
| `backend/modules/library/content_manager_worker.py` | orchestrator | New durable worker contract; retain and unit-tested. No concrete pipeline yet. |
| `backend/modules/library/routes.py` | HTTP/security | Tenant-scoped changes; retain; full backend tests pass. |
| `backend/core/config.py`, `backend/globalVar.py` | configuration | Typed limits/lease values; retain. |
| `backend/db/migrations/041_*` | migration | New hardening schema; dry-run in rolled-back PG transaction passed; not applied. |
| `backend/tests/test_content_manager_orchestration.py` | tests | New; 40 focused tests pass. |
| `backend/scripts/audit_pdf_upload_ingestion_console_v1.py` | audit | Updated read-only audit; correctly remains BLOCKED. |
| `astro/src/components/admin/ContentManager.svelte`, `astro/src/pages/admin/content.astro` | UI baseline | Tracked and unchanged in this continuation; incomplete premium UX. |
| `docs/adr/ADR-022-*`, `docs/breslov/page-first-*`, `docs/status_actual.md`, this report | documentation | Update with partial hardening and current blockers. |

## Pre-existing unrelated changes — preserved and excluded

- Modified frontend public configuration/layout: `astro/src/components/global.js`, `global.test.ts`, `layouts/PublicLayout.astro`.
- Modified backend regression: `backend/tests/test_simple_research_rag.py`.
- Modified manual documentation and architecture: `docs/manual-dev-pro-configuration.md`, `docs/adr/ADR-013-*`, `lat.md/frontend-implementation-policy.md`.
- Modified historical screenshots under the 2026-07-16 and 2026-07-26 reports.
- Untracked social assets and rendering scripts under `astro/public/` and `astro/scripts/`.
- Untracked historical probes, backend-generated reports and report trees dated 2026-07-09 through 2026-07-31.

These files were neither restored nor staged. Generated `__pycache__`, `.dev-logs` and `.dev-pids` remain ignored operational artifacts.

## Commit allowlist

Only the explicit Content Manager paths listed in the first table are eligible. No `git add .` is used.
