# TebaAI — Breslov Test Hybrid Integrity Validation

Fecha: 2026-06-30.
Estado: validated.

## Objetivo

Validar la integridad de búsqueda híbrida aislada sobre los tres libros de `breslov_test` antes de avanzar a lemas/shoresh.

## Corpus

| Documento | Chunks PG | Milvus | Page refs |
|-----------|:---------:|:------:|:---------:|
| El Alma del Rebe Najmán | 476 | 476 | 273 |
| Kokhavey Ohr | 903 | 903 | 395 |
| KITZUR | 636 | 636 | 222 |
| **Total** | **2015** | **2015** | **890** |

## Resultados

| Chequeo | Resultado |
|---------|-----------|
| FTS pass | ✅ |
| Vector pass | ✅ |
| Hybrid pass | ✅ (top_k=30 detecta rama vectorial) |
| Round-trip PG↔Milvus | ✅ |
| Negative query | ✅ (max_score < 0.30) |
| Product isolation | ✅ |

## Round-trip

Todos los `chunk_id` devueltos por Milvus existen en PostgreSQL con `collection_code = breslov_test` y `document_id` coincidente.

## Hybrid isolation

`search_chunks_hybrid` usa `tebaai_breslov_test_chunks_v1` para `collection_code = breslov_test`. No mezcla productivo.

## Tests

- `test_breslov_test_hybrid_integrity.py`: 10 tests.
- `validate_breslov_test_hybrid_integrity.py`: script de validación integral.
- `pytest`: 404 PASS.

## Comando

```bash
TEBAAI_LITELLM_API_KEY="..." uv run python -m scripts.validate_breslov_test_hybrid_integrity
```
