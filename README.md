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
