# Ingestion Status: LIKUTEY MOHARÁN I int (imprenta).pdf

## Classification

**`LIKUTEY_MOHARAN_I_FULL_INGESTION_CONFIRMED`**
**`READY_FOR_WORK_IDENTITY_REVIEW`**

## Physical File

- **Absolute path**: `/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARÁN I int (imprenta).pdf`
- **SHA-256**: `71fb3c763c34d13465441c57b2bf3a65629fcdc37a7588f21e4fbf21f984b8d7`
- **Size**: 3,902,674 bytes
- **PDF pages**: 442
- **Duplicates**: None found

## Document Registration

- **Document ID**: `6673da69-eb38-40bf-9f5c-447ff3ba6725`
- **Title**: `Likutey Moharán I — edición española BRI`
- **Status**: `test_candidate`
- **Created**: 2026-07-18
- **Ingestion profile**: `likutey_moharan_i_literal_page_first_v1`
- **Metadata**: `{"physical_pages": 442}`

## Page Coverage

| Metric | Value |
|--------|-------|
| PDF total pages | 442 |
| Pages in DB (`library_lmi_literal_search_v1`) | 431 |
| Missing pages (blank, confirmed) | 11 |
| Coverage rate | 97.5% (431/442) |
| Duplicates | 0 |

The 11 missing pages (2, 6, 12, 20, 348, 385, 387, 415, 437, 439, 441) were verified as **blank pages** with zero extractable text via PyMuPDF. All content-bearing pages are fully present.

## Sections

55 sections from `#1:1` through `#6:15`, each with proper `section_page_label` mapping.

- Lesson 1: 6 sections (#1:1 - #1:6)
- Lesson 2: 9 sections (#2:1 - #2:9)
- Lesson 3: 7 sections (#3:1 - #3:8)
- Lesson 4: 11 sections (#4:1 - #4:11)
- Lesson 5: 7 sections (#5:1 - #5:7)
- Lesson 6: 15 sections (#6:1 - #6:15)

## Chunks

0 chunks in `library_document_chunks`. The page-first ingestion uses `library_lmi_literal_search_v1` view directly (no chunk-level indexing). This is the expected pattern for this document.

## Search Views

- `library_lmi_literal_search_v1`: 431 rows, fully searchable
- No chunk-level embeddings for this document (not required for literal search)

## Focal Page Verification

### Printed page 73 (PDF page 93)

- **PDF page**: 93
- **Printed page**: 73
- **Section**: `LIKUTEY MOHARÁN #2:6`
- **Text**: Contains "Moshé, tú lo has dicho bien" with Shabat 101b reference
- **Status**: Present, exact_phrase matchable

### Section #2:6

- PDF pages: 92–93 (2 pages)
- Printed pages: 72–73
- Hebrew side (page 92) and Spanish side (page 93) both present

## Endpoint Verification

| Query | Status | LMI hits | Exact phrase | Primary |
|-------|--------|----------|-------------|---------|
| "Moshé, tú lo has dicho bien" | ok | 10 | 1 | Yes |
| "hasta que venga Shiló" | ok | 3 | 1 | Yes |
| "Shabat 101b" | ok | 10 | (concept) | No |

## Ingestion Plan

**No ingestion needed.** Document is fully ingested with all content pages present. The 11 missing pages are confirmed blank. No changes to code or data required.

## Conclusion

The ingestion audit confirms:

- [x] Physical file located and checksummed
- [x] Document registered in PostgreSQL
- [x] All 442 PDF pages accounted for (431 with text, 11 blank)
- [x] Focal printed page 73 (PDF page 93) present
- [x] Section `LIKUTEY MOHARÁN #2:6` present
- [x] Phrase "Moshé, tú lo has dicho bien" recoverable as exact_phrase
- [x] Search views include the document
- [x] 0 unjustified missing pages
- [x] 0 duplicates
- [x] Endpoint returns the document with correct metadata
- [x] No ingestion changes needed
- [x] Previous fix (`_compute_literal_match_kind` case-insensitive) resolved the retrieval issue
