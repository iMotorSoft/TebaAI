# TebaAI Breslov — Vector Layer V2 Closure

## Resumen ejecutivo

**Estado final: FULL_OPERATIVE (desarrollo).**

**Decisión: DUAL_BACKEND_AUTO.** Milvus queda como ruta preferida por latencia; pgvector es el fallback operativo con el mismo contrato V2. PostgreSQL conserva texto y páginas como evidencia autoritativa.

## Cambios realizados

| Área | Cambio |
|---|---|
| pgvector | Búsqueda cosine real sobre `library_vector_embeddings_v2_dev` con filtros V2. |
| Milvus | `ensure_loaded(timeout/polling)`, búsqueda V2 sin release posterior. |
| Adapter común | `milvus`, `pgvector`, `auto`, `disabled`; `auto` registra el backend seleccionado y fallos previos. |
| synthesis_qa_v1 | Recuperación vectorial por claim, incorporada a la matriz sin sustituir evidencia PG verificada. |
| Benchmark | Comparación homogénea Milvus/pgvector/auto/SQL-page sobre el corpus real. |
| Tests | Contrato, pgvector, Milvus, auto y presencia de integración de síntesis. |

## Infraestructura y corpus

| Componente | Estado | Observación |
|---|---|---|
| PostgreSQL 18 | ready | Fuente de verdad; pgvector 0.8.2 habilitado. |
| pgvector | ready | Tabla derivada `library_vector_embeddings_v2_dev`. |
| Milvus 2.6 | ready | Colección dev `tebaai_breslov_chunks_v2_dev`, HNSW/COSINE, dim 1536. |
| LiteLLM | ready | Embeddings `openai_text_embedding_3_small`; no se usó OpenAI directo. |
| Runtime de síntesis | `openai_gpt-5.4-nano` configurado | No se confundió con el modelo del agente. |

## pgvector V2

| Check | Resultado |
|---|---|
| extension | `vector` 0.8.2 |
| table | `library_vector_embeddings_v2_dev`, `vector(1536)` + HNSW cosine |
| rows | 506 |
| filtros V2 | scope, collection_code, run_id, document_id, language: PASS |
| search ok | 5/5 hits en smoke real; primer hit p. 29 con filtros completos |
| benchmark p50/p95 | 13.781 ms / 14.841 ms (promedio de casos medidos) |

## Milvus V2

| Check | Resultado |
|---|---|
| collection | `tebaai_breslov_chunks_v2_dev` |
| entities | 506 |
| metadata V2 | scope, collection_code, run_id, document_id, language, page, embedding model/version: PASS |
| ensure_loaded(timeout/polling) | PASS; informa estado antes/después, solicitud, elapsed, timeout y error |
| filters V2 | scope, collection_code, run_id, document_id, language: PASS |
| search ok | 5/5 hits en smoke real; primer hit p. 29 con filtros completos |
| benchmark p50/p95 | 4.896 ms / 5.120 ms (promedio de casos medidos) |

## VectorSearchBackend

| Backend | Health | Search | Filters | Tests |
|---|---|---|---|---|
| milvus | ready | PASS | V2 PASS | PASS |
| pgvector | ready | PASS | V2 PASS | PASS |
| auto | ready, selecciona Milvus | PASS | Hereda V2 | PASS |
| disabled | explicit disabled | `[]` | n/a | PASS |

`auto` intenta Milvus; si no está cargado ejecuta `ensure_loaded`; ante error usa pgvector, y si ambos fallan devuelve lista vacía con diagnóstico (`last_error`) para que el llamador siga con FTS/SQL. No libera colecciones al terminar una búsqueda.

## synthesis_qa_v1

El batch usa el adapter por claim en modo `auto`; la evidencia vectorial se registra como temática (`source_method=vector`) y la cita final sigue validada contra el texto/página PostgreSQL.

| Pregunta | Vector backend | Vector hits | Claims pass | Claims partial | Claims fail | Final |
|---|---|---:|---:|---:|---:|---|
| Teshuvá | milvus | 56 | 7 | 0 | 0 | PASS |
| Pureza sexual | milvus | 40 | 5 | 0 | 0 | PASS |
| Plegaria perfecta | milvus | 40 | 5 | 0 | 0 | PASS |
| Hitbodedut | milvus | 40 | 5 | 0 | 0 | PASS |
| Shabat | milvus | 32 | 4 | 0 | 0 | PASS |
| Punto bueno | milvus | 40 | 5 | 0 | 0 | PASS |
| Temor y ángeles | milvus | 40 | 5 | 0 | 0 | PASS |

## Benchmark comparable

Parámetros: 11 consultas españolas, `top_k=5,10,20`, warmup 2, cinco iteraciones medidas por combinación. La generación LiteLLM del embedding quedó fuera de la ventana de latencia para medir retrieval.

| Backend | p50 | p95 | success_rate | error_rate | notes |
|---|---:|---:|---:|---:|---|
| Milvus | 4.896 ms | 5.120 ms | 1.00 | 0.00 | Ruta preferida. |
| pgvector | 13.781 ms | 14.841 ms | 1.00 | 0.00 | Fallback funcional con filtros SQL. |
| auto | 5.574 ms | 5.815 ms | 1.00 | 0.00 | Resolvió a Milvus. |
| SQL/page | 15.883 ms | 16.575 ms | 1.00 | 0.00 | Referencia literal por página. |

Datos detallados: `benchmark_comparable.json`.

## Reconciliación 506 páginas

El run Kitzur V2 contiene 512 páginas de layout. Se vectorizaron las **506 páginas con texto no vacío**; seis páginas sin texto fueron excluidas de ambos stores derivados. No hay discrepancia de corpus ni backfill incompleto.

## Validaciones ejecutadas

* Smoke real con filtros V2 completos: pgvector, Milvus y auto, 5 hits cada uno.
* `uv run python -m compileall ...`: PASS.
* Tests focalizados: **7 passed**.
* Batch de siete preguntas: **7 PASS**; resultados en `synthesis_qa_v1_vector_results.json`.
* No se modificaron datos fuente; los únicos datos persistentes son los stores vectoriales derivados de desarrollo ya existentes.

## Pendientes reales

Ninguno para operar Vector Layer V2 en desarrollo. La advertencia de deprecación ORM de PyMilvus 2.6 debe abordarse antes de PyMilvus 3.1, pero no afecta la operación actual.
