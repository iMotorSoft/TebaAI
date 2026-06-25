# Status actual - TebaAI lat.md

Objetivo: `arquitectura-viva`

Ultima actualizacion: 2026-06-25

## Estado general

Bootstrap inicial completado. Se replicaron las ramas Git desde Team360 y se
actualizaron todas las dependencias frontend/backend a latest.

## Acciones realizadas

### 2026-06-25 - Convencion de uso de `status_actual.md`

- Se adopto el patron validado en Team360 para TebaAI: usar
  `status_actual.md` como bitacora de cierre, no como diario.
- Se definio `SrvRestAstroLS_v1/docs/status_actual.md` como bitacora tecnica
  principal del runtime, agrupando backend, frontend Astro/Svelte e integracion
  frontend/backend.
- Se aclaro que `lat.md/status_actual.md` queda limitado a arquitectura viva,
  invariantes, politicas canonicas y documentos LAT.
- Se documento que `docs/**/status_actual.md` y `data/**/status_actual.md`
  deben crearse solo para directorios activos con contenido real.
- Se actualizaron `AGENTS.md`, `.agents/skills/tebaai-project/SKILL.md`,
  `docs/templates/status_actual_template.md` y
  `SrvRestAstroLS_v1/docs/status_actual.md`.
- No se modifico codigo runtime, dependencias, servicios externos, Docker,
  `.env`, migraciones ni integraciones.

### 2026-06-25 - Politica de fachada de configuracion global

- Creado `lat.md/global-configuration-facade-policy.md` como documento
  canonico para la relacion entre `.env`, `core/config.py`, `globalVar.py` y
  `global.js`.
- Creado `docs/adr/ADR-002-global-configuration-facade.md` con estado
  `Accepted`.
- Documentado que `globalVar.py` se conserva como fachada estable de
  configuracion comun, sin conexiones, pools, clientes, llamadas de red ni
  side effects de infraestructura.
- Documentado que solo `core/config.py` debe leer variables de entorno
  directamente.
- Documentado que `global.js` puede contener solo configuracion publica
  frontend y nunca secretos.
- Ajustada la ubicacion frontend aprobada a
  `SrvRestAstroLS_v1/astro/src/components/global.js`, siguiendo el uso real de
  Team360.
- Agregados enlaces desde `lat.md/lat.md`, `AGENTS.md`,
  `.agents/skills/tebaai-project/SKILL.md` y `docs/adr/README.md`.

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
- Implementar `core/config.py`, `globalVar.py` y `global.js` siguiendo
  `lat.md/global-configuration-facade-policy.md`.
- Conectar backend con PostgreSQL via psycopg pool y configurar DSN.
- Conectar backend con Milvus y LiteLLM en fase de integracion.

## Notas de seguridad

- No se cargaron corpus reales ni archivos pesados.
- No se imprimieron ni leyeron secretos.
- No se iniciaron, detuvieron ni reiniciaron servicios externos.
- La decision de configuracion global es documental; no implementa runtime ni
  crea recursos vivos.
