# Publication preflight remediation V1 — parada por defecto productivo

Resultado: `TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V1_FAIL`.
Motivo: `FAIL_PRODUCT_DEFECT_DISCOVERED`.

## Evidencia y regla de parada

La sección 7 del alcance exige detenerse ante un defecto real de producto y no corregirlo aquí. La inspección actual confirma dos órdenes inválidos en `SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py`:

1. `persist_document_and_pages`, línea 250: llama `_register_generation` antes del INSERT de `library_ingestion_runs_v2` (línea 258). El INSERT de generación lleva un run_id no nulo cuyo padre aún no existe: `library_document_generations_run_id_fkey`.
2. `_register_generation`, línea 342: inserta la generación antes del UPDATE que vincula el documento con el lógico (línea 355). El documento recién insertado no lleva logical_document_id: `library_document_generations_document_logical_fkey`.

Migration 043 declara ambas FK sin diferimiento. Los resultados históricos de `parallel-generation-foundation-v2-publication-v1r1/gateway-registration-results.json` corroboran ambos rechazos; no se modificaron ni se reinterpretaron como PASS. El catálogo vivo no se volvió a consultar y no se ejecutó otra reproducción en DEV.

Esto es independiente de los 13 ERROR de fixtures: el REPORT histórico atribuye esos ERROR a `IndeterminateDatatype` en `jsonb_build_object`, no a las dos FK. Por tanto no hay fundamento para afirmar que arreglar sólo el fixture resuelva los dos errores de registro del gateway.

## Estado de ejecución

Rama: `feature/console-backend-core`. Fetch y comparación de HEAD local, tracking y ls-remote: coinciden en `9882b569e55513dc179eccdc1c465bf31b25cb6a`.

No se modificaron producto, fixtures, tests ni evidencia histórica. Sólo se añadió este directorio. El worktree preexistente se preservó.

Por parada temprana: grafo de catálogo vivo, inventario clasificado completo, remediación de fixtures, UUID certification, ciclos sintéticos, limpieza, comparación de C, medición de fuente durable, detector de contradicciones, freeze y suites: **NOT_RUN**. Conteos de errores restantes: **no medidos**, no cero. No se emiten manifiestos ni artefactos que aparenten certificación ejecutada.

Fuente durable: **NOT_RUN**. No se adopta como verdad ni el booleano histórico ni su resumen humano. La contradicción histórica queda pendiente de medición independiente.

C: escrituras PostgreSQL/Milvus de esta ejecución = 0; reingesta, extracción, embeddings, reconstrucción vectorial y cambio de pointer = NO. No se afirma una comparación de snapshots que no se ejecutó.

PUBLICATION_PREFLIGHT_READY = NO
READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2 = NO
FOUNDATION_V2_PUBLISHED = NO
READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2 = NO
READY_FOR_C_REINGEST_EXECUTION = NO
C_REINGEST_EXECUTED = NO
COMMIT = NO
PUSH = NO

## Próximo paso

Autorizar por separado la corrección productiva del orden transaccional del gateway y su regresión. Este gate no la implementa. La certificación del harness y la medición de fuente durable siguen pendientes.
