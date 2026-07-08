# TebaAI Frontend Implementation Policy

This policy defines the package, configuration, UI abstraction and browser-validation boundaries for the Astro and Svelte frontend.

## Toolchain

The frontend uses the versions declared by its package manifest and lockfile.

- `pnpm` is the only package manager;
- `pnpm-lock.yaml` and the `packageManager` field are versioned;
- do not introduce npm or Yarn lockfiles;
- Astro 7, Svelte 5, Tailwind CSS 4 and DaisyUI 5 are the current stack;
- dependency upgrades require `pnpm check`, and build-affecting changes also require `pnpm build`.

## Public Configuration

`src/components/global.js` is the single source of truth for public frontend configuration and routes.

API clients import `API_BASE_URL` and route constants from that module. They do not define separate base URLs, ports or API prefixes. `global.d.ts` remains synchronized with exported values.

Only `PUBLIC_*` values safe for browser exposure may influence frontend configuration. Secrets never enter Astro public environment variables or generated assets.

## URL Rule

Absolute backend URLs outside `global.js` are implementation debt and new occurrences are prohibited.

The current direct-backend development URL is `http://127.0.0.1:7008`, overridable with `PUBLIC_TEBAAI_API_BASE_URL`. Any future reverse-proxy strategy must be made explicit in the same configuration boundary.

## UI Boundary

Tailwind and DaisyUI are implementation details, not the long-term public API of business screens.

New repeated primitives belong in `src/components/ui/` wrappers with TebaAI-owned variants and accessibility behavior. Business logic, authentication transport and API calls do not belong in base UI components.

Existing screens currently use DaisyUI classes directly. Migration to wrappers should be incremental when a primitive is repeated or materially changed; do not rewrite stable screens only for conformance.

## Data and Session Boundary

Private data renders only after session and effective context validation.

API clients centralize credential behavior and error normalization. Components own interaction state, not token persistence rules. Tenant context changes follow [[tenant-context-authorization-policy]].

## Accessibility and Localization

Interactive UI must remain keyboard usable, semantically labeled and direction-aware.

Spanish, English and Hebrew are configured locales. Components that display user or corpus text must tolerate RTL content without forcing the whole application direction incorrectly.

## Validation

Frontend changes use static checks, builds and reproducible browser tests in proportion to their risk.

- run `pnpm check` for frontend changes;
- add `pnpm build` for pages, configuration and build behavior;
- use Playwright + Chromium for reproducible flows;
- use Browser MCP only for exploration under [[browser-mcp-validation-policy]];
- authenticated E2E receives credentials only through `TEBAAI_E2E_ADMIN_EMAIL` and `TEBAAI_E2E_ADMIN_PASSWORD`.
