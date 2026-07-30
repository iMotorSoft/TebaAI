# Page-First Evidence Contract V1 — DEV Report

**Date:** 2026-07-30
**Gate:** `TEBAAI_PAGE_FIRST_EVIDENCE_CONTRACT_V1_DEV_READY`

## Pilot case: CONSTRUYENDO UN MISHKÁN

| Field | Value |
|-------|-------|
| document | Likutey Halajot Explicado — Interior Final |
| file | LIKUTEY HALAJOT (Interior Final).pdf |
| pdf_page | 51 |
| printed_page | 33 |
| heading_text | 4 ■ CONSTRUYENDO UN MISHKÁN |
| heading_source | structural_heading_candidate |
| evidence_id | ev-bf5ac6e2fbf46812 |
| location_precision | exact |
| exact_quote | 4 ■ CONSTRUYENDO UN MISHKÁN |
| section_path | ["4 ■ CONSTRUYENDO UN MISHKÁN"] |
| page_resolution_method | chunk_page_start |
| status | complete |

## Test results

| Suite | Result |
|-------|--------|
| Unit tests (page_first_evidence) | 27/27 passed |
| Focused backend (page_first, evidence, heading, simple_rag) | 43/43 passed |
| Full backend suite | 1330/1330 passed (+27 new, 0 regressions) |
| Frontend check | 0 errors, 0 warnings |
| Frontend tests | 60/60 passed |
| Frontend build | 8 pages, PASS |

## Files committed

- `SrvRestAstroLS_v1/backend/modules/library/page_first_evidence.py` (new)
- `SrvRestAstroLS_v1/backend/tests/test_page_first_evidence.py` (new)
- `SrvRestAstroLS_v1/backend/modules/library/simple_research_rag.py` (modified)
- `SrvRestAstroLS_v1/astro/src/components/research/SourcePanel.svelte` (modified)
- `docs/adr/ADR-011-page-first-evidence-contract-v1.md` (new)
- `data/reports/breslov/2026-07-30-page-first-evidence-contract-v1-dev/README.md` (new)

## Services

- PostgreSQL: not restarted
- Milvus: not restarted
- LiteLLM: not restarted
- Production: not modified
- Migrations: not executed
- Corpus: not modified
- Reingestion: not performed
- Embeddings: not recalculated
- Push: not performed
