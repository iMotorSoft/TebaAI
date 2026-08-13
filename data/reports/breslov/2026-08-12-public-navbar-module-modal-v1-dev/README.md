# Public Navbar Module Modal V1 — Reporte de desarrollo (DEV)

Fecha: 2026-08-12
Rama: `feature/console-backend-core`
HEAD inicial = HEAD final: `a12229cf3046955e98eab94e99375c0d20fb1775` (sin commit; no push)
Construido sobre los cambios no commiteados de UX Integration V2 + Module Entry V1.

## Estado

PASS

## Gates

| Gate | Estado |
|---|---|
| `TEBAAI_PUBLIC_NAVBAR_MODULE_MODAL_V1_DEV_READY` | PASS |
| `TEBAAI_PUBLIC_MODULE_MODAL_ACCESSIBILITY_V1_DEV_READY` | PASS |
| `TEBAAI_PUBLIC_MODULE_MODAL_PREMIUM_UX_V1_PASS` | PASS |
| `TEBAAI_PUBLIC_MODULE_ENTRY_MODAL_V1_DEV_READY` | PASS |

## Cambios

- `src/components/breslov/ModuleModal.svelte` (nuevo): modal `<dialog>` nativo,
  focus trap manual, Escape, backdrop, focus restore, consume moduleRegistry.
- `src/components/breslov/HomeHeader.astro`: «Ingresar» → `ModuleModal`.
- `src/components/breslov/MobileMenu.svelte`: «Ingresar» → `ModuleModal`.
- `src/assets/investigative-home.css`: estilos modal + resets de botón.
- `src/components/modules/moduleRegistry.ts`: reutilizado (sin cambios).

## Modal

- Ingresar abre modal; Investigación/Edición visibles; Administración no.
- Cierre: botón Cerrar, Escape, click fuera (backdrop).
- Focus: trap manual + restore a «Ingresar».

## Auth

- Investigación → `/research` (anónimo: `/login?next=/research`).
- Edición → `/admin/content` (anónimo: `/login?next=/admin/content`).
- `resolveSafePostLoginDestination` reutilizado; allowlist intacta.

## Permisos

- admin/editor → Edición directa; viewer → denegado (guard existente).
- Sin lógica de permisos duplicada en el modal.

## Accesibilidad

- role=dialog + aria-modal (nativo), aria-label.
- keyboard PASS, focus trap PASS, focus restore PASS, Escape PASS.
- contrast PASS (navy/ivory/gold), touch targets, reduced-motion (heredado).

## Responsive

- 1440×900 / 1024×768 PASS; 390×844 PASS (cards apiladas, sin overflow).

## Tests

| Control | Resultado |
|---|---|
| Vitest | 109 PASS |
| `pnpm check` | 0 errores |
| Build | 9 páginas PASS |
| Playwright `public-navbar-module-modal` | 8/8 |
| Playwright regresión (home/login/module-entry/auth/permissions) | 28/28 |
| Backend completo (env limpio) | 1585 PASS, 94 warnings preexistentes |
| `lat check` | PASS |
| `git diff --check` | PASS |

## Regresiones

- Home premium preservada; sección Investigación/Edición inferior preservada.
- Auth intended destination preservado; Research y Content Manager preservados.
- Core (pipeline/worker/Milvus/embeddings/cleanup/upload) no tocado.

## Datos / Servicios

- Ningún documento creado/eliminado; corpus no reingerido; Milvus no reindexado.
- PostgreSQL/Milvus/LiteLLM no reiniciados; backend/Astro/worker DEV activos.
- `.bashrc` no modificada; producción no tocada; push no realizado.
