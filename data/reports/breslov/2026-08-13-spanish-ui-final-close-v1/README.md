# Spanish UI Final Close V1 — 2026-08-13 (DEV)

## Estado: BLOCKED (backend full suite — PostgreSQL connectivity)

El cierre funcional y visual de la UI pública **Español V1** está completo y
verificado. El único bloqueo es **ambiental**: la suite backend completa no
puede ejecutarse porque PostgreSQL no acepta conexiones nuevas.

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
| `TEBAAI_BRESLOV_PUBLIC_ENTRY_AND_CONTENT_MANAGER_V2_COMMITTED_DEV_READY` | **BLOCKED** (backend full suite) |

## Commits

- `877da00` feat(breslov): integrate Content Manager library navigation
- `a7b6e46` feat(breslov): add module-aware public entry flow
- `48ace56` feat(breslov): add premium module selector modal
- docs(breslov): close Spanish public entry UX gates (este cierre)

## Evidencia backend BLOCKED

- Test aislado (fails alone):
  `test_hebrew_fts_builder.py::TestTSQueryPostgreSQL::test_to_tsquery_or_correct`
  → `psycopg_pool.PoolTimeout: couldn't get a connection after 10.00 sec`.
- Conexión directa:
  `psycopg.AsyncConnection.connect(host=localhost:5432)`
  → `ConnectionTimeout: connection timeout expired` (::1 y 127.0.0.1).
- Focalizado Content Manager views: 7 PASS.
- Histórico de esta sesión: 1585 PASS más temprano (antes de la degradación de
  PostgreSQL). El código backend **no cambió** con estos commits de UI.

No se reinició PostgreSQL (prohibido). Causa: ambiental.

## Screenshots ES

`screenshots/home-modal-es-1440.png`, `-1024`, `-768`, `-680`,
`-390x844`, `-390x667`. Sin capturas EN/HE/RTL (not in scope).
