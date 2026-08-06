# TebaAI Breslov — Vector Store Decision

## Resumen ejecutivo

Decisión: **MILVUS_KEEP_PRIMARY_WITH_FIXES**.

Milvus no es una capa inútil ni una razón para migrar a pgvector: el safe-load controlado de la colección V2 existente cambió `NotLoad` a `Loaded` y una búsqueda vectorial read-only respondió correctamente. El benchmark aislado mostró p50 promedio de **2,24 ms** para Milvus frente a **9,27 ms** para SQL/page. Sin embargo, la integración V2 aún no es confiable: el índice de páginas carece de metadata V2 para filtros y el helper híbrido libera la colección entre consultas sin esperar que un nuevo `load()` quede ready.

pgvector no está instalado ni hay datos comparables; no es un fallback implementable ni medible hoy. No se recomienda migración.

## Infraestructura

| Componente | Estado | Observación |
|---|---|---|
| PostgreSQL | PASS | Read-only; fuente de verdad y baseline SQL/page. |
| Milvus service | PASS | Conexión, metadata, query y búsqueda V2 safe-load funcionaron. |
| Milvus collection V2 | PASS con política de carga | Antes NotLoad; safe-load explícito la dejó Loaded. |
| LiteLLM embeddings | PASS | Generó sólo vectores de consulta para probes, sin indexación. |
| pgvector | **PGVECTOR_NOT_INSTALLED** | Sin extensión ni schema/vector data. |
| Backend dev | PASS | No se reinició ningún servicio permanente. |

## Milvus status

| Check | Resultado |
|---|---|
| connection_ok | yes |
| collection detectada | `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1` |
| collection exists | yes |
| load_state_before | `NotLoad` |
| safe-load | explícito, 1 sola colección, sin escritura |
| load_state_after_safe_load | `Loaded` |
| num_entities | 100 |
| schema/index | embedding 1536, HNSW / COSINE |
| metadata query after load | yes |
| vector search after load | yes |
| search before load | omitida: correctamente reportada como NotLoad |

Los estados antes/después están en [milvus_status_before.json](milvus_status_before.json) y [milvus_status_after_safe_load.json](milvus_status_after_safe_load.json).

## PostgreSQL vs Milvus

| Métrica | PostgreSQL esperado | Milvus observado | Match |
|---|---:|---:|---|
| Kitzur run V2 páginas | 512 | 100 entidades de página | no: subset/cobertura pendiente |
| V2 run id | `492acd8d-…` | no existe en schema | no |
| V2 document id | `dffa06db-…` | no existe en schema | no |
| V2 scope | `breslov_test` | no existe en schema | no |
| V1 productivo | 5.102 chunks esperados | 5.102 entidades | sí, conteo observado |
| V1 collection alias | scope lógico `breslov_primary` | metadata `collection_code=breslov` | sí, alias conocido |

Esto confirma dos problemas distintos: el `NotLoad` era operativo y se resolvió con safe-load; el contrato V2 de metadata está incompleto y no permite filtros seguros por run/document/scope.

## pgvector status

| Check | Resultado |
|---|---|
| extension_installed | no |
| vector tables exist | no |
| comparable data exists | no |
| benchmark possible | no |

Ver [pgvector_status.json](pgvector_status.json). No se instaló extensión, no se creó schema ni se copiaron embeddings.

## Benchmark

10 queries, 2 warmups, 5 iteraciones medidas, `top_k=5,10,20`; el tiempo de embedding se precalculó y no forma parte de la latencia de retrieval.

| Backend | p50 ms | p95 ms | success rate | expected hit rate | error rate |
|---|---:|---:|---:|---:|---:|
| SQL/page V2 | 9,27 | 9,92 | 100% | no evaluado con oracle por query | 0% |
| Milvus V2 cargado | 2,24 | 2,38 | 100% | no evaluado con oracle por query | 0% |
| pgvector | N/A | N/A | N/A | N/A | N/A |

Datos: [vector_benchmark.json](vector_benchmark.json). La comparación mide backend de página SQL contra índice V2 de 100 páginas; no es aún una evaluación de recall de 512 páginas.

## Reliability

| Scenario | Resultado | Observación |
|---|---|---|
| Milvus not loaded | claro | Probe devuelve `COLLECTION_FOUND_NOT_LOADED`; no intenta search. |
| safe load | PASS | `Collection.load()` sólo tras flag explícito y espera de readiness. |
| wrong collection | PASS | El probe diferencia `COLLECTION_NOT_FOUND`. |
| scope filter V1 | disponible como `collection_code=breslov` | Contrato V1. |
| run_id/document V2 | FAIL de contrato | Campos ausentes del schema V2. |
| batch synthesis hybrid | PARTIAL | Helper actual usa `release()` y no espera readiness entre consultas. |
| SQL/Book QA fallback | PASS | La síntesis continúa con PostgreSQL canónico. |
| data mutation | ninguna | Sin insert/delete/index/flush/compact. |

## Synthesis QA impact

La primera corrida de `synthesis_qa_v1` no podía usar el índice V2 porque estaba `NotLoad`. Tras safe-load, el benchmark aislado comprobó search, pero el rerun batch reveló el adapter defectuoso: `book_qa_v2_hybrid_probe` llama `col.release()` al final y una siguiente iteración puede buscar antes de que la carga esté lista. No se presenta ese rerun como éxito vectorial; los siete resultados SQL/Book QA siguen siendo válidos.

## Causa raíz de problemas Milvus

1. **collection not loaded**: real, pero no implica caída del servicio; faltaba política de carga bajo demanda con espera de readiness.
2. **adapter V2 incompleto**: el índice de páginas V2 tiene 100 entidades y no guarda `run_id`, `document_id`, scope, idioma ni `collection_code`.
3. **lifecycle de helper**: liberar tras cada consulta y cargar de inmediato en la siguiente no es una política de batch robusta.
4. **no hay evidencia de alias incorrecto**: productivo V1 tiene el alias lógico/físico conocido; V2 es un contrato separado.

## Decisión técnica

Milvus debe permanecer como vector store principal porque está disponible, realiza búsqueda V2 al cargarse y ofrece una ventaja de latencia aproximada de 4,1× en este benchmark. La condición es implementar fixes concretos antes de depender de él para síntesis V2:

- adapter V2 con metadata `run_id`, `document_id`, scope lógico, idioma y página;
- `ensure_loaded(collection, timeout)` que espere `Loaded` y nunca oculte `NotLoad`;
- no `release()` por consulta en batch; lifecycle administrado por proceso o request;
- healthcheck que reporte servicio, colección, readiness, schema y search-ready;
- fallback explícito a SQL/FTS mientras Milvus no está ready.

No se recomienda `PGVECTOR_MIGRATION_RECOMMENDED`: pgvector no está instalado ni medido. Tampoco se puede declarar `MILVUS_PRIMARY_WITH_PGVECTOR_FALLBACK` porque el fallback no existe.

## Próximo gate

Crear un ADR para el contrato metadata V2 y el lifecycle de carga. Luego implementar `VectorSearchBackend` inicialmente con `milvus` y `disabled/sql_fallback`; evaluar pgvector en un lab separado sólo después de aprobación para instalar extensión y crear datos comparables.
