# TebaAI — Page Mapping Failure Diagnosis

This diagnosis explains the low high-confidence page coverage in the two largest Breslov documents without changing bibliographic metadata.

## Scope and safety

The diagnostic command reads PostgreSQL chunks inside an explicit read-only transaction and compares them with local PDF extraction.

- Script: `scripts/diagnose_page_mapping_failures.py`
- Documents: `La Potencia de la Plegaria` and `Likutey Halajot LM II 8`
- Samples: 50 evenly distributed unmapped chunks per document
- Holdout: up to 25 already-mapped high-confidence chunks per document
- Page numbering: physical PDF pages, not printed pagination
- No PostgreSQL metadata, chunks, embeddings or Milvus entities were changed.
- No LiteLLM or generative model was called.

## Findings

The main failure is not missing source text. It is a representation mismatch between full-document `pymupdf4llm` extraction, from which chunks were created, and page-level PyMuPDF extraction used by the baseline mapper.

| Document | Total | Mapped | Unmapped | Full extraction anchor | Page baseline anchor | Full-only gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| La Potencia de la Plegaria | 643 | 73 | 570 | 50/50 | 36/50 | 14/50 |
| Likutey Halajot LM II 8 | 1201 | 128 | 1073 | 50/50 | 33/50 | 17/50 |

Every sampled chunk remained identifiable in full-document extraction. Page-level baseline extraction lost all exact anchors for 28% of Potencia samples and 34% of Likutey samples.

### Primary failure categories

Boundary and layout differences dominate both 50-chunk samples; hyphenation, repetition and extreme chunk length do not.

| Category | Potencia | Likutey | Interpretation |
| --- | ---: | ---: | --- |
| Start match only | 13 | 10 | Chunk endings fall across page/layout boundaries. |
| End match only | 14 | 16 | Chunk beginnings include extraction or boundary differences. |
| Cross-page uncertain | 5 | 7 | Both boundaries carry evidence but do not satisfy a safe range. |
| Hyphenation or linebreak | 2 | 0 | Minor contributor, limited to Potencia in this sample. |
| Layout order mismatch | 16 | 14 | Full extraction contains the anchor but page order/format weakens exact matching. |
| OCR or extraction difference | 0 | 3 | Likutey has a small residual extraction gap. |
| Repeated/ambiguous primary cause | 0 | 0 | Repetition was not a dominant sampled cause. |

Headers/footer removal produced no incremental candidates over normalization. Chunk lengths were generally consistent with the configured chunk size: median 1591 characters for Potencia and 1524 for Likutey. No sampled chunk met the diagnostic `CHUNK_TOO_LONG` threshold, although start/end evidence shows that ordinary chunks often cross physical page boundaries because original chunking was full-document and not page-aware.

## Strategy dry-runs

Candidate totals below are measured on 50 unmapped chunks per document. Estimated new-high counts extrapolate those samples and are not approved metadata counts.

| Strategy | Potencia H/M/A | Likutey H/M/A | Holdout high precision | Risk | Automatic apply |
| --- | --- | --- | --- | --- | --- |
| Baseline current matcher | 0/23/0 | 0/18/0 | 100% / 100% | low | no new high candidates |
| Normalization plus | 40/8/0 | 43/6/1 | 96% / 100% | low | Potencia: no; Likutey: candidate |
| Hyphenation fix | 40/8/0 | 43/6/1 | 96% / 100% | low | no incremental gain |
| Header/footer strip | 40/8/0 | 43/6/1 | 96% / 100% | low | no incremental gain |
| Sliding-window similarity | 15/17/3 | 3/17/4 | 100% / 100% on limited high predictions | medium | no |
| Relaxed medium candidate | 0/47/1 | 0/47/3 | no high predictions | high | no |

`normalization_plus` removes accent and punctuation variance, removes Markdown marks, collapses whitespace and uses 100-character anchors while preserving the existing start/end confidence rules. It estimates 456 new-high Potencia candidates and 923 new-high Likutey candidates, but those projections depend on the 50-chunk samples.

## Decision

The next implementation should refine the low-risk normalization path and preserve strict unambiguous start/end evidence.

1. Treat `normalization_plus` as the primary candidate.
2. Require zero exact-range regressions on a larger mapped holdout before applying it to Potencia.
3. Keep ambiguity excluded from high confidence.
4. Do not add hyphenation or header/footer passes unless they demonstrate incremental gain.
5. Keep sliding similarity as diagnostic evidence, not an automatic high-confidence mapper.
6. Keep relaxed matches in medium-confidence review only.

## Not applied

This phase did not apply high, medium, low or ambiguous metadata.

It did not update PostgreSQL, change chunk content or identity, re-extract/reingest PDFs, recalculate embeddings, query or reindex Milvus, call LiteLLM, add chapter/section metadata, or introduce RAG.

## Limitations

The evidence supports a next experiment, not a corpus-wide accuracy guarantee.

- Counts and strategy projections depend on deterministic samples.
- Holdout validation covers at most 25 existing high-confidence mappings per document.
- Existing high-confidence metadata is the holdout reference and is not an independent human-labelled gold set.
- Physical PDF pages remain distinct from printed book pages.
- Chapter and section mapping remain pending.
