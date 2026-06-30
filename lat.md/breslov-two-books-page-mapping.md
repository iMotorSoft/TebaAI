# TebaAI — Breslov Two Books Page Mapping

Fecha: 2026-06-30.
Estado: applied.

## Objetivo

Page mapping real para chunks estructurales (heading-aware, lesson-aware) de Kokhavey Ohr y KITZUR usando normalization_plus.

## Resultados

| Documento | Chunks | High-confidence | Invalid ranges |
|-----------|------:|---------------:|:--------------:|
| Kokhavey Ohr | 903 | 395 (43.7%) | 0 |
| KITZUR | 636 | 222 (34.9%) | 0 |

## Metadata

- `bibliographic_metadata.chunking` preservado
- `bibliographic_metadata.section` preservado
- `bibliographic_metadata.page_mapping` agregado

Reference labels incluyen `section_label` + `PDF page(s)`.

## No contaminación

| Colección | Chunks |
|-----------|:------:|
| breslov | 7964 (sin cambios) |
| breslov_test | 6045 |

## Tests

- `test_page_mapping_markdown_chunks.py`: 10 tests (normalization_plus para Markdown, anchors, safety).
- `pytest`: 386 PASS.

## Comandos

```bash
uv run python -m scripts.enrich_chunk_page_metadata \\
  --collection breslov_test --document-title "Kokhavey Ohr" \\
  --strategy normalization_plus --apply

uv run python -m scripts.enrich_chunk_page_metadata \\
  --collection breslov_test --document-title "KITZUR" \\
  --strategy normalization_plus --apply
```

## Próxima fase

Indexar chunks nuevos en Milvus test separado o validar búsqueda híbrida aislada.
