---
name: tebaai-project
description: Rules and workflow for TebaAI, a generic iMotorSoft content platform using Litestar, Astro.js, Svelte 5 and reproducible browser validation.
---

# TebaAI Project

## Scope

TebaAI is a generic content platform. Breslov is planned as the first vertical
project, but the base project must stay domain-neutral until a later phase.

## Naming

- Directory: `TebaAI`.
- GitHub repository: `TebaAI`.
- Visible brand: `Teba AI`.
- Technical identifier: `tebaai`.
- Environment variable prefix: `TEBAAI_`.

## Official Stack

- Backend: Litestar.
- Frontend: Astro.js + Svelte 5 runes.
- Package manager: pnpm.
- Browser E2E gate: Playwright + Chromium.
- Diagram source: Mermaid.

## Ports

- Backend: `7008`.
- Astro: `3008`.

## Backend Entrypoint

Canonical file:

`SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`

ASGI object:

`app`

Launcher:

```bash
uvicorn ls_iMotorSoft_Srv01:app --host 127.0.0.1 --port 7008
```

Do not create `backend/app.py` unless a new ADR explicitly approves a wrapper
or exception.

## External Services

PostgreSQL, Milvus and LiteLLM are permanent external services.

Do not start, stop, restart, reconfigure or migrate them automatically. Manual
and explicit user instruction is required for any action on those services.

## Documentation Policy

- `lat.md/`: architecture invariants and canonical operating rules.
- `SrvRestAstroLS_v1/docs/`: technical runtime status.
- `docs/`: ADRs, strategy, product, UX and templates.
- `data/`: source corpus, processed outputs and generated reports.

Do not duplicate the same decision across layers. Link instead.

`status_actual.md` is a closing-state log, not a diary. Update it when closing
a meaningful phase.

- `SrvRestAstroLS_v1/docs/status_actual.md` is the main runtime technical log
  for backend, Astro/Svelte frontend and frontend/backend integration.
- `lat.md/status_actual.md` records architecture invariants, canonical policies
  and LAT document changes.
- `docs/**/status_actual.md` records local status for active documentation
  directories.
- `data/**/status_actual.md` records local status for corpus, generated data,
  reports and evidence.

Do not duplicate long decisions inside status files. Link to the canonical LAT,
ADR or technical document instead. Empty auxiliary folders that only contain
`.gitkeep` do not need a `status_actual.md`.

Before modifying global configuration, environment variables, PostgreSQL,
Milvus, LiteLLM, auth, `globalVar.py` or `global.js`, read
`lat.md/global-configuration-facade-policy.md`.

`globalVar.py` is the stable backend configuration facade backed by typed
settings in `core/config.py`. Do not remove it, do not add connections or
infrastructure side effects to it, and do not read environment variables
outside `core/config.py`. `global.js` may contain only public frontend
configuration and must never contain secrets.

## Testing Policy

Playwright + Chromium is the official E2E gate. Browser MCP is exploratory and
diagnostic only.

Use root cause methodology for non-trivial bugs: reproduce, hypothesize,
collect evidence, fix minimally and add regression coverage when reasonable.

## Prohibitions

- Do not install or configure FastAPI.
- Do not create `SrvRestAstroLS_v1/backend/app.py`.
- Do not rename `ls_iMotorSoft_Srv01.py`.
- Do not load real books, corpora or heavy data into Git.
- Do not manage PostgreSQL, Milvus or LiteLLM automatically.
- Do not install gstack or the full `/diagram` workflow.

## Recommended Flow Before Changes

1. Read `AGENTS.md`.
2. Read this skill.
3. Read `lat.md/lat.md`.
4. Check `lat.md/status_actual.md`.
5. Check `git status`.
6. Confirm the change belongs to the current phase.

Update the relevant `status_actual.md` when a meaningful phase is completed.
