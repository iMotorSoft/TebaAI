# Worktree Reconciliation V1 — 2026-08-06

Gate: `TEBAAI_WORKTREE_RECONCILIATION_V1_DEV_READY`

## Resumen

- Rama: `feature/console-backend-core` · HEAD inicial: `a6d3aca379d5872d32ecbc0450c9d74a557977f3`
- 17 tracked modificados, 0 staged, 303 untracked. `git diff --check` PASS.
- Ningún secreto (scan `api_key|secret|password|token|Bearer` → solo falsos positivos).
- Ningún archivo ajeno eliminado; `backend/data/` (13 JSON runtime) conservado en disco y excluido del commit.
- Probes Milvus verificados read-only por defecto.

## Clasificación

- **A/B — config HTTP**: `global.js`, `global.test.ts`, `manual-dev-pro-configuration.md`, `lat.md/frontend-implementation-policy.md`. El contrato anterior (`false→127.0.0.1:7008, true→/api`) queda superseded por `/api` same-origin, cuya base (proxy Astro) ya está commiteada en `astro.config.mjs`. Cambio coherente y documentado.
- **C — branding**: `PublicLayout.astro` (links favicon), `public/favicon*`, `apple-touch-icon.png`, `public/images/breslov-social-card.png` (1200×630), `scripts/render-social-assets.cjs`.
- **D — test**: `test_simple_research_rag.py` (esperado `ev-71b37371035d805f` alineado a evidence ID v2).
- **E — documentación**: `docs/adr/ADR-013` (sección Corpus reconciliation).
- **F — reportes**: 282 archivos de evidencia en `data/reports/breslov/` (14 MB) + 10 capturas PNG modificadas.
- **G — probes**: `backend/scripts/milvus_v2_isolated_status_probe.py`, `milvus_operational_closure_probe.py`.
- **H — runtime excluido**: 13 JSON en `SrvRestAstroLS_v1/backend/data/reports/...` (salida cruda de probes).

## Commits (5, sin push)

1. `chore(tebaai): always use same-origin /api and document DEV/PRO proxy` (4)
2. `chore(tebaai): add favicons and social card assets` (7)
3. `test(breslov): align primary evidence id expectation to v2` (1)
4. `docs(breslov): record corpus reconciliation cases in ADR-013` (1)
5. `docs(breslov): commit pending report evidence and read-only probes` (294)

## Estado final exigido por el gate

- [x] todos los tracked clasificados
- [x] todos los untracked relevantes clasificados
- [x] sin secretos
- [x] runtime excluido
- [x] posibles commits delimitados
- [x] `git diff --check` PASS
- [x] ningún cambio ajeno eliminado

Evidencia: `baseline.json`, `tracked-classification.md`, `untracked-classification.md`, `commit-candidates.json`, `excluded-files.json`, `validation-results.json`.
