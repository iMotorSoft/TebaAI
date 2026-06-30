# TebaAI — Breslov Additional Test Books Ingestion

Fecha: 2026-06-30.
Estado: ingested.

## Objetivo

Ingestar dos nuevos PDFs como `test_candidate` en `breslov_test` usando PyMuPDF4LLM (Markdown canónico).

## Libros

| Libro | Archivo | Idioma | Páginas | Chars Markdown |
|-------|---------|--------|-------:|---------------:|
| Kokhavey Ohr | Kokhavey Ohr layout BH_PRINT-4.pdf | en | 576 | 1,136,153 |
| KITZUR | KITZUR ultimo(createspace).pdf | es | 512 | 1,003,612 |

## Extracción

| Atributo | Valor |
|----------|-------|
| Extractor | `pymupdf4llm` 1.27.2.3 |
| Formato | Markdown |
| OCR | No requerido |

## Resultados

| Libro | Status | Chunks | Milvus | LiteLLM |
|-------|--------|:------:|:------:|:-------:|
| Kokhavey Ohr | test_candidate | 0 | No tocado | No llamado |
| KITZUR | test_candidate | 0 | No tocado | No llamado |

## No contaminación

| Colección | Documentos | Chunks |
|-----------|:----------:|:------:|
| breslov | 4 | 7964 |
| breslov_test | 3 | 476 (solo El Alma) |

## Comando

```bash
uv run python -m scripts.ingest_document \\
  --collection breslov_test --status test_candidate \\
  --file "path/to.pdf" --title "Title" --language en \\
  --metadata-json '{...}' --apply
```
