# TebaAI — Breslov Two Books Milvus Test Indexing

Fecha: 2026-06-30.
Estado: applied.

## Objetivo

Indexar los chunks estructurales (heading-aware, lesson-aware) de Kokhavey Ohr y KITZUR en `tebaai_breslov_test_chunks_v1` vía LiteLLM gateway.

## Resultados

| Documento | Chunks PostgreSQL | Indexados Milvus |
|-----------|:-----------------:|:----------------:|
| El Alma del Rebe Najmán | 476 | 476 |
| Kokhavey Ohr | 903 | 903 |
| KITZUR | 636 | 636 |
| **Total test** | **2015** | **2015** |

## Embeddings

| Atributo | Valor |
|----------|-------|
| Proveedor | LiteLLM |
| Modelo alias | `openai_text_embedding_3_small` |
| Modelo upstream | `text-embedding-3-small` |
| Dimensión | 1536 |
| Auth | `TEBAAI_LITELLM_API_KEY` (LiteLLM master key) |

## No contaminación

| Colección | Antes | Después |
|-----------|:-----:|:-------:|
| `tebaai_breslov_test_chunks_v1` | 476 | **2015** |
| `tebaai_breslov_chunks_v1` | 1991 | **1991** (sin cambios) |

## Smoke

Vector search: Kokhavey Ohr returns Kokhavey Ohr chunks (score 0.5874).
Hybrid search with `--milvus-collection tebaai_breslov_test_chunks_v1` works isolated.

## Comandos

```bash
TEBAAI_LITELLM_API_KEY="..." uv run python -m scripts.index_chunks_milvus \\
  --collection breslov_test --document-title "Kokhavey Ohr" \\
  --milvus-collection tebaai_breslov_test_chunks_v1 --apply

TEBAAI_LITELLM_API_KEY="..." uv run python -m scripts.index_chunks_milvus \\
  --collection breslov_test --document-title "KITZUR" \\
  --milvus-collection tebaai_breslov_test_chunks_v1 --apply
```
