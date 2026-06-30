# TebaAI — Breslov Test Milvus Indexing

Fecha: 2026-06-30.
Estado: applied.

## Contexto

Los 476 chunks Sijot-aware de "El Alma del Rebe Najmán" en `breslov_test` fueron indexados en una colección Milvus separada: `tebaai_breslov_test_chunks_v1`.

## Colecciones

| Colección | Propósito | Chunks |
|-----------|-----------|--------|
| `tebaai_breslov_chunks_v1` | Producción Breslov | 1991 (sin cambios) |
| `tebaai_breslov_test_chunks_v1` | Test corpus | 476 |

## Embeddings

| Atributo | Valor |
|----------|-------|
| Proveedor | LiteLLM |
| Modelo | `openai_text_embedding_3_small` |
| Dimensión | 1536 |
| API Key | `LITELLM_MASTER_KEY` (vía env) |
| Batch size | 32 |

## Safety guards

- `breslov_test` solo permite Milvus test (`tebaai_breslov_test_chunks_v1`)
- `breslov` solo permite Milvus productivo (`tebaai_breslov_chunks_v1`)
- Rechaza colección productiva como destino para test
- Rechaza colección test como destino para productivo

## Payload Milvus

Cada vector incluye: `pk`, `chunk_id`, `document_id`, `collection_code`, `language`, `title`, `chunk_index`, `page_start`, `page_end`, `content_preview`, `embedding`.

## Search smoke

| Query | Top | Score | Chunk |
|-------|-----|-------|-------|
| La maravilla del cerebro | Chunk 246 | 0.5933 | Sija #25 |
| Sija 25 | Chunk 2/246 | — | Índice + cuerpo |
| emuná | Varios | — | Section metadata |

## Tests

- `test_milvus_test_indexing.py`: 13 tests (safety guards, payload, dim).
- `pytest` total: 311 PASS (antes 298).

## No contaminación

| Colección | PostgreSQL | Milvus |
|-----------|:----------:|:------:|
| breslov | 1991 | 1991 |
| breslov_test | 476 | 476 |

## Comando usado

```bash
TEBAAI_EMBEDDINGS_API_KEY="\$LITELLM_MASTER_KEY" uv run python -m scripts.index_chunks_milvus \\
  --collection breslov_test \\
  --document-title "El Alma del Rebe Najmán" \\
  --milvus-collection tebaai_breslov_test_chunks_v1 \\
  --apply --batch-size 32
```
