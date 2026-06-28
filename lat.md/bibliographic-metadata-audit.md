# TebaAI — Bibliographic Metadata Audit

This audit records what bibliographic structure can be supported by evidence and what must remain unknown.

## Purpose

This document summarizes the bibliographic metadata audit of the Breslov
PDFs loaded in the TebaAI library.

## Current state (2026-06-28)

The initial corpus contained 1,991 chunks without persisted page or chapter metadata.

| Document | Chunks | Page metadata | Chapter metadata | Confidence |
|----------|-------:|:-------------:|:----------------:|:----------:|
| El Jardín de las Almas | 146 | none | none | medium |
| La Potencia de la Plegaria | 643 | none | none | medium |
| Likutey Halajot LM II 8 | 1201 | none | none | medium |

**Total:** 1991 chunks, 0 with page/chapter metadata.

## Key findings

The source text contains useful structural signals, but the original extraction did not preserve reliable page boundaries.

- Page markers exist in extracted text for "La Potencia de la Plegaria"
  and "Likutey Halajot LM II 8" (~30 patterns detected each).
- Heading candidates (markdown `##` lines, "Capítulo", "Lección", "Halajá")
  are detectable in all three books.
- Current chunking was done without page-awareness via `pymupdf4llm.to_markdown()`
  without per-page range extraction. Pages are not preserved in metadata.
- PDF originals are available at `/media/issajar/DEVELOP/Download/Tora/Breslov/`.
- No page, chapter, or section fields are populated in `library_document_chunks`.

## Risks

Heuristic enrichment can create false citations or invalidate derived vectors if chunk boundaries change.

- Page markers from extracted text are heuristic and may be unreliable.
- Heading detection is heuristic; not all headings are structural chapters.
- PDF re-extraction with page awareness would change existing chunk boundaries.
- Enrichment requires careful merge strategy to avoid duplicating vectors.
- Re-chunking changes `chunk_id` and `chunk_uid`, invalidating existing Milvus vectors.

## Recommended strategy

Reliable page metadata requires page-aware extraction, controlled rechunking and retrieval evaluation.

1. **Re-extract PDFs with page-range awareness** using `pymupdf4llm.to_markdown()`
   called per page or per small page range, preserving `page_start`/`page_end`.
2. **Detect headings** from the per-page markdown to infer chapter/section labels.
3. **Create new chunks** with explicit `page_start`, `page_end`, `chapter`, `section`.
4. **Re-index embeddings** for the new chunks to Milvus.
5. **Update evaluation harness** to validate page-level recall.

This is a significant re-processing phase, not a simple metadata update.

## Related files

Scripts and temporary reports provide the reproducible evidence behind this audit.

- Audit script: `scripts/audit_bibliographic_structure.py`
- Temporary MD report: `/tmp/tebaai_breslov_structure_audit.md`
- Temporary JSON report: `/tmp/tebaai_breslov_structure_audit.json`
- PDFs: `/media/issajar/DEVELOP/Download/Tora/Breslov/`
