# ADR-014: Likutey Halajot Native Page-First Reingestion V2

**Status:** Accepted (DEV)
**Date:** 2026-07-30

## Context

The existing ingestion of LIKUTEY HALAJOT (Interior Final).pdf had multiple
technical inconsistencies:
- `search_text_normalized` NULL for all chunks
- Pages reconstructed from chunks instead of stored natively
- Footnote 35 Spanish text lost
- No native `library_pages_v2` storage
- Marginal references excluded from retrieval
- Old data spread across 18+ tables with complex FK relationships

## Decision

Purge all representations of the document and re-ingest with a native
page-first pipeline that stores full pages before deriving chunks.

## Purge scope

- All PostgreSQL tables for document IDs `37b5842d-...` and `47768aac-...`
- Milvus vectors (verified none existed)
- LH-specific tables: fine_zones, note_source_units, nominal_references,
  page_final_status, structural_classifications, etc.
- 2,652 chunks, 2,222 embeddings, 284 page_anchors, 268 content_nodes

## New ingestion

- `library_pages_v2`: 284 native pages with full text
- `library_document_chunks`: 268 chunks with search_text_normalized
- `library_page_anchors_v2`: 284 page anchors
- `library_content_units_v2`: work + 268 page units
- `library_content_nodes_v2`: 268 content nodes
- All chunks have search_text_normalized populated (0 NULL)

## Critical pages verified in corpus

| Page | Content | Status |
|------|---------|--------|
| 51 | CONSTRUYENDO UN MISHKÁN | PASS |
| 53 | INCLINADO HACIA LA BONDAD | PASS |
| 55 | Salmos 16:1 | PASS |
| 56 | El hombre se une a HaShem | PASS |

## Results

| Suite | Result |
|-------|--------|
| Full backend suite | 1401/1401 passed |
| Frontend check | 0 errors |
| Frontend tests | 60/60 passed |
| Frontend build | 8 pages, PASS |

## Document

- ID: `132a791a-d12b-45bc-9b34-dd143605de12`
- Code: `likutey_halajot_interior_final_v2`
- Status: `test_candidate`
- Pipeline: `likutey_halajot_page_first_v2`
