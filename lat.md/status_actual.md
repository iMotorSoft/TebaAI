# Status actual - TebaAI lat.md

Objetivo: `arquitectura-viva`

Ultima actualizacion: 2026-06-24

## Estado general

Bootstrap inicial completado. Se replicaron las ramas Git desde Team360 y se
actualizaron todas las dependencias frontend/backend a latest.

## Acciones realizadas

### 2026-06-24 - Convencion de ramas Git y AGENTS.md

- Se agrego la seccion `Git Branch Convention` en `AGENTS.md` replicando el
  modelo de Team360: `main` estable, `feature/console-backend-core` para
  desarrollo activo, `feature/knowledge-ingestion-service` para knowledge,
  `docs/knowledge-documents-foundation` para documentacion y
  `ux/team360-console-design-handoff` para UX.
- Se crearon y empujaron las 4 ramas desde `main`.
- El proyecto queda en `feature/console-backend-core` como rama de trabajo
  activo.

### 2026-06-24 - Frontend Astro actualizado a v7

- `astro`: 6.4.2 -> 7.0.2
- `@astrojs/svelte`: 8.1.2 -> 9.0.0
- `svelte`: 5.56.0 -> 5.56.4
- `@playwright/test`: 1.60.0 -> 1.61.1
- `@types/node`: 26.0.0 -> 26.0.1
- Agregados: `tailwindcss` 4.3.1, `@tailwindcss/vite` 4.3.1, `daisyui` 5.5.23
- Creado `src/layouts/Layout.astro` con import de `app.css` (tailwind + daisyui)
- `astro.config.mjs`: agregado plugin `@tailwindcss/vite`
- `pnpm build` y `pnpm check`: ambos PASS sin errores.

### 2026-06-24 - Backend Python actualizado

- Python: 3.12.3 -> 3.12.13 (via `uv python install`)
- Agregados: `psycopg` 3.3.4, `psycopg-binary` 3.3.4, `psycopg-pool` 3.3.1
- Agregado: `pymilvus` 2.6.15 (compatible con Milvus 2.6 server)
- Agregado: `litellm` 1.89.3 (SDK para LiteLLM proxy)
- Todas las dependencias verificadas funcionales con `uv run -- python -c`.

## Validacion

- `pnpm check`: 0 errors, 0 warnings.
- `pnpm build`: 1 page built in 1.23s, daisyUI 5.5.23 activo.
- `uv run -- python -c "import psycopg; ..."`: PASS con AsyncConnection.
- `uv run -- python -c "import pymilvus; ..."`: PASS version 2.6.15.
- `uv run -- python -c "from litellm import completion, acompletion"`: PASS.
- `git diff --check`: PASS.

## Pendientes recomendados

- Definir la primera vertical Breslov en una fase posterior.
- Conectar backend con PostgreSQL via psycopg pool y configurar DSN.
- Conectar backend con Milvus y LiteLLM en fase de integracion.

## Notas de seguridad

- No se cargaron corpus reales ni archivos pesados.
- No se imprimieron ni leyeron secretos.
- No se iniciaron, detuvieron ni reiniciaron servicios externos.
