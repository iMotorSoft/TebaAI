# Likutey Halajot Page-First Reingest V2 — DEV Report

**Date:** 2026-07-30
**Gate:** TEBAAI_LIKUTEY_HALAJOT_PAGE_FIRST_REINGEST_V2_DEV_READY

## Summary

Complete purge and re-ingestion of `LIKUTEY HALAJOT (Interior Final).pdf`.

## Pre-purge inventory

| Layer | Count |
|-------|-------|
| Documents | 2 |
| Chunks | 2,652 |
| Embeddings (PG) | 2,222 |
| Page anchors | 284 |
| Content units | 269 |
| Content nodes | 268 |
| Structural classif. | 284 |
| Fine zones | 506 |
| Note source units | 474 |
| Nominal references | 5 |
| Page final status | 284 |

## Purge

All data for document IDs `37b5842d-...` and `47768aac-...` removed from all
tables. Zero residues verified. Milvus had 0 vectors for these IDs.

## New ingestion

| Metric | Value |
|--------|-------|
| Document ID | `132a791a-d12b-45bc-9b34-dd143605de12` |
| Code | `likutey_halajot_interior_final_v2` |
| Status | `test_candidate` |
| Pages (library_pages_v2) | 284 |
| Textual pages | 268 |
| Chunks (library_document_chunks) | 268 |
| Chunks with search_text_normalized | 268 (100%) |
| Duration | 17.77s |

## Critical page content verified

| Page | Content | Found? |
|------|---------|--------|
| 51 | CONSTRUYENDO UN MISHKÁN | ✅ |
| 53 | INCLINADO HACIA LA BONDAD | ✅ |
| 55 | Salmos 16:1 | ✅ |
| 56 | El hombre se une a HaShem | ✅ |

## Test results

| Suite | Result |
|-------|--------|
| Full backend | 1401/1401 passed |
| Frontend check | 0 errors |
| Frontend tests | 60/60 passed |
| Frontend build | 8 pages, PASS |

## Files

| File | Description |
|------|-------------|
| `scripts/ingest_likutey_halajot_page_first_v2.py` | New page-first ingestion |
| `docs/adr/ADR-014-...` | Architecture decision record |
| `data/reports/.../pre-purge-inventory.json` | Machine-readable pre-purge inventory |
| `data/reports/.../backup-manifest.json` | Backup manifest |
