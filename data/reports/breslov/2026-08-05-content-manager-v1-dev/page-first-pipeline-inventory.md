# Page-first pipeline inventory

## Existing scripts

`ingest_likutey_halajot_page_first_v2.py`, `ingest_lmii_page_first.py`, `ingest_likutey_moharan_xv_kdp_page_first_column_aware.py` and related scripts prove page-first persistence but are not reusable worker services. They contain absolute/local source paths, document codes, edition/run IDs, fixed titles/page assumptions, work-specific heading and note rules, direct connection setup and CLI-side effects.

## Extracted common contract

`modules/library/page_first_pipeline.py` now owns typed input/output and generic stages. It uses canonical PyMuPDF4LLM per physical page, retains original Markdown, builds a separate NFKC/ligature-normalized search surface, preserves Hebrew/niqqud, detects conservative headings/footnotes/printed references, preserves empty pages and emits warnings instead of unsafe editorial inference.

`page_first_gateway.py` owns PostgreSQL/LiteLLM/Milvus effects. The worker imports the service directly; no shell, subprocess, filename dispatch or document-specific code is used.
