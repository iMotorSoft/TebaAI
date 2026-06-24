# Browser Validation Policy

Playwright + Chromium is the official browser E2E gate for TebaAi.

Browser MCP is exploratory. It can help inspect layout, reproduce visual bugs
or understand a flow, but it does not replace a reproducible Playwright test
for closing regressions or approving a phase.

## Local URLs

- Backend: `http://127.0.0.1:7008`
- Astro: `http://127.0.0.1:3008`

## PASS Evidence

Relevant browser validation should record:

- environment;
- base URL;
- command;
- test count;
- failures;
- console critical errors when applicable;
- 5xx errors when applicable;
- duplicate requests when applicable.

Do not start PostgreSQL, Milvus or LiteLLM as part of browser validation unless
the user explicitly asks for that action.
