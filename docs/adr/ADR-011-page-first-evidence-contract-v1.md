# ADR-011: Page-First Evidence Contract V1

**Status:** Accepted (DEV)

**Date:** 2026-07-30

## Context

The research pipeline's evidence model used flat chunk references with `pdf_page`, `printed_page`, and `section` as unstructured fields. Evidence was tied to chunks, not pages, making it impossible to:
- Verify page context around a quote
- Identify the exact position within a page
- Trace the containing section heading
- Separate AI-generated `answer_markdown` from structured evidence

## Decision

Adopt a **page-first evidence contract** where:

```
Document
└── CanonicalPage (assembled from chunks sharing page_start)
    ├── StructuralHeading
    ├── StructuralBlock
    ├── Paragraph
    ├── SemanticChunk
    └── EvidenceLocation (exact quote + offsets + page refs)
```

## Contract

Evidence entries now include these page-first fields (all optional, backward-compatible):

| Field | Type | Description |
|-------|------|-------------|
| `page_id` | `str\|null` | Canonical page identifier (from pages_v2 or null) |
| `pdf_page` | `int\|null` | Physical PDF page number |
| `printed_page` | `int\|null` | Printed/folio page number |
| `heading_text` | `str\|null` | The editorial heading containing the evidence |
| `heading_level` | `int\|null` | Heading nesting level (future) |
| `heading_source` | `str\|null` | Source of heading: `section_title`, `structural_heading_candidate`, `markdown_heading_before`, `heading_candidates_list`, `none` |
| `section_path` | `list[str]` | Hierarchical path of containing sections |
| `exact_quote` | `str\|null` | Exact matched text from the canonical page |
| `context_before` | `str\|null` | Text preceding the quote (up to 200 chars) |
| `context_after` | `str\|null` | Text following the quote (up to 200 chars) |
| `start_offset` | `int\|null` | Character offset of quote in canonical page |
| `end_offset` | `int\|null` | End character offset |
| `location_precision` | `str` | Precision level: `exact`, `normalized_exact`, `token_span`, `block_level`, `approximate`, `unresolved` |
| `block_id` | `str\|null` | Block identifier when chunk-level |
| `canonical_page_source` | `str` | How page was assembled: `assembled_from_chunks`, `pages_v2`, `empty` |
| `page_resolution_method` | `str` | How page was resolved: `explicit_page_id`, `page_anchor`, `chunk_page_start`, `page_marker_inference` |

## Architecture

### Layer separation

1. **Retrieval** — selects candidate chunks (unchanged)
2. **Page resolution** (`resolve_page_for_retrieval_hit`) — maps chunk → canonical page
3. **Canonical page assembly** (`assemble_page_text`) — builds page text from same-page chunks
4. **Evidence localization** (`locate_evidence_within_page`) — finds exact quote, offsets, precision
5. **Section resolution** (`resolve_containing_section`) — identifies editorial heading
6. **Context extraction** (`extract_context`) — captures before/after text

### Resolution priority

Page resolution prefers in order:
1. Explicit `page_id` foreign key
2. `page_anchor` reference
3. Chunk `page_start` as `pdf_page`
4. `printed_page_label`
5. Page marker inference (minimum confidence)

Heading resolution prefers:
1. `section_title` on the chunk
2. Structural heading candidate from heading search
3. Preceding Markdown heading in page
4. `heading_candidates` from the retrieval layer
5. `none` — tolerated without error

## New files

- `backend/modules/library/page_first_evidence.py` — core models and resolution logic
- `backend/tests/test_page_first_evidence.py` — 27 unit tests

## Modified files

- `backend/modules/library/simple_research_rag.py` — page-first enrichment hook + V1 fields in evidence + hits
- `astro/src/components/research/SourcePanel.svelte` — display V1 fields

## Limits

- No `pages_v2` entries exist for Likutey Halajot (the pilot document). Pages are assembled from chunks sharing `page_start`.
- No full PDF viewer implemented — page `text` is available in the canonical page object but not exposed in the API response (future).
- `heading_level` is always `null` in V1 — hierarchical depth requires section tree integration.
- `page_id` is `null` when no `pages_v2` entry exists — the page is still resolvable via `page_start`.

## Next phase

**Bibliographic Query Planner V1** — counting sections, excluding works, grouping by volume, and cross-referencing.

Not started in this gate.
