# LAT Documentation Policy

This policy defines the permanent structure, linking, indexing, status and validation rules for TebaAI architecture and Markdown documentation.

## Purpose

Documentation must remain searchable, navigable and consistent with implementation without turning status files into append-only logs.

## Scope

The policy applies to architecture, operating instructions, runtime status, ADRs and project documentation.

- `lat.md/`
- `SrvRestAstroLS_v1/docs/`
- `docs/`
- `AGENTS.md`
- `.agents/skills/tebaai-project/SKILL.md`

Generated evidence under `data/reports/` follows the same link and secret rules, but may use report-oriented structure.

## Heading Rule

Every section begins with a concise prose summary before a list, table, code block or subsection so LAT extraction preserves meaningful context.

The introductory paragraph should normally stay below 250 characters. A heading followed directly by another heading, list, table or code block is invalid for new or modified LAT documents.

## Link Rule

Wiki links represent existing architectural concepts, not future placeholders.

Every `[[wiki-link]]` must resolve to a real LAT document or section. Create the target first and use `lat locate` when the destination is ambiguous.

## Index Rule

`lat.md/lat.md` is the complete navigable inventory of concept documents in `lat.md/`.

Add a document to the index in the same change that creates it. Do not index generated reports or operational evidence as architecture concepts.

## Status Rule

Status documents describe the current closing state and link to canonical decisions and evidence.

- `lat.md/status_actual.md` stays compact and architectural.
- `SrvRestAstroLS_v1/docs/status_actual.md` records current runtime state.
- frozen history remains in the historical status file and Git.
- detailed run output belongs in `data/reports/`.

When LAT changes, update `lat.md/status_actual.md` without copying the full policy or implementation narrative.

## Duplication Rule

One source owns each stable decision; other documents summarize and link to it.

LAT contains invariants and contracts. ADRs contain decision context and consequences. Status contains current state. Reports contain generated evidence.

## Secret Rule

Documentation, examples and reports must not expose functional credentials or sensitive connection material.

Use variable names and sanitized identifiers. Never include passwords, API keys, access or refresh tokens, private keys, full DSNs or reusable E2E credentials.

## Required Gates

Documentation changes run every available structural gate from the repository root.

```bash
lat check md
lat check index
lat check sections
lat check code-refs
lat check
git diff --check
```

If the installed LAT version does not provide a subcommand, record that limitation and still run `lat check` plus `git diff --check`.

## Failure Policy

A documentation phase is not a PASS while a mandatory gate fails because of the current change.

Fix new failures before closing. If a gate exposes pre-existing failures, separate them from the new diff and report them explicitly.
