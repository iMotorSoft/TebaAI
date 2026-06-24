# Status actual - TebaAI Runtime

Objetivo: `desarrollo`

Ultima actualizacion: 2026-06-24

## Estado general

Bootstrap tecnico completado. Frontend actualizado a Astro 7 con Tailwind CSS 4
+ DaisyUI 5. Backend con psycopg 3, pymilvus 2.6.15 y litellm 1.89.3.

## Acciones realizadas

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

- `pnpm check`: 0 errors, 0 warnings.
- `pnpm build`: 1 page, daisyUI 5.5.23, build 1.23s.
- `uv sync`: 36 packages, PASS.
- `uv run -- python -c "import psycopg; from psycopg import AsyncConnection"`:
  PASS.
- `uv run -- python -c "import pymilvus; print(pymilvus.__version__)"`: 2.6.15.
- `uv run -- python -c "from litellm import completion, acompletion"`: PASS.

## Pendientes recomendados

- Conectar backend con PostgreSQL via psycopg async pool.
- Conectar backend con Milvus 2.6.
- Integrar LiteLLM para llamadas a modelos LLM.
- Definir primera vertical Breslov en fase posterior.

## Notas de seguridad

- No se tocaron servicios externos.
- No se cargaron corpus reales.
- No se imprimieron ni leyeron secretos.
