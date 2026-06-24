# TebaAi - Instructions For Agents

Work from the project root:

`/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAi`

TebaAi is a generic content platform. Breslov will be the first vertical
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

## Documentation Placement

- Architecture invariants: `lat.md/`.
- Runtime technical status: `SrvRestAstroLS_v1/docs/`.
- Product, strategy, UX and ADRs: `docs/`.
- Corpus, generated data and reports: `data/`.

Update the relevant `status_actual.md` when closing meaningful phases.
