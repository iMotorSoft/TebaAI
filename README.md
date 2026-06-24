# Teba AI

TebaAI is a generic content platform for iMotorSoft projects.

The visible brand is `Teba AI`; the internal technical identifier is
`tebaai`. Breslov will be the first vertical project, but this repository
starts as a generic platform without domain-specific ingestion, corpus or
business logic.

## Stack

- Backend: Litestar.
- Backend entrypoint: `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`.
- ASGI object: `app`.
- Backend local port: `7008`.
- Frontend: Astro.js + Svelte 5 runes.
- Astro local port: `3008`.
- Package manager: pnpm.
- Browser E2E gate: Playwright + Chromium.
- Browser exploratory diagnostics: Browser MCP.
- Diagrams: Mermaid source in Git.

## First local commands

Backend syntax check:

```bash
cd SrvRestAstroLS_v1/backend
python -m py_compile ls_iMotorSoft_Srv01.py
```

Backend dev launcher:

```bash
cd SrvRestAstroLS_v1/backend
uv run uvicorn ls_iMotorSoft_Srv01:app --host 127.0.0.1 --port 7008
```

Frontend:

```bash
cd SrvRestAstroLS_v1/astro
corepack pnpm install
corepack pnpm dev
```

No PostgreSQL, Milvus or LiteLLM process should be started, stopped or
restarted automatically from this bootstrap.
