# Spanish UI Final Close V1 — 2026-08-13 (DEV)

## Estado: BLOCKED (backend full suite — connection timeout)

El cierre funcional y visual de la UI pública **Español V1** está completo y
verificado. La suite backend completa no pudo ejecutarse: la conexión a
PostgreSQL desde el proceso de test agota el tiempo de espera (`ConnectionTimeout`
en conexión directa, `PoolTimeout` en el test FTS aislado). **Causa raíz no
establecida.**

## Scope contract

| Aspecto | Resultado |
|---|---|
| UI Español | IN SCOPE / PASS |
| UI Inglés | NOT IN SCOPE |
| UI Hebreo | NOT IN SCOPE |
| RTL de UI | NOT IN SCOPE |
| Corpus / Research content | ES + EN + HE preservado |
| UI i18n futura | `PUBLIC_UI_I18N_ES_EN_HE` (fase futura) |

## Gates

| Gate | Resultado |
|---|---|
| `TEBAAI_BRESLOV_PUBLIC_ENTRY_ES_VISUAL_FINAL_V1_PASS` | **PASS** |
| `TEBAAI_BRESLOV_UI_SCOPE_RECONCILIATION_V1_PASS` | **PASS** |
| `TEBAAI_BRESLOV_UI_ACCUMULATED_WORKTREE_RECONCILIATION_V1_PASS` | **PASS** |
| `TEBAAI_BRESLOV_PUBLIC_ENTRY_AND_CONTENT_MANAGER_V2_COMMITTED_DEV_READY` | **BLOCKED** (backend full) |

## Provenance de validación

- **Post-commit**: `pnpm check` (0), Vitest (109), build (9 páginas),
  Content Manager views focalizado (7 PASS), `lat check`, `git diff --check`.
- **Pre-commit (no re-ejecutado post-commit)**: Playwright modal (12×3=36),
  focalizado (54), auth/permissions/Content Manager UI specs.
- **Bloqueado**: backend full suite (connection timeout, causa raíz no
  establecida). Histórico de la sesión: 1585 PASS más temprano hoy.

## Commits

- `877da00` feat(breslov): integrate Content Manager library navigation
  (incluye código backend Content Manager: read-model + tests)
- `a7b6e46` feat(breslov): add module-aware public entry flow (solo frontend)
- `48ace56` feat(breslov): add premium module selector modal (solo frontend)
- `6a64a66` docs(breslov): close Spanish public entry UX gates
- (corrective docs commit: provenance)

## Evidencia backend BLOCKED

- Test aislado (fails alone):
  `test_hebrew_fts_builder.py::TestTSQueryPostgreSQL::test_to_tsquery_or_correct`
  → `psycopg_pool.PoolTimeout: couldn't get a connection after 10.00 sec`.
- Conexión directa:
  `psycopg.AsyncConnection.connect(host=localhost:5432)`
  → `ConnectionTimeout: connection timeout expired` (::1 y 127.0.0.1).

No se reinició PostgreSQL (prohibido). Causa raíz no determinada.

## Screenshots ES (PNG verificado)

`screenshots/home-modal-es-1440.png`, `-1024`, `-768`, `-680`,
`-390x844`, `-390x667` (todos PNG válidos). Sin capturas EN/HE/RTL (not in scope).
