# Editorial V2 — Corpus Reconciliation Report

**Date:** 2026-07-30
**Gate:** TEBAAI_PAGE_FIRST_EDITORIAL_EVIDENCE_V2_CORPUS_DEV_READY

## Summary

| Case | Status | Page | Reference | Match |
|------|--------|------|-----------|-------|
| B: Salmos 16:1 | PASS | 55 | marginal_source | printed_reference_exact |
| C: Footnote 35 | DATA GAP | 56 | — | Spanish text not in corpus |
| A: INCLINADO | PASS | 53 | section_heading | structural_heading_exact |

## Document verified

| Field | Value |
|-------|-------|
| document_id | 47768aac-704e-4296-9649-53b9ea037096 |
| title | Likutey Halajot Explicado — Interior Final |
| filename | LIKUTEY HALAJOT (Interior Final).pdf |
| SHA-256 | 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a |
| status | test_candidate |
| chunk_count | 2652 |

## Case B — Marginal reference `Salmos 16:1`

**Primary evidence:** page 55, printed_page 37, marginal_reference source

### Root cause
`search_text_normalized` IS NULL for ALL chunks in test_candidate doc. The literal ILIKE search could not find the chunk. Additionally, the query was misidentified as an `english_name_query` because `detect_short_english_name_query("Salmos 16:1")` returned a match on token "Salmos".

### Fixes applied

1. **simple_research_repository.py**: Added `include_test_candidates` status filter to `search_literal_candidates` SQL (was missing)
2. **simple_research_repository.py**: Added content ILIKE fallback when `search_text_normalized IS NULL` in `search_literal_candidates`
3. **simple_research_rag.py**: Added `is_printed_reference` detection before `english_name_query` detection — skips english_name for biblical references
4. **simple_research_repository.py**: Added `search_printed_reference_candidates()` — targeted SQL search for marginal_source chunks by regex
5. **simple_research_rag.py**: Added `printed_reference_exact` priority tier (15.0) and `printed_reference` query shape
6. **simple_research_repository.py**: Fixed language filter — marginal_source chunks have `language='mixed'`, not 'es'/'en'/'he'
7. **simple_research_rag.py**: Added `marginal_reference` source_layer for marginal chunks
8. **editorial_evidence_v2.py**: Added `Salmo` (singular), `Proverbio` to `_BIBLICAL_REFERENCE` regex

### Variants tested

| Query | Result | Page |
|-------|--------|------|
| Salmos 16:1 | printed_reference_exact | 55 ✅ |
| (Salmos 16:1) | printed_reference_exact | 55 ✅ |
| Salmo 16:1 | printed_reference_exact | 55 ✅ |
| (Salmo 16:1) | printed_reference_exact | 55 ✅ |
| salmos 16:1 | printed_reference_exact | 55 ✅ |

## Case C — Footnote 35

**Status: DATA GAP — cannot be resolved without re-ingestion.**

### Investigation
- Chunk 416 (page 56): HEBREW text of footnote 35 ✅
- Chunk 417 (page 56): SPANISH ENDING of footnote 35 ✅
  - "en aquellos que están en un nivel espiritual muy bajo..."
- Spanish text beginning NOT FOUND in any chunk or raw text ❌
  - "El hombre se une a HaShem desde este mundo físico principalmente a través de la melodía y de la canción"
  - "Escuchar música inspira el anhelo"
- Page 56 marker .35 found in chunk 414: "Como hemos visto, de esa manera se crean melodías.35" ✅

### Root cause
PDF text extraction lost the Spanish portion of footnote 35. Only the Hebrew original and the Spanish continuation suffix were extracted. Re-ingestion of the PDF with improved PDF-to-text extraction is required.

## Files modified

| File | Changes |
|------|---------|
| `modules/library/simple_research_repository.py` | Added `search_printed_reference_candidates()`, fixed `search_literal_candidates` to include test_candidates and content fallback |
| `modules/library/simple_research_rag.py` | Added printed reference detection, priority tier, source_layer, selection support |
| `modules/library/editorial_evidence_v2.py` | Added Salmo/Proverbio to BIBLICAL_REFERENCE regex |

## Results

| Suite | Result |
|-------|--------|
| Editorial V2 tests | 36/36 passed |
| Focused tests | 160/160 passed |
| Full backend suite | 1401/1401 passed |
| Frontend check | 0 errors |
| Frontend tests | 60/60 passed |
| Frontend build | 8 pages, PASS |

## Services preserved

| Service | Modified? |
|---------|-----------|
| PostgreSQL | No |
| Milvus | No |
| LiteLLM | No |
| Production | No |
| Re-ingestion | No |
| Migrations | No |
| Push | No |
