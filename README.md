# Teba AI

TebaAI is a generic content and bibliographic retrieval platform for iMotorSoft projects. Breslov is its first configured collection, while platform code remains domain-neutral.

## Current stack

- Litestar backend on `127.0.0.1:7008`;
- Astro 7 + Svelte 5 frontend on `127.0.0.1:3008`;
- PostgreSQL 18 as source of truth;
- Milvus 2.6 as derived semantic index;
- LiteLLM for `text-embedding-3-small` embeddings;
- PostgreSQL FTS and hybrid PostgreSQL/Milvus retrieval;
- Playwright + Chromium for browser E2E.

The platform currently retrieves bibliographic evidence. It does not generate RAG answers or interpretative LLM responses.

## Development servers

Use the project launchers from `SrvRestAstroLS_v1/` as the standard way to run local development servers.

Backend:

```bash
./SrvRestAstroLS_v1/backend-dev.sh start
./SrvRestAstroLS_v1/backend-dev.sh status
./SrvRestAstroLS_v1/backend-dev.sh stop
```

Frontend:

```bash
./SrvRestAstroLS_v1/astro-dev.sh start
./SrvRestAstroLS_v1/astro-dev.sh status
./SrvRestAstroLS_v1/astro-dev.sh stop
```

`restart` is also supported, and omitting the action defaults to `start`. `backend-dev.sh` starts `ls_iMotorSoft_Srv01:app` with `uvicorn` on `127.0.0.1:7008` by default. `astro-dev.sh` starts Astro on `127.0.0.1:3008` by default. The ports can be overridden with `TEBAAI_BACKEND_PORT` and `TEBAAI_ASTRO_PORT` only when an intentional local conflict requires it.

The launchers write PID files under `SrvRestAstroLS_v1/.dev-pids/` and logs under `SrvRestAstroLS_v1/.dev-logs/`. `stop` only signals a PID file process after validating its command; unknown listeners on `7008` or `3008` are reported and left untouched. The scripts must not be used to manage PostgreSQL, Milvus or LiteLLM.

## Local validation

Backend:

```bash
cd SrvRestAstroLS_v1/backend
uv run pytest
```

Frontend:

```bash
cd SrvRestAstroLS_v1/astro
pnpm check
pnpm build
```

Authenticated E2E requires credentials supplied only through the environment:

```bash
TEBAAI_E2E_ADMIN_EMAIL='...' \
TEBAAI_E2E_ADMIN_PASSWORD='...' \
pnpm test:e2e
```

## Documentation

- operating rules: `AGENTS.md`;
- architecture index: `lat.md/lat.md`;
- current runtime status: `SrvRestAstroLS_v1/docs/status_actual.md`;
- frozen runtime history: `SrvRestAstroLS_v1/docs/status_historico_hasta_2026-06-28.md`;
- architecture decisions: `docs/adr/`.

Run `lat check` after changing LAT documents or `@lat` references.

## External services

PostgreSQL, Milvus and LiteLLM are permanent external services. Agents must not start, stop, restart, migrate or reconfigure them without explicit user instruction.

No credentials, DSNs, tokens, API keys or real licensed corpus files belong in Git.
