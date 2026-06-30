# TebaAI — Breslov Test Hybrid Search Validation

Fecha: 2026-06-30.
Estado: validated.

## Objetivo

Validar búsqueda híbrida aislada para `breslov_test` usando PostgreSQL FTS + Milvus `tebaai_breslov_test_chunks_v1` + LiteLLM embeddings gateway.

## Colecciones usadas

| Componente | Producción | Test |
|-----------|-----------|------|
| PostgreSQL | `breslov` | `breslov_test` |
| Milvus | `tebaai_breslov_chunks_v1` | `tebaai_breslov_test_chunks_v1` |
| Embeddings | LiteLLM (`openai_text_embedding_3_small`) | Mismo gateway |

## Safety guards

| Combinación | Resultado |
|-------------|-----------|
| breslov_test + tebaai_breslov_chunks_v1 | ❌ Rechazado |
| breslov + tebaai_breslov_test_chunks_v1 | ❌ Rechazado |
| breslov_test + tebaai_breslov_test_chunks_v1 | ✅ Aceptado |
| breslov + tebaai_breslov_chunks_v1 | ✅ Aceptado |

## Smoke results

| Query | FTS top | Milvus top | Hybrid top |
|-------|---------|------------|------------|
| La maravilla del cerebro | Chunk 246 (Sija #25) | Chunk 246 (0.5933) | Chunk 245/246 hybrid |
| Sija 25 | Chunk 2 (índice) | — | Chunk 2 FTS |

## CLI

```bash
uv run python -m scripts.search_library_text \\
  --collection breslov_test \\
  --milvus-collection tebaai_breslov_test_chunks_v1 \\
  --query "consulta" --mode hybrid --top-k 10
```

## No contaminación

| Colección | PostgreSQL | Milvus |
|-----------|:----------:|:------:|
| breslov | 1991 | 1991 |
| breslov_test | 476 | 476 |

## Tests

- `test_hybrid_breslov_test_isolation.py`: 10 tests (guards, hybrid params, CLI).
- `pytest` total: 332 PASS.

## Limitaciones

- Documento sigue `test_candidate`.
- Sin RAG.
- Sin frontend.
- Ranking: chunk 2 (índice) puede tener FTS rank más alto que chunk 246 (cuerpo) para "Sija 25".
