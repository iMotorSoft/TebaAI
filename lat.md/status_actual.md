# Status actual - TebaAI lat.md

Objetivo: `arquitectura-viva`

Ultima actualizacion: 2026-06-24

## Estado general

Bootstrap inicial de arquitectura viva para TebaAI.

## Acciones realizadas

### 2026-06-24 - Correccion de naming TebaAI

- Se normalizaron referencias textuales del proyecto a `TebaAI`.
- Se confirmo que el directorio de trabajo actual ya usa `TebaAI`.
- Servicios externos PostgreSQL, Milvus y LiteLLM: no tocados.

### 2026-06-24 - Bootstrap inicial

- Se creo la estructura base de `lat.md/`.
- Se documentaron stack, puertos, entrypoint Litestar, politicas de navegador,
  Mermaid, root cause, PostgreSQL y servicios externos.
- Backend minimo Litestar: completado como scaffold.
- Frontend minimo Astro/Svelte: completado como scaffold.
- Servicios externos PostgreSQL, Milvus y LiteLLM: no tocados.

## Validacion

- `python3 -m py_compile ls_iMotorSoft_Srv01.py`: PASS.
- `node --check astro.config.mjs`: PASS.
- `package.json` parseado con Node: PASS.
- `find . -name app.py`: sin resultados.
- `pnpm check`: no ejecutado porque no hay `node_modules`; no se instalaron
  dependencias en este bootstrap.
- `pnpm build`: no ejecutado porque no hay `node_modules`; no se instalaron
  dependencias en este bootstrap.
- Playwright: no ejecutado para evitar instalacion/uso de navegador pesado sin
  instruccion adicional.

## Pendientes recomendados

- Instalar dependencias con `uv` y `pnpm` cuando el usuario lo apruebe.
- Ejecutar `pnpm check`, `pnpm build` y Playwright despues de instalar
  dependencias.
- Definir la primera vertical Breslov en una fase posterior.

## Notas de seguridad

- No se cargaron corpus reales ni archivos pesados.
- No se imprimieron ni leyeron secretos.
- No se iniciaron, detuvieron ni reiniciaron servicios externos.
