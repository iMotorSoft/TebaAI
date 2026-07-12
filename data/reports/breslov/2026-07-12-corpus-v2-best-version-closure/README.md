# TebaAI Breslov — Corpus V2 Best Version Closure

## Resumen ejecutivo

**Estado: PASS_WITH_LIMITATIONS**

| Decisión de reconstrucción | Valor |
|---|---|
| REUSE_DERIVED_WITH_FIXES | No |
| DROP_AND_REBUILD_VECTOR_DERIVED | **Sí** |
| REINGEST_KITZUR_V2 | No (páginas fuente correctas) |

## Cambios realizados

1. **Auditoría profunda del corpus V2** — página a página, metadata, vectores.
2. **Drop y recreación de `library_vector_embeddings_v2_dev`** (pgvector) — se eliminó la tabla con 506 registros con `collection_code=breslov_test` incorrecto.
3. **Drop y recreación de `tebaai_breslov_chunks_v2_dev`** (Milvus) — se eliminó la colección con metadata incorrecta.
4. **Backfill completo** — 506 embeddings regenerados vía LiteLLM (`openai_text_embedding_3_small`, dim=1536).
5. **Metadata corregida** — `knowledge_scope_code=breslov_primary`, `collection_code=breslov_primary`.
6. **VectorSearchBackend verificado** — Milvus, pgvector, auto (Milvus preferido, pgvector fallback), disabled.
7. **Nivel 4 re-ejecutado** — 29/29 claims PASS, 290 hits vectoriales (vs. 0 antes de la corrección).
8. **Test suite ampliada** — 732 tests (24 nuevos), todos PASS.

## Corpus audit

| Check | Resultado |
|---|---|
| Total pages | 512 |
| With text | 506 |
| Without text | 6 (páginas 8, 10, 12, 414, 416, 418 — blancas/separadores) |
| run_id complete | 506/506 |
| document_id complete | 506/506 |
| scope complete (breslov_primary) | 506/506 |
| language complete (es) | 506/506 |
| 506 vs 512 explained | 6 páginas sin texto (portadas/separadores internos del PDF) |

### Páginas sin texto

| Página | Tipo | Justificación |
|---|---|---|
| 8 | Blanca | Separador entre secciones del libro |
| 10 | Blanca | Separador |
| 12 | Blanca | Separador |
| 414 | Blanca | Separador |
| 416 | Blanca | Separador |
| 418 | Blanca | Separador |

Son páginas intencionalmente en blanco en el PDF original. No constituyen error de extracción.

## Rebuild / Backfill

| Backend | Expected | Inserted | Skipped | Errors | Status |
|---|---:|---:|---:|---:|---|
| pgvector | 506 | 506 | 0 | 0 | PASS |
| Milvus | 506 | 506 | 0 | 0 | PASS |

### Parámetros de backfill

- `run_id`: `492acd8d-06bd-42ac-a511-f3ec52f97bb3`
- `scope`: `breslov_primary`
- `collection_code`: `breslov_primary`
- `backend`: `both`
- `embedding`: `openai_text_embedding_3_small` (1536 dim)
- `batch_size`: 64

## Vector Layer

| Backend | Status | Filters V2 | Hit count | Notas |
|---|---|---|---|---|
| Milvus | PASS | scope, run_id, language, page | 5/5 | HNSW/COSINE |
| pgvector | PASS | scope, run_id, document_id, language | 5/5 | HNSW/COSINE |
| auto | PASS | scope → Milvus, fallback → pgvector | 5/5 | Milvus preferido |
| SQL/page | PASS | run_id, page_number | 46/46 | Búsqueda directa |

## Level 4 result (post-rebuild)

Resultados tras la corrección de `collection_code`:

| Área | Antes | Después |
|---|---|---|
| claims PASS | 29/29 | 29/29 |
| vector hits total | 0 | **290** |
| relations PASS | 9 | 9 |
| relations INFERRED | 6 | 6 |
| AI synthesis | 7079 chars | N/A (no-AI run) |
| Fallback determinístico | 9071 chars | 9071 chars |

La corrección principal: los vectores ahora responden a `knowledge_scope_code=breslov_primary` porque así fueron backfilleados.

## Citation audit

| Check | Resultado |
|---|---|
| AI citations standard | Pendiente (requiere refinamiento de prompt) |
| Fallback citations standard | PASS — usa formato `**claim_id** → p. N` |
| Unknown citations rejected | PASS — fallback no inventa |
| All cited pages in evidence matrix | PASS |

## Vector Benchmark (post-rebuild)

| Query | pgvector p50 | pgvector hits | Milvus p50 | Milvus hits |
|---|---|---|---|---|
| humildad orgullo daat | ~10ms | 5 | ~5ms | 5 |

## Tests

| Suite | Tests | Resultado |
|---|---|---|
| `test_corpus_v2_integrity` | 10 | PASS |
| `test_citation_format` | 8 | PASS |
| `test_relation_qa_level4_integration` | 6 | PASS |
| `test_synthesis_qa_level4_claims` | 19 | PASS |
| `test_synthesis_qa_level4_relations` | 9 | PASS |
| `test_synthesis_qa_level4_output` | 11 | PASS |
| `test_vector_backend_contract` | 1 | PASS |
| `test_synthesis_qa_v1_vector_integration` | 1 | PASS |
| `test_library_synthesis_qa_v1_batch` | 2 | PASS |
| **Full suite** | **732** | **ALL PASS** |

## Limitaciones reales

1. **Descomposición automática**: la de pregunta → claims sigue siendo manual.
2. **Relation QA**: no está integrado en el pipeline Level 4. Las relaciones inferidas (6/15) no se benefician del análisis detallado de co-ocurrencia.
3. **Formato de citas AI**: el prompt de síntesis AI produce citas no estándar. Se requiere refinamiento.
4. **Chunking**: el corpus V2 usa página como unidad de evidencia, no chunk semántico. No hay `library_document_chunks` para el Kitzur V2. Esto es una limitación estructural que afecta la granularidad de la búsqueda.
5. **PyMilvus ORM deprecado**: las APIs ORM (`Collection`, `connections`) serán eliminadas en PyMilvus 3.1. Migrar a `MilvusClient`.

## Próximo paso

1. Implementar descomposición automática Nivel 4 (`--decomposition ai`).
2. Integrar Relation QA en el pipeline Level 4.
3. Refinar prompt de síntesis AI para citas estandarizadas.
4. Migrar PyMilvus a MilvusClient (API moderna).
