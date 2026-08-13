# Content Manager UX Integration V2 — Reporte de desarrollo (DEV)

Fecha: 2026-08-12
Rama: `feature/console-backend-core`
HEAD inicial: `a12229cf3046955e98eab94e99375c0d20fb1775`

## Estado

PASS — los tres gates de fase y el gate general quedan READY.

## Gates

| Gate | Estado |
|---|---|
| `TEBAAI_CONTENT_MANAGER_UNIFIED_NAVIGATION_V1_DEV_READY` | PASS |
| `TEBAAI_CONTENT_MANAGER_LIBRARY_DASHBOARD_V1_DEV_READY` | PASS |
| `TEBAAI_CONTENT_MANAGER_TEST_DATA_VISIBILITY_V1_DEV_READY` | PASS |
| `TEBAAI_CONTENT_MANAGER_UX_INTEGRATION_V2_DEV_READY` | PASS |

Preservados (no degradados):

- `TEBAAI_CONTENT_MANAGER_INGESTION_ORCHESTRATOR_V1_DEV_READY`
- `TEBAAI_PDF_UPLOAD_INGESTION_CONSOLE_V1_DEV_READY`
- `TEBAAI_CONTENT_MANAGER_PREMIUM_UX_V1_PASS`
- `TEBAAI_CONTENT_MANAGER_V1_DEV_READY`

## Cambios

### Backend (read model)

- `backend/modules/library/content_manager_schemas.py`: `ContentSummary`,
  `DocumentListItem`, `DocumentListResponse`.
- `backend/modules/library/content_manager.py`: `get_content_summary`,
  `list_content_documents`, `_operational_state`, `_e2e_clause`.
- `backend/modules/library/routes.py`: `GET /admin/content/summary`,
  `GET /admin/content/documents`.
- `backend/ls_iMotorSoft_Srv01.py`: registro de las dos rutas nuevas.
- `backend/tests/test_content_manager_document_views.py`: 7 tests.

### Frontend

- `astro/src/components/admin/contentManagerClient.ts`: tipos y clientes
  `getContentSummary` / `listContentDocuments`.
- `astro/src/components/admin/ContentManager.svelte`: vista biblioteca
  documental (indicadores, tabla/cards, toggle de prueba, acción Abrir).
- `astro/src/components/research/ResearchWorkspace.svelte`: enlace
  «Gestor de Contenidos» (header + panel móvil) para admin/editor.
- `astro/src/assets/content-manager.css`: badge E2E, barra de filtros/toggle.

### Playwright

- Actualizados: `content-manager-captures`, `content-manager-mobile`,
  `content-manager-rtl`, `content-manager-premium` (fixtures document-centric).
- Nuevos: `research-content-manager-navigation`, `content-manager-library`,
  `content-manager-e2e-visibility`.

## Navegación

- admin `/research` → ve «Gestor de Contenidos» → `/admin/content` (PASS)
- `/admin/content` → «Investigación» → `/research`, misma sesión (PASS)
- guest `/research` → NO ve «Gestor de Contenidos» (PASS)
- `/admin/content` sin sesión → redirige a `/login` (PASS, spec premium)

## Biblioteca

Contadores reales de DEV (scope `breslov_primary`, E2E excluido por defecto):

- total documentos: 23
- ready: 8
- test_candidate: 14
- processing: 1
- with_warnings: 0
- failed: 0
- idiomas: es 13, he 9, en 1

## Datos E2E

- Método de identificación: `knowledge_scope_code == breslov_e2e`.
- Exclusión por defecto: backend (cláusula SQL) + frontend (toggle OFF).
- Filtro explícito: `include_test_data=true` / «Mostrar datos de prueba».
- Badge visual: `E2E`.
- Registros eliminados: 0.

## Validaciones

| Control | Resultado |
|---|---|
| Backend focalizado | 55 PASS |
| Backend completo | 1585 PASS, 94 warnings preexistentes |
| Frontend `pnpm check` | 0 errores |
| Vitest | 94 PASS |
| Build | 9 páginas PASS |
| Playwright navegación | 3/3 PASS |
| Playwright biblioteca | 2/2 PASS |
| Playwright visibilidad E2E | 1/1 PASS |
| Playwright mock (captures/mobile/rtl) | 7/7 PASS |
| `lat check` | PASS |
| `git diff --check` | PASS |

## Regresión E2E real (nota ambiental)

`content-manager-premium.spec.ts` (backend real + worker) exige
`PUBLIC_CONTENT_MANAGER_SCOPE=breslov_e2e` en el server Astro y el env
`.env.backend-dev.local` cargado en el proceso de cleanup (precedente ya
documentado en `status_actual.md`). Con el env E2E correcto:

- wizard five-stage: PASS
- permissions (2): PASS

El spec de retry depende de que el fixture cancelado sea localizable entre los
datos E2E acumulados; los leftovers `breslov_primary` «Fuente Premium UX
Playwright» en estado `queued` (artefacto de corridas previas con scope por
defecto) contaminan el listado y se documentan como huérfanos — no se
repararon (pertenecen al procedimiento de cleanup; prompt §29, §68).

## Datos existentes

- Ningún documento real eliminado.
- Ningún documento E2E eliminado.
- Corpus no reingerido; embeddings no recalculados; Milvus no reindexado.
- PostgreSQL, Milvus y LiteLLM no reiniciados.

## Servicios

- PostgreSQL / Milvus / LiteLLM: no reiniciados.
- backend DEV: activo (`127.0.0.1:7008`).
- Astro DEV: activo (`127.0.0.1:3008`, scope por defecto `breslov_primary`).
- worker DEV: activo (scope aislado `breslov_e2e`).
- `.bashrc`: no modificada. Producción: no modificada. Push: no realizado.
