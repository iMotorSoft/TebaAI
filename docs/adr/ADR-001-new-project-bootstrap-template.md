# ADR-001 - Bootstrap estandar de proyectos iMotorSoft

Estado: aprobado.

Fecha: 2026-06-24.

## Contexto

TebaAi inicia como plataforma generica de contenidos para iMotorSoft. Breslov
sera el primer proyecto vertical, pero el bootstrap debe mantener la base sin
logica de dominio.

## Decision

TebaAi adopta el bootstrap estandar de proyectos iMotorSoft:

- Backend: Litestar.
- Frontend: Astro.js + Svelte 5 runes.
- No se usa `backend/app.py` como entrypoint principal.
- Entry point canonico: `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`.
- Objeto ASGI recomendado: `app`.
- Launcher: `uvicorn ls_iMotorSoft_Srv01:app`.
- Puerto backend: `7008`.
- Puerto frontend Astro: `3008`.
- Mermaid como fuente canonica versionable para diagramas.
- Playwright + Chromium como gate E2E oficial.
- Browser MCP como herramienta exploratoria y de diagnostico visual.
- PostgreSQL, Milvus y LiteLLM son servicios externos permanentes no
  gestionados automaticamente por agentes.

Cualquier excepcion debe documentarse en un ADR nuevo.

## Consecuencias

- El proyecto arranca con convenciones claras para agentes y humanos.
- El entrypoint backend queda alineado con el patron iMotorSoft.
- FastAPI no forma parte del bootstrap.
- Las herramientas exploratorias no reemplazan tests reproducibles.
- Los servicios externos no se modifican por accidente durante el bootstrap.
