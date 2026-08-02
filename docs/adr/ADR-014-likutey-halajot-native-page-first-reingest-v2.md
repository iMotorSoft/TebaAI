# ADR-014 — Native Page-First PDF Ingestion

**Status:** Accepted (DEV)
**Date:** 2026-07-30 (decision), 2026-07-31 (closure)
**Validated with:** `LIKUTEY HALAJOT (Interior Final).pdf` (SHA-256: `440d4fd3…`)

## Context

The previous ingestion of Likutey Halajot suffered from multiple structural
problems that cascaded into retrieval errors:

- `search_text_normalized` was NULL for all chunks because page text was
  reconstructed from chunk groups after fragmentation, losing normalized forms.
- Pages were not stored natively; the only complete page representation was
  assembled by joining chunks on `page_start`/`page_end`, which broke
  footnotes, marginal references, and running headers.
- Footnote 35 Spanish text was truncated at ingestion boundaries.
- Marginal printed references (e.g. `(Salmos 16:1)`) were invisible to the
  printed-reference search lane because no chunk carried
  `evidence_role='marginal_citation'`.
- The document was scattered across 18+ tables with complex FK chains, making
  auditing and repair expensive.

Patching individual pages failed: every fix introduced new boundary conditions
and the lack of a canonical page source meant no fix could be independently
verified without re-reading the PDF.

## Decision

**Store the complete page before deriving chunks.** This is a general
architectural rule, not specific to Likutey Halajot.

For every page-first ingestion:

```
PDF page
  → extract full text (PyMuPDF4LLM + page marker injection)
  → persist as library_pages_v2 row (text, page_number, char_count)
  → derive editorial blocks (headings, body, references, footnotes)
  → derive semantic chunks (one per page section, preserving source_layer)
  → populate search_text_normalized on every chunk
  → embed and index in Milvus
```

The page is the atomic unit. Chunks are derivations, not primary storage.

## Architecture

### Page model (`library_pages_v2`)

Every page row carries:

| Field | Source | Obligatory |
|---|---|---|
| `page_id` | UUID, generated | Yes |
| `document_id` | FK to `library_documents` | Yes |
| `page_number` | 1-indexed PDF page | Yes |
| `text` | Full extracted text | Yes |
| `char_count` | Computed from text | Yes |
| `extraction_method` | `pymupdf4llm_markers` etc. | Yes |
| `confidence` | 0.0–1.0, extraction quality | Recommended |
| `layout_notes` | JSONB, positional metadata | Recommended |

### Chunk model (`library_document_chunks`)

Every chunk carries:

| Field | Purpose | Obligatory |
|---|---|---|
| `id` | UUID | Yes |
| `document_id` | FK | Yes |
| `page_start` / `page_end` | PDF page range | Yes |
| `printed_page_label` | Roman numeral or Arabic | If available |
| `content` | Markdown payload | Yes |
| `search_text_normalized` | unaccent + NFKC + casefold | Yes |
| `content_sha256` | Integrity fingerprint | Yes |
| `token_estimate` | Approximate token count | Recommended |
| `block_type` | `page_first_v2`, `body`, `heading`, … | Yes |
| `evidence_role` | `commentary`, `marginal_citation`, `footnote_body`, … | Yes |
| `citable` | Boolean | Yes |
| `section_title` | Canonical section heading | If available |
| `node_path` | Hierarchical path | Recommended |
| `chunking_strategy` | `page_first_v2` | Yes |
| `bibliographic_metadata` | JSONB (edition, printed_page, page_mapping) | Yes |

## Editorial Roles

The ingestion pipeline classifies each chunk into one of these editorial roles:

| Role | Description | Example |
|---|---|---|
| `section_heading` | Numbered or unnumbered heading | `4 ■ CONSTRUYENDO UN MISHKÁN` |
| `subsection_heading` | Sub-heading under a section | — |
| `commentary` | Main body commentary text | `El Rabí Natán concluye…` |
| `marginal_reference` | Printed reference in margin or inline | `(Salmos 16:1)` |
| `footnote_marker` | Inline superscript or bracketed number | `³⁵` |
| `footnote_body` | Footnote text at page bottom | `El hombre se une a HaShem…` |
| `notes_heading` | Heading of the notes section | — |
| `running_header` | Page header (book title, chapter name) | `LIKUTEY HALAJOT` |
| `page_number` | Printed page number | `33` |
| `unknown` | Unclassified block | — |

These roles map to retrieval lanes (heading → structural_heading, reference →
printed_reference, footnote → footnote_literal).

## Editorial Relationships

The following parent-child relationships are preserved:

```
heading → associated body paragraph
reference → associated body paragraph
footnote_marker → footnote_body
footnote → anchor paragraph → containing section
block → containing section (resolved from preceding heading)
block → next heading (section boundary)
```

Critical rule:

> The section of a footnote is resolved from the marker and its anchor
> paragraph, **not** from the heading visually closest to the footnote text.

## Printed References

Printed biblical references follow a strict contract:

| Field | Example |
|---|---|
| `reference_surface` | `(Salmos 16:1)` |
| `reference_normalized` | `salmos 16:1` |
| `source_layer` | `marginal_reference` |

The surface form must always be preserved. Normalization for search is a
derived operation. No AI-based correction of references is permitted.

The regex used for detection in retrieval: `(?i)(?:Salmo|Génesis|Éxodo|…) \d+:\d+`

## Footnotes — Case: Note 35

**Location:** PDF page 56, printed page 38. The note body is set with the
following page boundary: its marker anchor remains in `5 ■ INCLINADO HACIA LA
BONDAD`, while `6 ■ MELODÍAS Y PLEGARIAS` is the next heading. These are
separate editorial relationships and must never be represented by one field.

**Marker:** `³⁵` inline after `se crean melodías.`

**Full footnote text:**

> El hombre se une a HaShem desde este mundo físico principalmente a través
> de la melodía y de la canción. Esto lo vemos de manera empírica. Escuchar
> música inspira el anhelo. Genera el deseo de una mayor cercanía con HaShem,
> incluso en aquellos que están más alejados.

**Retrieval gates:**

- `El hombre se une a HaShem` → page 56, footnote_literal_exact
- `MELODÍAS Y PLEGARIAS` → page 56, structural_heading_exact (next heading)
- `nota 35` in isolation → ambiguous; resolves better via context

Notes 35, 36 and 37 coexist on adjacent pages and must be distinguishable by
their anchor paragraph and marker. The ingestion must preserve marker-to-body
separation.

## Validation Fixtures (Permanent)

These five cases must pass on every re-ingestion or pipeline change:

| Query | Expected PDF Page | Expected Match Type |
|---|---|---|
| `CONSTRUYENDO UN MISHKÁN` | 51 | `structural_heading_exact` |
| `INCLINADO HACIA LA BONDAD` | 53 | `structural_heading_exact` |
| `Salmos 16:1` | 55 | `printed_reference_exact` |
| `El hombre se une a HaShem desde este mundo físico…` | 56 | `footnote_literal_exact` |
| `MELODÍAS Y PLEGARIAS` | 56 | `structural_heading_exact` |

These are encoded in `SrvRestAstroLS_v1/backend/tests/fixtures/likutey_halajot_page_first_v2_acceptance.json`.

## Results

| Metric | Value |
|---|---|
| Native pages (`library_pages_v2`) | 284 |
| Chunks (`library_document_chunks`) | 268 |
| `search_text_normalized` NULL | 0 |
| Embeddings | 268/268 |
| PG↔Milvus match | 100% (268/268) |
| Document status | `test_candidate` |
| Pipeline | `likutey_halajot_page_first_v2` |

## Rejection / Alternative

**Incremental page repair.** Rejected. Every repair introduced new boundary
conditions; the absence of a native page store made verification impractical.

**Chunk-first storage with page reconstruction from chunks.** Rejected.
This is the architecture that caused the original problems. Pages are the
natural unit of PDF extraction and printed-book evidence.

## See Also

- ADR-015 (Exact Editorial Evidence Ranking V1)
- `docs/breslov/page-first-and-editorial-retrieval-conventions.md`
- `SrvRestAstroLS_v1/docs/status_actual.md` (Likutey Halajot section)
