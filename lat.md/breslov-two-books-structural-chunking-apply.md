# TebaAI — Breslov Two Books Structural Markdown Chunking Apply

Fecha: 2026-06-30.
Estado: applied.

## Objetivo

Aplicar chunking estructural sobre Markdown persistido para Kokhavey Ohr y KITZUR.

## Documentos

| Libro | Strategy | Chunks esperados | Chunks reales |
|-------|----------|----------------:|--------------:|
| Kokhavey Ohr | heading-aware | 903 | 903 |
| KITZUR | lesson-aware | ~651 | 636 |

## Metodología

- Fuente: `library_document_texts.content` (Markdown persistido vía PyMuPDF4LLM).
- Estrategias: `heading-aware` para Kokhavey Ohr (172 H2), `lesson-aware` para KITZUR (494 lessons).
- Metadata: `metadata.chunking` + `metadata.section` por chunk.

## Post-apply

| Colección | Documentos | Chunks |
|-----------|:----------:|:------:|
| breslov | 4 | 7964 |
| breslov_test | 3 | 6045 |

| Documento | Status | Chunks | chunking meta | section meta |
|-----------|--------|------:|:------------:|:------------:|
| El Alma del Rebe Najmán | test_candidate | 476 | 273 | 273 |
| Kokhavey Ohr | test_candidate | 903 | 903 | 903 |
| KITZUR | test_candidate | 636 | 636 | 636 |

## FTS smoke

Las búsquedas FTS retornan resultados de los nuevos libros con `section` visible.

## Tests

- `test_apply_markdown_structural_chunks.py`: 11 tests.
- `pytest`: 376 PASS.

## No contaminación

- `breslov` productivo: 7964 chunks (sin cambios).
- Milvus no tocado. LiteLLM no llamado. Embeddings no generados.

## Comandos

```bash
uv run python -m scripts.chunk_documents --collection breslov_test \\
  --document-title "Kokhavey Ohr" --strategy heading-aware --apply

uv run python -m scripts.chunk_documents --collection breslov_test \\
  --document-title "KITZUR" --strategy lesson-aware --apply
```

## Próxima fase

Page mapping para Kokhavey Ohr y KITZUR o indexar en Milvus test separado.
