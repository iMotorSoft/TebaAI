# Breslov Milvus Productive Baseline Restoration — 2026-07-08

Este documento consolida el ciclo que detectó, explicó y corrigió el desvío del índice vectorial productivo Breslov, y fija el cierre operativo verificado del hito.

## Alcance y cierre

La restauración terminó con el baseline lógico productivo nuevamente alineado con PostgreSQL y sin contaminación del corpus experimental.

| Control de cierre | Resultado final |
|---|---:|
| Colección Milvus | `tebaai_breslov_chunks_v1` |
| Chunks únicos en PostgreSQL | 5102 |
| Chunks únicos en Milvus | 5102 |
| Match PG↔Milvus | 100% |
| Duplicados por `chunk_id` | 0 |
| Entidades stale con `source_type=''` | 0 |
| Likutey layout `test_candidate` en productivo | No |
| Relation QA posterior al cleanup | Válido |

PostgreSQL continuó siendo la fuente de verdad y Milvus el índice derivado. Este informe documenta operaciones ya ejecutadas con autorización durante el hito; su elaboración no produjo escrituras en PostgreSQL ni Milvus.

## Cronología consolidada

El ciclo completo separó diagnóstico, planificación, ejecución y validación antes de declarar restaurado el baseline.

| Fase | Estado | Resultado |
|---|---|---|
| Detección | Cerrada | Se observó `3274` en Milvus frente al baseline PG de `5102` |
| Reconciliación read-only | Cerrada | Se confirmó una diferencia exacta de 1828 chunks en tres documentos |
| Diagnóstico | Cerrada | `DRIFT_REAL`, con causa raíz conocida |
| Repair plan | Cerrada | Re-embedding selectivo desde texto canónico PG y upsert controlado |
| Dry-run y backup | Cerrada | 1828/1828 faltantes y SHA-256 validados; backups generados |
| Reparación productiva | Cerrada | 1828 embeddings restaurados mediante LiteLLM |
| Cleanup de duplicados | Cerrada | 1828 entidades redundantes eliminadas conservando la PK referenciada por PG |
| Validación final | Cerrada | 5102 únicos, 0 duplicados, 0 stale, match 100% |
| Relation QA | Cerrada | Reejecución válida con cobertura productiva restaurada |

## Detección y reconciliación read-only

El conteo `3274` era el número real de entidades activas después de la compactación automática de Milvus; no era un filtro del laboratorio ni un nuevo baseline.

| Documento afectado | Baseline PG | Milvus observado | Faltantes |
|---|---:|---:|---:|
| Likutey Halajot LM II 8 | 1205 | 166 | 1039 |
| La Potencia de la Plegaria | 646 | 3 | 643 |
| El Jardín de las Almas | 147 | 1 | 146 |
| **Subtotal afectado** | **1998** | **170** | **1828** |
| Otros cinco documentos ready | 3104 | 3104 | 0 |
| **Total productivo** | **5102** | **3274** | **1828** |

La reconciliación descartó cambio de colección, conteo filtrado, exclusión por citabilidad y modificación del baseline. Los ocho documentos `ready` y sus 5102 chunks seguían vigentes en PostgreSQL.

## Diagnóstico `DRIFT_REAL`

La causa raíz fue la limpieza del 2026-07-05 basada únicamente en `source_type=''`.

Tres documentos habían sido indexados por un pipeline anterior que no poblaba `source_type`. La eliminación pretendía retirar entidades stale, pero también borró 1828 entidades canónicas. Las entidades todavía visibles como ghosts llevaron a declarar prematuramente un match completo; la compactación posterior expuso la cobertura física real de `3274/5102`.

El criterio corregido quedó basado en identidad estable: la pertenencia canónica se determina por `chunk_id` y su correspondencia con PostgreSQL, no por la presencia aislada de metadata opcional.

## Repair plan, dry-run y backups

El plan limitó la reparación a los 1828 chunks ausentes y reutilizó el texto y metadata canónicos de PostgreSQL para regenerar únicamente los vectores perdidos.

El dry-run confirmó 1039 chunks de Likutey, 643 de Potencia y 146 de Jardín; validó SHA-256 para `1828/1828`, el payload con UUID nuevo, `source_type='book'` y `collection_code='breslov'`, sin ejecutar escrituras.

La evidencia previa a la mutación quedó registrada en estos artefactos:

- `backups/repair_pg_chunks.json`: snapshot de chunks y metadata requeridos por la reparación;
- `backups/repair_milvus_snapshot_before_repair.json`: snapshot del estado Milvus con 3274 entidades y cero `source_type=''`;
- `backups/cleanup_duplicates_pks.json`: manifiesto de las 1828 PK redundantes seleccionadas para cleanup.

## Reparación productiva controlada

Con autorización explícita, la reparación regeneró `1828/1828` embeddings a través de LiteLLM, insertó las entidades en `tebaai_breslov_chunks_v1` y actualizó en PostgreSQL las referencias `milvus_primary_key` correspondientes.

La operación no reingirió PDFs, no cambió chunks ni promovió documentos experimentales. Los cinco documentos no afectados conservaron sus 3104 entidades.

Una reejecución posterior del repair produjo dos entidades para cada uno de los 1828 `chunk_id` reparados. El problema fue duplicación de identidad lógica, no pérdida ni corrupción del texto canónico.

## Cleanup de duplicados

El cleanup resolvió cada par usando la referencia autoritativa existente en PostgreSQL.

Para cada `chunk_id` duplicado se conservó la PK igual a `library_chunk_embeddings.milvus_primary_key` y se eliminó la PK redundante. La selección fue validada primero en dry-run y aplicada en lotes limitados a los tres documentos afectados.

| Métrica | Antes del cleanup | Cierre |
|---|---:|---:|
| Entidades Milvus | 6930 | 5102 |
| Chunks únicos | 5102 | 5102 |
| Duplicados por `chunk_id` | 1828 | 0 |
| Entidades con `source_type=''` | 0 | 0 |
| Match PG↔Milvus | Lógico, con duplicados | 100% uno-a-uno |

## Baseline productivo restaurado

El baseline lógico final queda fijado en 5102 chunks únicos para los ocho documentos `ready` del scope Breslov productivo.

La colección no contiene entidades stale con `source_type=''`, cada `chunk_id` productivo resuelve a PostgreSQL y no existen duplicados lógicos. El documento layout-aware `Likutey Halajot Explicado — Interior Final` conserva estado `test_candidate` y permanece fuera de `tebaai_breslov_chunks_v1`.

## Impacto sobre Relation QA Lab

La ejecución inicial del Relation QA Lab con 3274 entidades no quedó invalidada: sus evidencias recuperadas resolvían a texto canónico PG, aunque la cobertura vectorial de tres documentos era parcial.

Después de la reparación y del cleanup, el laboratorio se reejecutó sobre el baseline restaurado y obtuvo 56 hits vectoriales, 187 fragmentos consolidados y 0 evidencias sin correspondencia PostgreSQL. La conclusión sangre/habla continúa válida y ya no lleva la limitación de cobertura `3274/5102`.

La separación de evidencia literal, coocurrencia, relación temática e inferencia de IA se mantiene obligatoria; una inferencia no debe presentarse como vínculo textual directo.

## Habilitación de `/library/relation-qa`

La restauración elimina el bloqueo de integridad vectorial para diseñar el futuro endpoint `POST /library/relation-qa`; el endpoint no fue implementado en este hito.

La siguiente fase puede apoyarse en un corpus productivo reconciliado y en un lab post-cleanup válido. Antes de exponerlo deberá definir contrato HTTP, autenticación y autorización por scope, límites de costo, timeout, caché, source map trazable y pruebas de regresión contra PostgreSQL y Milvus.

## Evidencia relacionada

Los documentos de fase conservan el detalle histórico; este informe posee el estado final consolidado.

- `milvus_productive_count_reconciliation.md` — detección, reconciliación y causa raíz;
- `milvus_productive_repair_plan.md` — estrategia, riesgos y validaciones del repair;
- `milvus_duplicate_cleanup_plan.md` — selección y eliminación de duplicados;
- `concept_relation_qa_blood_speech_lab.md` — laboratorio y resultado post-restauración;
- `SrvRestAstroLS_v1/docs/status_actual.md` — resumen del estado runtime vigente.

## Guardrails de esta consolidación

Esta fase fue exclusivamente documental.

- no se modificó código funcional;
- no se consultó ni modificó PostgreSQL;
- no se consultó ni modificó Milvus;
- no se ejecutaron scripts de reparación, cleanup o QA;
- no se inició, detuvo ni reinició ningún servicio.
