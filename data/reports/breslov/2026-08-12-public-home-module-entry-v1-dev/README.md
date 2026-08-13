# Public Home Module Entry V1 — Reporte de desarrollo (DEV)

Fecha: 2026-08-12
Rama: `feature/console-backend-core`
HEAD inicial = HEAD final: `a12229cf3046955e98eab94e99375c0d20fb1775` (sin commit; no push)
Fase construida sobre los cambios no commiteados de UX Integration V2.

## Estado

PASS — los cinco gates quedan READY/PASS.

## Gates

| Gate | Estado |
|---|---|
| `TEBAAI_PUBLIC_HOME_MODULE_ENTRY_V1_DEV_READY` | PASS |
| `TEBAAI_AUTH_INTENDED_DESTINATION_V1_DEV_READY` | PASS |
| `TEBAAI_MODULE_ENTRY_PERMISSION_FLOW_V1_DEV_READY` | PASS |
| `TEBAAI_PUBLIC_HOME_MODULE_ENTRY_PREMIUM_UX_V1_PASS` | PASS |
| `TEBAAI_BRESLOV_MODULE_ENTRY_FLOW_V1_DEV_READY` | PASS |

Preservados: Content Manager V1, UX Integration V2 (navegación ↔, biblioteca,
datos E2E ocultos), Research.

## Cambios

### Frontend

- `src/components/modules/moduleRegistry.ts` (nuevo): registro de módulos +
  `resolveSafePostLoginDestination` + `findModuleByDestination` +
  `roleCanAccessModule`.
- `src/components/modules/moduleRegistry.test.ts` (nuevo): 15 tests de unidad.
- `src/components/breslov/ModuleEntry.svelte` (nuevo): entrada session-aware
  con `next`.
- `src/components/breslov/ModuleSelector.astro` (nuevo): sección de dos cards.
- `src/components/breslov/SessionAwareAccess.svelte`: prop `next` opcional.
- `src/components/breslov/HeroSection.astro`: CTA research con `next=/research`.
- `src/components/auth/LoginForm.svelte`: lee `next`, valida, autoriza, UX 403.
- `src/pages/index.astro` y `breslov.astro`: importan ModuleSelector.
- `src/assets/investigative-home.css`: cards + corrección contraste kicker.

### Backend

Ningún cambio. Las rutas/read-model de V2 se preservan.

## Home

- Investigación y Edición visibles antes de auth (desktop + móvil).
- Administración NO visible.
- Estética premium preservada (navy/ivory/gold, serif/sans).
- Accesibilidad: corrección de contraste `.section-kicker` (`#76500b` en fondos
  claros, `gold-400` en navy).

## Auth

- Mecanismo: `?next=` con `resolveSafePostLoginDestination` (allowlist exacta
  `/research`, `/admin/content`).
- Fallback directo `/login`: `/research` histórico.
- Error de login conserva `next`.
- Open redirect bloqueado (externas, protocol-relative, scheme, backslash,
  codificadas).

## Permisos

| Rol | Investigación | Edición |
|---|---|---|
| admin | sí | sí |
| editor | sí | sí |
| viewer | sí | no (403 legible) |
| guest/viewer | sí | no (403 legible) |
| anonymous | → login | → login |

## Flujos

- Home → Investigación → Login → `/research` (PASS)
- Home → Edición → Login → `/admin/content` (PASS)
- autenticado → Investigación → directo (PASS)
- autenticado → Edición → directo según permisos (PASS)
- viewer → Edición → denegado, sesión viva (PASS)

## Tests

| Control | Resultado |
|---|---|
| Vitest | 109 PASS (15 nuevos) |
| `pnpm check` | 0 errores |
| Build | 9 páginas PASS |
| Playwright home module entry | 5/5 |
| Playwright auth destination | 7/7 |
| Playwright permissions | 4/4 |
| Playwright regresión (home/login/V2) | 26/26 |
| Backend completo | 1585 PASS, 94 warnings preexistentes |
| `lat check` | PASS |

Nota: la corrida backend requiere entorno limpio (`TEBAAI_AUTH_ENABLED` sin
exportar); un `source .env.backend-dev.local` previo filtra esa variable y hace
fallar `test_global_var.py::test_auth_exports` (espera el default `False`). No
es regresión de código.

## Datos

- Ningún documento creado ni eliminado en esta fase (solo navegación/auth).
- Corpus no reingerido; embeddings no recalculados; Milvus no reindexado.

## Servicios

- PostgreSQL / Milvus / LiteLLM no reiniciados.
- backend DEV activo, Astro DEV activo, worker DEV activo.
- `.bashrc` no modificada; producción no modificada; push no realizado.
