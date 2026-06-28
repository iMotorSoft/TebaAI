# TebaAI — Page-Aware Metadata Mapping Audit

This audit measures whether existing chunks can be mapped to physical PDF pages without inventing bibliographic precision.

## Purpose

This document summarizes the page↔chunk mapping audit for the Breslov
PDFs. It evaluates whether existing chunks can be reliably associated
with physical PDF pages without re-extraction.

## Results

The mapping audit found useful page evidence for 52.3% of the 1,990 chunks evaluated.

| Document | PDF pages | Chunks | High | Medium | Low | None | Useful % |
|----------|----------:|-------:|-----:|-------:|----:|-----:|---------:|
| El Jardín de las Almas | 94 | 146 | 83 | 32 | 29 | 2 | 78.8% |
| La Potencia de la Plegaria | 416 | 643 | 113 | 220 | 181 | 129 | 51.8% |
| Likutey Halajot LM II 8 | 527 | 1201 | 192 | 401 | 265 | 343 | 49.4% |
| **Total** | **1037** | **1990** | **388** | **653** | **475** | **474** | **52.3%** |

## Findings

Mapping quality varies materially by document and extraction characteristics.

- **El Jardín de las Almas**: strong mapping (78.8% useful). High-quality
  anchors, good text-page correlation. 2 unmapped chunks only.
- **La Potencia de la Plegaria**: moderate (51.8%). 129 chunks unmapped.
  Heading candidates limited; page markers present but anchor matching
  was weaker.
- **Likutey Halajot LM II 8**: moderate (49.4%). 343 chunks unmapped.
  Largest document with mixed Hebrew/Spanish content affecting anchor
  matching.

## Risks

Physical page mapping remains probabilistic and must not be presented as printed pagination.

- PDF page numbers are physical, not printed book page numbers.
- Mapping depends on text extraction quality from PyMuPDF.
- Ambiguous chunks may cross structural boundaries (30 in Likutey).
- Low-confidence chunks should not be enriched without review.

## Recommended strategy

Enrich only high-confidence mappings and re-extract the uncertain remainder when page precision is required.

1. **Enrich high-confidence chunks first** (388 chunks, ~20%).
2. **Validate medium-confidence by sampling** (653 chunks, ~33%).
3. **For low-confidence/unmapped**: re-extract PDFs with page-range
   awareness via `pymupdf4llm.to_markdown(pages=...)`.
4. **Never invent** page numbers or chapter labels.
5. **Re-index Milvus only if chunk content/boundaries change**.

## Related files

The audit script and generated reports contain the detailed mapping evidence.

- Audit script: `scripts/audit_page_chunk_mapping.py`
- Temporary MD report: `/tmp/tebaai_breslov_page_chunk_mapping.md`
- Temporary JSON report: `/tmp/tebaai_breslov_page_chunk_mapping.json`
- PDFs: `/media/issajar/DEVELOP/Download/Tora/Breslov/`
