---
name: tebaai-project
description: Operative workflow for TebaAI, a Litestar, Astro, PostgreSQL, Milvus and LiteLLM content platform.
---

# TebaAI Project

## Scope

TebaAI is a generic content platform. Breslov is the first configured collection, but domain-specific content remains data and configuration rather than platform logic.

## Required start

1. Work from `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI`.
2. Read `AGENTS.md` and `SrvRestAstroLS_v1/docs/status_actual.md`.
3. Check branch and worktree state.
4. Load only the canonical LAT document relevant to the task.

`AGENTS.md` owns branch routing, validation and repository-wide limits. This skill adds no competing rules.

## Stable boundaries

- brand: `Teba AI`;
- identifier: `tebaai`;
- environment prefix: `TEBAAI_`;
- backend: Litestar on port `7008`;
- frontend: Astro 7 + Svelte 5 on port `3008`;
- PostgreSQL: source of truth;
- Milvus: derived vector index;
- LiteLLM: embedding and model gateway;
- backend entrypoint: `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`.

Do not create `backend/app.py` without an ADR.

## Context routing

- configuration and secrets: `lat.md/global-configuration-facade-policy.md`;
- PostgreSQL: `lat.md/postgres-driver-policy.md`;
- auth: `lat.md/authentication-security-policy.md`;
- library and retrieval: `lat.md/library-retrieval-models-policy.md`;
- services: `lat.md/service-preflight-methodology.md`;
- browser: `lat.md/browser-mcp-validation-policy.md`;
- debugging: `lat.md/root-cause-debugging-policy.md`.

## External services

PostgreSQL, Milvus and LiteLLM are permanent services. Never start, stop, restart, migrate or reconfigure them without explicit user instruction.

## Documentation

- current runtime state: `SrvRestAstroLS_v1/docs/status_actual.md`;
- frozen history: `SrvRestAstroLS_v1/docs/status_historico_hasta_2026-06-28.md`;
- architecture: `lat.md/`;
- decisions: `docs/adr/`;
- evidence: `data/reports/`.

Status is a closing-state board, not an append-only diary. Link canonical decisions instead of copying them.

## Validation

- run focused tests and `git diff --check`;
- run `lat check` after LAT or `@lat` changes;
- run `pnpm check` for frontend changes and `pnpm build` for pages/build configuration;
- provide `TEBAAI_E2E_ADMIN_EMAIL` and `TEBAAI_E2E_ADMIN_PASSWORD` for authenticated E2E;
- treat Browser MCP as exploratory and Playwright as the reproducible browser gate.

Never version secrets or credential fallbacks.
