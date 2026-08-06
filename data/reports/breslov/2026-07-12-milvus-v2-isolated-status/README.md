# Milvus V2 Isolated Status Probe

## Resumen ejecutivo

Estado principal: **MILVUS_COLLECTION_NOT_LOADED** para el índice V2 de páginas Kitzur.

Milvus está operativo: acepta conexión, lista colecciones, entrega schema/índices/conteos y permite consultas de metadata read-only en las colecciones cargadas. El mensaje previo `collection not loaded` es real y corresponde a `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1`, no a una colección inexistente ni a un alias de la colección productiva.

No se ejecutó `load_collection`, búsqueda vectorial ni modificación alguna. Por lo tanto la siguiente acción, si se desea probar búsqueda V2, es **OPTIONAL_SAFE_LOAD_PROBE_REQUIRED** bajo autorización explícita.

## Infraestructura

| Componente | Estado | Observación |
|---|---|---|
| Milvus connection | PASS | `127.0.0.1:19530`, metadata read-only disponible. |
| PostgreSQL read-only | PASS | Run Kitzur V2 encontrado y completado. |
| LiteLLM | No requerido | Este probe no generó vector ni llamó al gateway. |

## Colecciones detectadas

| Collection | Exists | Load state | Entities | Index | Vector field | Dim |
|---|---:|---|---:|---|---|---:|
| `tebaai_breslov_chunks_v1` | sí | Loaded | 5.102 | HNSW / COSINE | embedding | 1536 |
| `tebaai_breslov_test_chunks_v1` | sí | Loaded | 10.115 | HNSW / COSINE | embedding | 1536 |
| `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1` | sí | **NotLoad** | 100 | HNSW / COSINE | embedding | 1536 |

Las dos colecciones V1 cargadas respondieron `query` de metadata con `pk`, `chunk_id`, `document_id`, `collection_code`, `language`, título y páginas. La búsqueda vectorial se omitió deliberadamente: el probe no fabrica embeddings ni altera el estado de load. La colección V2 no recibió query porque está `NotLoad`.

## Colección esperada por código/config

| Fuente | Collection |
|---|---|
| `core/config.py` / runtime productivo | `tebaai_breslov_chunks_v1` |
| `hybrid_search.py` / Relation QA | colección productiva, con alias lógico `breslov_primary` → metadata `collection_code=breslov` |
| Book QA V2 hybrid probe / synthesis prototype | `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1` |

No hay una única “colección V2” configurada en el núcleo: la de Kitzur es un índice experimental de páginas, distinto del contrato V1 de chunks.

## PostgreSQL esperado

| Documento | document_id | scope | run_id | páginas | embedding_model |
|---|---|---|---|---:|---|
| Kitzur Likutey Moharán V2 | `dffa06db-0740-401e-92a8-aa9ccd6b68dd` | `breslov_test` | `492acd8d-06bd-42ac-a511-f3ec52f97bb3` | 512 | `openai_text_embedding_3_small` (configurado) |

El run usa `ingestion_v2_kitzur_createspace_001`, está `completed` y tiene 19 menciones de concepto. `knowledge_scopes` no contiene `breslov_test`: confirma que el scope de run V2 no es el mismo contrato de autorización `knowledge_scope_code` V1.

## Milvus observado

| Collection | metadata scope | run_id | entities | sample ok | search ok |
|---|---|---:|---:|---:|---:|
| productiva V1 | `collection_code=breslov` en muestra | no existe en schema | 5.102 | sí | omitida sin vector de consulta |
| test V1 | campo `collection_code` disponible | no existe en schema | 10.115 | sí | omitida sin vector de consulta |
| páginas Kitzur V2 | no soportado por schema | no soportado por schema | 100 | omitida: NotLoad | omitida: NotLoad |

El schema V2 es exactamente `pk`, `page_number`, `text_preview`, `embedding`. Por diseño no puede filtrar por `run_id`, `document_id`, `collection_code`, `knowledge_scope_code` ni idioma. Esto es un **RUN_ID_NOT_SUPPORTED** en el índice V2 actual, además de su estado NotLoad.

## Diagnóstico

1. **Milvus está operativo**: conexión, enumeración, schema, índice, conteos y query metadata V1 funcionan.
2. **El nombre V2 es correcto**: `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1` existe. No hay `MILVUS_COLLECTION_NAME_MISMATCH`.
3. **`collection not loaded` es real**: el load state observado es `NotLoad`; explica exactamente el error de `search` previo.
4. **No es alias `breslov_primary`**: esa relación es V1 lógico→físico y metadata `breslov`; el Kitzur está en el run scope `breslov_test`, que no existe en `knowledge_scopes`.
5. **Hay mismatch de cobertura V2**: PostgreSQL tiene 512 páginas para el run, mientras el índice V2 tiene 100 entidades. No se puede declarar round-trip completo; estado `PG_MILVUS_COUNT_MISMATCH` para el índice de páginas.
6. **Hay un adapter gap**: `synthesis_qa_v1` no puede filtrar el índice V2 por run ni document y no debe mezclarlo con V1; estado secundario `SYNTHESIS_ADAPTER_GAP`.

## Recomendación

No reindexar. La siguiente fase debe ser explícita y separada:

1. autorizar un **safe load probe** de la colección V2 existente;
2. si pasa, ejecutar una sola búsqueda con vector vía LiteLLM y rehidratar la página desde PostgreSQL;
3. decidir un contrato V2 de metadata (`run_id`, `document_id`, scope lógico) antes de usar ese índice en síntesis;
4. sólo después medir si faltan 412 entidades por diseño de subset o por una discrepancia de indexación.

## Evidencia reproducible

- [`status.json`](status.json): estado agregado y muestras metadata.
- [`collections.json`](collections.json): conteos y load state por colección.
- [`schema.json`](schema.json): fields e índices.
- [`postgres_expected.json`](postgres_expected.json): expectativa V2 read-only.
- [`probe_errors.log`](probe_errors.log): vacío; no hubo fallo de conexión.
