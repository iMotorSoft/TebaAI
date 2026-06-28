# TebaAI — Page Metadata Enrichment

## Purpose

This document records the enrichment of `library_document_chunks` with
high-confidence page metadata derived from page-aware PDF auditing.

## Migration 007

- File: `db/migrations/007_add_library_chunk_bibliographic_metadata.sql`
- Columns added: `page_start`, `page_end`, `chapter`, `section`,
  `paragraph_index`, `reference_label`, `bibliographic_metadata`
- Constraints: positive page numbers, page_end >= page_start
- Indexes: document+page, reference_label

## Enrichment criteria

Only chunks with `confidence = high` from the page-aware mapping audit
were enriched. High confidence requires:
- Start and end anchors found on the same page with ≥60% hit rate, OR
- Start and end anchors on different pages with ≥50% hit rate (cross-page)
- No ambiguity (anchors spread across non-adjacent pages)

## Results

| Document | High-confidence | Total chunks | Coverage |
|----------|---------------:|------------:|---------:|
| El Jardín de las Almas | 83 | 146 | 56.8% |
| La Potencia de la Plegaria | 73 | 643 | 11.4% |
| Likutey Halajot LM II 8 | 128 | 1201 | 10.7% |
| **Total** | **284** | **1990** | **14.3%** |

## Notes

- Pages are physical PDF page numbers, not printed book page numbers.
- Medium/low/none confidence chunks were not enriched.
- Chapter/section fields were NOT populated (deferred to future phase).
- No chunk content, chunk_id, FTS vectors, embeddings, or Milvus were modified.
- Evaluation metrics unchanged after enrichment (26/30 PASS hybrid).

## Related files

- Enrichment script: `scripts/enrich_chunk_page_metadata.py`
- Audit script: `scripts/audit_page_chunk_mapping.py`
