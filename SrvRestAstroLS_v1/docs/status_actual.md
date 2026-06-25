# Status actual - TebaAI Runtime

Objetivo: `desarrollo`

Ultima actualizacion: 2026-06-25

## Estado general

Bootstrap tecnico completado. Frontend actualizado a Astro 7 con Tailwind CSS 4
+ DaisyUI 5. Backend con psycopg 3, pymilvus 2.6.15 y litellm 1.89.3.

Esta es la bitacora tecnica principal del runtime TebaAI. Agrupa backend,
frontend Astro/Svelte e integracion frontend/backend para evitar bitacoras
paralelas prematuras.

## Alcance de esta bitacora

- Backend Litestar, dependencias Python, entrypoint, launchers y validaciones
  tecnicas.
- Frontend Astro/Svelte, build, check, rutas, UI y configuracion publica.
- Integracion frontend/backend, URLs, puertos, contratos HTTP, proxy local y
  validaciones Playwright.
- No cubre decisiones largas de arquitectura, que viven en `lat.md/`, ni ADRs
  resumidos, que viven en `docs/adr/`.

## Backend

- Entry point canonico:
  `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`.
- ASGI object: `app`.
- Puerto local backend: `7008`.
- Dependencias instaladas para fases futuras: `psycopg`, `psycopg-pool`,
  `pymilvus` y `litellm`.
- PostgreSQL, Milvus y LiteLLM siguen como servicios externos permanentes; esta
  fase no crea conexiones ni gestiona servicios.

## Frontend Astro

- Astro/Svelte vive en `SrvRestAstroLS_v1/astro/`.
- Puerto local Astro: `3008`.
- Stack actual: Astro 7, Svelte 5, Tailwind CSS 4 y DaisyUI 5.
- La configuracion publica frontend debe mantenerse separada de secretos.
- La fachada frontend comun debe ubicarse en
  `SrvRestAstroLS_v1/astro/src/components/global.js`, siguiendo el uso real de
  Team360.

## Integracion frontend/backend

- URL backend local esperada: `http://127.0.0.1:7008`.
- URL Astro local esperada: `http://127.0.0.1:3008`.
- Playwright + Chromium es el gate E2E oficial.
- Browser MCP puede usarse para diagnostico visual, pero no reemplaza tests
  Playwright reproducibles.

## Acciones realizadas

### 2026-06-25 - Convencion de bitacora runtime backend + Astro

- Se formalizo que este archivo es la bitacora tecnica principal del runtime.
- Se agrego alcance explicito para backend, frontend Astro/Svelte e integracion
  frontend/backend.
- Se decidio no crear `backend/status_actual.md` ni `astro/status_actual.md`
  por ahora; se evaluara solo si el volumen tecnico lo justifica.
- Se actualizaron `AGENTS.md`, `.agents/skills/tebaai-project/SKILL.md` y
  `docs/templates/status_actual_template.md` con la convencion general de
  `status_actual.md`.
- No se modifico codigo runtime, dependencias, Docker, `.env`, migraciones ni
  servicios externos.

### 2026-06-24 - Upgrade frontend Astro 7 + Tailwind + DaisyUI

- `astro`: 6.4.2 -> 7.0.2
- `@astrojs/svelte`: 8.1.2 -> 9.0.0
- `svelte`: 5.56.0 -> 5.56.4
- `@playwright/test`: 1.60.0 -> 1.61.1
- `@types/node`: 26.0.0 -> 26.0.1
- Agregados: `tailwindcss` 4.3.1, `@tailwindcss/vite` 4.3.1, `daisyui` 5.5.23
- Creado `src/layouts/Layout.astro` (importa `src/assets/app.css`).
- Creado `src/assets/app.css` con `@import "tailwindcss"` y `@plugin "daisyui"`.
- `astro.config.mjs`: agregado plugin `@tailwindcss/vite`.
- `index.astro`: ahora usa `<Layout>` en vez de HTML directo.

### 2026-06-24 - Upgrade backend Python + librerias

- Python: 3.12.3 -> 3.12.13.
- Agregados: `psycopg` 3.3.4, `psycopg-binary` 3.3.4, `psycopg-pool` 3.3.1.
- Agregado: `pymilvus` 2.6.15 (compatible Milvus 2.6).
- Agregado: `litellm` 1.89.3 (SDK LiteLLM).

### 2026-06-24 - Agentes/Git

- AGENTS.md actualizado con convencion de ramas Git.
- Creadas y pusheadas ramas: `feature/console-backend-core`,
  `feature/knowledge-ingestion-service`, `docs/knowledge-documents-foundation`,
  `ux/team360-console-design-handoff`.

## Validacion

- Para la convencion de `status_actual.md`: `git diff --check` PASS.
- `pnpm check`: 0 errors, 0 warnings.
- `pnpm build`: 1 page, daisyUI 5.5.23, build 1.23s.
- `uv sync`: 36 packages, PASS.
- `uv run -- python -c "import psycopg; from psycopg import AsyncConnection"`:
  PASS.
- `uv run -- python -c "import pymilvus; print(pymilvus.__version__)"`: 2.6.15.
- `uv run -- python -c "from litellm import completion, acompletion"`: PASS.

## Pendientes recomendados

- Usar este archivo como punto unico de cierre para cambios runtime backend,
  Astro e integracion hasta que el volumen justifique bitacoras locales.
- Implementar `SrvRestAstroLS_v1/astro/src/components/global.js` como fachada
  publica frontend cuando llegue la fase de configuracion global.
- Conectar backend con PostgreSQL via psycopg async pool.
- Conectar backend con Milvus 2.6.
- Integrar LiteLLM para llamadas a modelos LLM.
- Definir primera vertical Breslov en fase posterior.

## Notas de seguridad

- No se tocaron servicios externos.
- No se cargaron corpus reales.
- No se imprimieron ni leyeron secretos.
