# Canonical Work–Edition–Source Metadata V1 — DEV

## Result

`TEBAAI_CANONICAL_WORK_EDITION_SOURCE_METADATA_V1_DEV_READY`

Canonical bibliographic identity now separates containing work, canonical work,
edition, volume, source work/lesson, technical version and document instance.
No document was promoted.

## Model

The internal dataclass contract validates provenance
`explicit|derived|unresolved|conflicting`. Confirmed metadata lives in the
existing `library_documents.bibliographic_metadata.canonical_identity_v1`
object; no migration was created.

| Document | Family | Edition | Volume | Source | Technical |
|---|---|---|---|---|---|
| `LIKUTEY HALAJOT LM II 8.pdf` | Likutey Halajot | The Rosenberg Edition, explicit | unresolved | develops Likutey Moharán II, lesson 8 | unresolved |
| `LIKUTEY HALAJOT (Interior Final).pdf` | Likutey Halajot | Interior Final, derived filename label | runtime unresolved; physical hint 1 pending approval | section/chunk level | v2 |
| `LIKUTEY MOHARAN II Interior.pdf` | Likutey Moharán II | Edición española BRI, derived | unresolved | original work | layout_v1 |

`source_work` never changes `work_family`; `_v2`, `II` and lesson 8 never imply
volume.

## Scope

- family LH: both legitimate LH editions participate;
- edition Interior Final: only Interior Final;
- document hash: one exact instance;
- LH + source LM II lesson 8: Rosenberg LH commentary;
- original LM II lesson 8: persisted original structural nodes, not LH;
- comparative: original LM II plus explicit LH commentary with separate roles;
- `Likutey`/`LM`: `scope_ambiguous`, no evidence.

Scope labels are removed only from deterministic lexical/heading variants. The
intact query remains the semantic embedding and audit input.

## API and UI

The API is additive: five optional request fields and canonical identity fields
on hits. Existing fields were not removed or renamed. The UI displays `Obra`,
`Edición` and `Fuente desarrollada` separately. Technical version is secondary
metadata and volume is shown only when resolved.

Live API admin+guest: 16/16 PASS. Relation QA remains HTTP 200 with 20 sources.

## Validation

- focused backend: 134 passed, 0 failed;
- complete backend: 1,468 passed, 0 failed, 94 known warnings;
- frontend check: 0 errors, 0 warnings, 2 pre-existing hints;
- Vitest: 70 passed;
- Astro build: 8 pages PASS;
- canonical API: 16/16 admin+guest;
- editorial/proper-name/Hebrew/planner regressions: 9/9;
- Playwright Chromium: 3/3 admin, guest and mobile 390×844.

## Persistence and operations

Only `bibliographic_metadata.canonical_identity_v1` changed on three guarded DEV
rows. Status remained `ready,test_candidate,test_candidate`. PostgreSQL, Milvus
and LiteLLM were not restarted. No migration, reingestion, embedding operation,
Milvus write, production change or push occurred.

Interior Final remains `test_candidate`. Note 36 remains outside scope at 24/25;
next gate: `PDF_LIGATURE_LITERAL_NORMALIZATION_V1`.

## Reproduction

```bash
cd SrvRestAstroLS_v1/backend
PYTHONPATH=. uv run python scripts/audit_canonical_work_edition_source_metadata_v1.py \
  --output ../../data/reports/breslov/2026-08-04-canonical-work-edition-source-metadata-v1-dev
PYTHONPATH=. uv run python scripts/run_canonical_metadata_api_v1.py \
  --output ../../data/reports/breslov/2026-08-04-canonical-work-edition-source-metadata-v1-dev/api-live-results.json
```

See ADR-019, `migration-recommendation.md` and `rollback-plan.md`.
