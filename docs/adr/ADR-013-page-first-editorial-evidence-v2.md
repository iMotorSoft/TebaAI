# ADR-013: Page-First Editorial Evidence V2

**Status:** Accepted (DEV)
**Date:** 2026-07-30

## Context

Page-First V1 provided page resolution, evidence localization, and heading
resolution. Research queries require deeper editorial context:
- Intermediate headings within a page
- Printed biblical references (e.g., "Salmos 16:1")
- Footnotes with their markers and anchor sections

## Decision

Extend the page-first contract with optional V2 editorial fields that capture
block roles, printed references, footnote structure, and heading-body associations
without breaking backward compatibility.

## Editorial block roles

- `section_heading` — content-based detection (numbers + dingbat + uppercase)
- `marginal_reference` — from `evidence_role=marginal_citation`
- `footnote_body` — from `block_type=footnote`
- `notes_heading` — text "Notas y Fuentes"
- `main_body`, `hebrew_source`, `running_header`, `page_number`, etc.

## New fields

All optional, under `evidence.editorial`:

- `block_role`, `block_role_confidence`, `block_role_method`
- `printed_reference`, `reference_normalized`, `reference_status`
- `canonical_reference_candidate`
- `footnote_number`, `footnote_marker`, `footnote_anchor_text`
- `anchor_block_id`, `anchor_section_path`
- `next_heading`
- `containing_heading`
- `associated_body_text`, `associated_body_block_id`

## Files

- `backend/modules/library/editorial_evidence_v2.py` — classification,
  reference detection, footnote resolution, heading-body association
- `backend/tests/test_editorial_evidence_v2.py` — 36 unit tests
- `backend/modules/library/simple_research_rag.py` — integration hook

## Test results

| Suite | Result |
|-------|--------|
| Unit tests (editorial_v2) | 36/36 passed |
| Full backend suite | 1401/1401 passed |
| Frontend check | 0 errors |
| Frontend tests | 60/60 passed |
| Frontend build | 8 pages, PASS |

## Corpus reconciliation

### Caso B — Salmos 16:1 (PASS)
- pdf_page=55, printed_page=37, source_layer=marginal_reference
- match_type=printed_reference_exact
- Variants "Salmos 16:1", "Salmo 16:1", "salmos 16:1" all resolve to page 55

### Caso C — Footnote 35 (DATA GAP)
- Spanish text beginning "El hombre se une a HaShem..." does not exist in corpus
- Chunk 416: Hebrew original
- Chunk 417: Spanish ending only
- Marker .35 at chunk 414
- Re-ingestion required to recover lost footnote text

### Fixes applied
- `search_literal_candidates`: added `include_test_candidates` status filter and content ILIKE fallback for NULL `search_text_normalized`
- `search_printed_reference_candidates`: new targeted SQL search for marginal_source chunks
- Printed reference detection (`is_printed_reference`) runs before english_name detection
- `printed_reference_exact` priority tier (15.0), query shape, and source_layer
- Language filter includes `'mixed'` for marginal chunks
- `_BIBLICAL_REFERENCE` regex now handles singular/plural book names
