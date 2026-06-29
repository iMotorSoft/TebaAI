# TebaAI — El Alma del Rebe Najmán Chunking Strategy Audit

This document records the dry-run comparison of generic vs section-aware (sijot-aware) chunking for the test candidate document.

## Purpose

Compare two chunking strategies for `El Alma del Rebe Najmán` (collection `breslov_test`, status `test_candidate`) and produce a technical recommendation for the next phase.

## Document

| Attribute | Value |
|-----------|-------|
| Title | El Alma del Rebe Najmán |
| Collection | `breslov_test` |
| Status | `test_candidate` |
| Text | 643,028 characters |
| Chunks (pre-audit) | 0 |
| Milvus | not indexed |

## Script

`scripts/compare_chunking_strategies.py` implements the dry-run comparison CLI. Strategies compared: `generic` (current paragraph-based) and `sijot-aware` (section-aware). No PostgreSQL writes occur.

## Constraints

No chunks were inserted into PostgreSQL, no Milvus or LiteLLM calls made, and no changes to the `breslov` production collection. All analysis is in-memory.

## Audit findings

The audit executed as a dry-run. Detailed metrics, section detection, page mapping simulation and simulated searches are documented in the generated reports.

### Generic strategy

| Metric | Expected approx | Actual |
|--------|----------------:|------:|

### Sijot-aware strategy

| Metric | Value |
|--------|------:|

### Section detection

| Metric | Value |
|--------|------:|
| Sijot 1–52 detected | |

### Recommendation

| Option | Decision | Motivo |
|--------|----------|--------|
| **A/B/C/D** | | |

## Related files

The compare script, its tests, and the generated reports form the complete audit artifact set.
See `scripts/compare_chunking_strategies.py`, `tests/test_compare_chunking_strategies.py`, and `/tmp/tebaai_el_alma_chunking_compare.json` / `.md`.