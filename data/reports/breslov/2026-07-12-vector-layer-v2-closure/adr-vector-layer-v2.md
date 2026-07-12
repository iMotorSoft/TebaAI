# ADR — Vector Layer V2

## Estado

Accepted — 2026-07-12.

## Contexto

TebaAI/Breslov usa PostgreSQL como fuente de texto y metadata. La recuperación semántica necesitaba soportar explícitamente `knowledge_scope_code`, `collection_code`, `run_id`, `document_id` y `language` para Ingesta V2. Milvus aportaba baja latencia, pero el estado `NotLoad` y la ausencia de un fallback uniforme impedían tratarlo como una capa operacional cerrada.

## Decisión

Adoptar **DUAL_BACKEND_AUTO** para desarrollo:

1. Milvus V2 es la ruta preferida cuando está disponible.
2. Si la colección existe pero está `NotLoad`, el adapter ejecuta `ensure_loaded(timeout_seconds=10, poll_interval_seconds=.25)`.
3. Si Milvus falla o vence el timeout, `auto` intenta pgvector V2.
4. Si ambos fallan, el adapter devuelve diagnóstico explícito y el consumidor continúa con FTS/SQL; no fabrica evidencia vectorial.
5. Las respuestas investigativas solo citan texto y páginas verificados en PostgreSQL.

## Opciones consideradas

| Opción | Resultado |
|---|---|
| Milvus only | Rechazada: no cubre el riesgo operativo de colección no cargada. |
| pgvector only | Rechazada: funciona, pero Milvus es ~2.8x más rápido en esta medición. |
| Milvus primary + pgvector fallback | Válida conceptualmente; implementada bajo el nombre operativo `DUAL_BACKEND_AUTO`. |
| pgvector primary + Milvus optional | Rechazada por benchmark. |
| dual backend auto | Aceptada. |

## Configuración operativa

El factory expone `milvus`, `pgvector`, `auto` y `disabled`. El caller selecciona el modo y registra `vector_backend_requested`, `vector_backend_used` y el motivo de fallback. Las colecciones/tables V2 dev son `tebaai_breslov_chunks_v2_dev` y `library_vector_embeddings_v2_dev`.

## Lifecycle/load policy

La colección Milvus no se libera tras búsquedas normales ni en batches. `ensure_loaded` consulta load state, solicita carga solo cuando corresponde, espera con polling y devuelve los estados antes/después, elapsed time, timeout y error. Cargar no muta entidades ni índices.

## Fallback policy

El fallback es de disponibilidad, no de autoridad: Milvus → pgvector → FTS/SQL del caller. PostgreSQL mantiene la validación de texto/página. Un resultado semántico no se transforma en cita sin esa verificación.

## Consecuencias

Se agregan dos stores derivados que deben backfillearse idempotentemente desde PostgreSQL. La capa gana continuidad operativa y conserva el mejor rendimiento de Milvus. Queda una deuda futura de migrar la API ORM de PyMilvus antes de 3.1.

## Rollback

Seleccionar `disabled` para desactivar retrieval vectorial sin tocar corpus, tabla ni colección; el pipeline conserva SQL/FTS. También se puede seleccionar individualmente `milvus` o `pgvector` para aislar una incidencia.

## Validaciones

Corpus real Kitzur V2: 506 páginas no vacías en ambos stores; filtros V2 completos PASS; batch Nivel 3: 7/7 PASS; benchmark comparable y tests focalizados documentados en `README.md` y `benchmark_comparable.json`.
