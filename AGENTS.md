# TebaAI - Instructions For Agents

Work from the project root:

`/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI`

TebaAI is a generic content platform. Breslov will be the first vertical
project, but this bootstrap must not create Breslov-specific logic, ingestion,
PostgreSQL, Milvus or LiteLLM integration yet.

## Canonical Decisions

- Visible brand: `Teba AI`.
- Technical identifier: `tebaai`.
- Environment variable prefix: `TEBAAI_`.
- Backend standard: Litestar.
- Frontend standard: Astro.js + Svelte 5 runes.
- Backend port: `7008`.
- Astro port: `3008`.
- Backend entrypoint: `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`.
- ASGI object: `app`.
- Launcher: `uvicorn ls_iMotorSoft_Srv01:app --host 127.0.0.1 --port 7008`.
- Do not create `SrvRestAstroLS_v1/backend/app.py` unless a new ADR explicitly
  approves the exception.

## External Services

PostgreSQL, Milvus and LiteLLM are permanent external services.

Agents must not start, stop, restart, reconfigure or migrate those services
automatically. Any action on those services requires explicit manual
instruction.

## Browser And Testing Policy

Playwright + Chromium is the official E2E gate.

Browser MCP is exploratory and useful for visual diagnostics, reproduction and
inspection. Browser MCP does not replace a reproducible Playwright test for
closing a phase or regression.

## Diagrams

Mermaid is the canonical source for diagrams and must be versioned in Git.
SVG, PNG and Excalidraw files are optional derived artifacts.

Do not install the full gstack `/diagram` workflow and do not make this project
depend on gstack.

## Root Cause

Non-trivial investigations must follow the local root cause methodology:
reproduce, state hypotheses, gather evidence, apply a minimal fix and add a
regression test when reasonable.

## Required Context Before Architecture Changes

Before modifying architecture, domain boundaries, external service policy,
browser validation, diagrams or root cause policy, read:

- `lat.md/lat.md`
- `lat.md/status_actual.md`
- `docs/adr/`

Before modifying global configuration, environment variables, PostgreSQL,
Milvus, LiteLLM, auth, `globalVar.py` or `global.js`, read:

- `lat.md/global-configuration-facade-policy.md`

`globalVar.py` is a stable configuration facade backed by typed settings in
`core/config.py`. Do not remove it, do not add connections or infrastructure
side effects to it, and do not read environment variables outside
`core/config.py`. `global.js` may contain only public frontend configuration and
must never contain secrets.

## Git Branch Convention

- `main`: estado estable validado / producción / snapshot estable. No trabajar directo salvo hotfix o consolidación final.
- `feature/console-backend-core`: rama de desarrollo activo. backend, frontend, runtime, orquestación. Es la rama para `desarrollo`, `dev` o `backend`. Todo el trabajo productivo va aquí.
- `feature/knowledge-ingestion-service`: knowledge ingestion / RAG / embeddings / chunking / retrieval. No usar para runtime productivo.
- `docs/knowledge-documents-foundation`: documentación knowledge: estándares, paquetes, contenido curado.
- `ux/team360-console-design-handoff`: diseño visual, frontend mock, handoff UX. Sin backend real ni integración productiva.

Cuando una instrucción mencione `desarrollo`, `dev` o `backend`, la rama destino es `feature/console-backend-core`.

## Documentation Placement

- Architecture invariants: `lat.md/`.
- Runtime technical status: `SrvRestAstroLS_v1/docs/`.
- Product, strategy, UX and ADRs: `docs/`.
- Corpus, generated data and reports: `data/`.

## `status_actual.md` Convention

`status_actual.md` is a closing-state log, not a diary. Update the relevant
file when closing a meaningful phase, not for every trivial edit.

- `SrvRestAstroLS_v1/docs/status_actual.md`: main runtime technical log. It
  covers backend, Astro/Svelte frontend and frontend/backend integration.
- `lat.md/status_actual.md`: architecture-living log. Use it only for
  architecture invariants, canonical policies and LAT documents.
- `docs/**/status_actual.md`: local documentation status for active product,
  strategy, UX, ADR or template directories.
- `data/**/status_actual.md`: local status for corpus, generated data, reports
  and evidence.

Do not duplicate long decisions inside status files. Link to the canonical LAT,
ADR or technical document instead. Empty auxiliary folders that only contain
`.gitkeep` do not need a `status_actual.md`.
