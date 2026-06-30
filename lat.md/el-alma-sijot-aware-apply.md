# TebaAI — El Alma del Rebe Najmán Sijot-aware Apply

Fecha: 2026-06-30.
Estado: applied.

## Contexto

Tras la validación Loop 0 real (52/52 Sijot detectadas, recomendación B), se procedió a aplicar chunking Sijot-aware en `breslov_test`.

## Documento

| Atributo | Valor |
|----------|-------|
| Título | El Alma del Rebe Najmán |
| Colección | `breslov_test` |
| Status | `test_candidate` |
| Texto | 643,028 caracteres |
| Chunks antes | 0 |
| Chunks después | 476 |

## Métricas de dry-run

| Métrica | Valor |
|---------|-------|
| Estrategia | `sijot-aware` |
| Chunks | 476 |
| Sijot detectadas | 52/52 |
| Missing Sijot | 0 |
| Chunks cross-section | 0 |
| Chunks con metadata section | 464 (97.5%) |

## Métricas de apply

| Métrica | Valor |
|---------|-------|
| Chunks creados | 476 |
| breslov_test total | 476 |
| breslov productivo | 1991 (sin cambios) |

## Metadata estructural

Cada chunk incluye:

```json
{
  "chunking": {
    "strategy": "sijot-aware",
    "source": "compare_chunking_strategies.py",
    "validated_by": "Loop 0 real",
    "document_status": "test_candidate"
  },
  "section": {
    "section_type": "sija|prefacio|creditos|indice|glosario|preamble",
    "section_number": 1–52,
    "section_label": "...",
    "section_title": "..."
  }
}
```

## FTS smoke

Las 7 búsquedas simuladas retornan resultados de `breslov_test`. FTS español y simple funcionan.

## No contaminación

| Colección | Chunks antes | Chunks después | Delta |
|-----------|:-----------:|:--------------:|:-----:|
| breslov | 1991 | 1991 | 0 |
| breslov_test | 0 | 476 | +476 |

## Tests

- `test_sijot_aware_chunk_apply.py`: 11 tests para conversión TemporaryChunk → DB format.
- `pytest` total: 282 PASS (antes 271).

## Limitaciones

- Documento sigue `test_candidate`.
- Milvus no indexado.
- Sin embeddings.
- Sin RAG.
- Page mapping pendiente.

## Comando usado

```bash
# Dry-run
uv run python -m scripts.chunk_documents \\
  --collection breslov_test \\
  --document-title "El Alma del Rebe Najmán" \\
  --strategy sijot-aware --dry-run

# Apply
uv run python -m scripts.chunk_documents \\
  --collection breslov_test \\
  --document-title "El Alma del Rebe Najmán" \\
  --strategy sijot-aware --apply
```
