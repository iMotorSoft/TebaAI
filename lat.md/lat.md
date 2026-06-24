# TebaAi Architecture

This directory contains living architecture and stable operating rules for
TebaAi.

## Project Map

- `AGENTS.md`: required operating instructions for agents.
- `.agents/skills/tebaai-project/SKILL.md`: local project skill.
- `lat.md/`: architecture invariants and canonical policies.
- `SrvRestAstroLS_v1/backend/`: Litestar backend.
- `SrvRestAstroLS_v1/astro/`: Astro.js + Svelte 5 frontend.
- `SrvRestAstroLS_v1/docs/`: technical runtime status.
- `SrvRestAstroLS_v1/lab/`: isolated experiments.
- `docs/`: ADRs, strategy, business, UX and templates.
- `data/`: corpus input, processed outputs and generated reports.

## Stack

- Backend: Litestar.
- Backend entrypoint: `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`.
- ASGI object: `app`.
- Frontend: Astro.js + Svelte 5 runes.
- Package manager: pnpm.
- E2E gate: Playwright + Chromium.
- Diagrams: Mermaid source in Git.

## Conventions

- Visible brand: `Teba AI`.
- Technical identifier: `tebaai`.
- Environment prefix: `TEBAAI_`.
- Backend port: `7008`.
- Astro port: `3008`.
- No `backend/app.py` unless a future ADR approves the exception.

## External Services

PostgreSQL, Milvus and LiteLLM are external permanent services. They must not
be started, stopped or restarted automatically.

## Canonical Documents

- [[service-preflight-methodology]]
- [[postgres-driver-policy]]
- [[browser-mcp-validation-policy]]
- [[mermaid-diagram-policy]]
- [[root-cause-debugging-policy]]
- `docs/adr/ADR-001-new-project-bootstrap-template.md`

## Development Flow

1. Read `AGENTS.md`.
2. Read `.agents/skills/tebaai-project/SKILL.md`.
3. Read this index and `lat.md/status_actual.md` for architecture changes.
4. Check `git status`.
5. Keep changes small and update status files when phases close.

## Completion Criteria

A phase is not complete until the relevant code or documentation exists,
validation was run or explicitly skipped with reason, and no external services
were modified without explicit instruction.
