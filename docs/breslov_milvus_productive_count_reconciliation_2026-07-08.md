# Breslov Milvus Productive Count Reconciliation

**Date:** 2026-07-08
**Rama:** `feature/console-backend-core`
**HEAD:** `1547bf0`

> **Resolución:** el `DRIFT_REAL` fue reparado y el baseline productivo quedó restaurado en 5102 chunks únicos. El cierre canónico está en `docs/breslov_milvus_productive_baseline_restoration_2026-07-08.md`; los conteos `3274/5102` de este informe describen el estado observado durante la reconciliación.

## 1. Resumen ejecutivo

**3274 NO contradice el baseline 5102. El baseline sigue vigente.**

3274 es el conteo real actual de entidades físicas en Milvus productivo `tebaai_breslov_chunks_v1`. La diferencia 5102 − 3274 = 1828 corresponde a entidades canónicas de 3 documentos que fueron eliminadas por la limpieza FASE D del cleanup del 2026-07-05 (delete de entidades con `source_type=''`), que afectó a documentos cuyo pipeline original no pobló `source_type`.

Tras compactación automática de Milvus, el conteo refleja la realidad física: **PG tiene 5102 embeddings ready; Milvus tiene 3274 entidades activas.**

## 2. Diagnóstico final

**DRIFT_REAL** — pero causado por la propia limpieza documentada, no por un error externo o posterior.

## 3. Rama y HEAD

| Campo                | Valor                                    |
| -------------------- | ---------------------------------------- |
| Rama                 | `feature/console-backend-core`           |
| HEAD inicial         | `1547bf0` (sin cambios)                  |
| HEAD final           | `1547bf0` (sin cambios nuevos)           |
| Working tree inicial | Sin cambios en archivos de código        |
| Working tree final   | Solo nuevos docs de reporte              |

## 4. Conteos PG (baseline)

| Documento | document_id | Status | PG chunks | PG embeddings |
|---|---|---|---|---|
| Cruzando el Puente Angosto | 0bad063c | ready | 741 | 741 |
| El Alma del Rebe Najmán | 987bd9d3 | ready | 498 | 498 |
| El Jardín de las Almas | 76f2adbc | ready | 147 | 147 |
| KITZUR | 27f175ea | ready | 817 | 817 |
| Kokhavey Ohr | c7c10741 | ready | 852 | 852 |
| La Potencia de la Plegaria | 43ba4f4b | ready | 646 | 646 |
| Likutey Halajot LM II 8 | 56ddcc3b | ready | 1205 | 1205 |
| Un Día en la Vida de un Jasid | a852721d | ready | 196 | 196 |
| **Total ready** | | | **5102** | **5102** |
| Likutey Halajot Interior (test) | 47768aac | test_candidate | 2652 | 2222 |
| Otros test_candidate (9 docs) | | test_candidate | 590 | 0 |

## 5. Conteos Milvus

| Colección | Conteo total | Método | Observación |
|---|---|---|---|
| `tebaai_breslov_chunks_v1` | **3274** | `num_entities` | Real, post-compactación |
| `tebaai_breslov_chunks_v1` | 3274 | query(pk!='') | Confirmado |
| `tebaai_breslov_chunks_v1` | 3274 | source_type='book' | Todos los activos |
| `tebaai_breslov_chunks_v1` | 0 | source_type='' | Todos eliminados |
| `tebaai_breslov_test_chunks_v1` | **10115** | `num_entities` | Test intacto |

## 6. PG vs Milvus productivo por documento

| Documento | document_id | PG embeddings | Milvus prod | Diferencia | Causa |
|---|---|---|---|---|---|
| Kokhavey Ohr | c7c10741 | 852 | 852 | 0 | source_type='book' → sobrevivió |
| KITZUR | 27f175ea | 817 | 817 | 0 | source_type='book' → sobrevivió |
| Cruzando el Puente | 0bad063c | 741 | 741 | 0 | source_type='book' → sobrevivió |
| El Alma del Rebe Najmán | 987bd9d3 | 498 | 498 | 0 | source_type='book' → sobrevivió |
| Un Día en la Vida | a852721d | 196 | 196 | 0 | source_type='book' → sobrevivió |
| Likutey Halajot LM II 8 | 56ddcc3b | 1205 | **166** | **−1039** | source_type='' → eliminado |
| La Potencia de la Plegaria | 43ba4f4b | 646 | **3** | **−643** | source_type='' → eliminado |
| El Jardín de las Almas | 76f2adbc | 147 | **1** | **−146** | source_type='' → eliminado |
| **Total** | | **5102** | **3274** | **−1828** | |

## 7. Origen del 3274

| Fuente | Filtro | Colección | Explicación |
|---|---|---|---|
| Lab script (preflight) | `num_entities` | `tebaai_breslov_chunks_v1` | Conteo total post-compactación |
| Pre-investigación | `num_entities` | `tebaai_breslov_chunks_v1` | Confirmado: 3274 |

El lab script NO aplicó filtro. `num_entities` devuelve el conteo real de entidades activas en Milvus. El número refleja la realidad tras la compactación automática que removió las entidades ghost.

## 8. Hipótesis evaluadas

| Hipótesis | Resultado | Evidencia |
|---|---|---|
| **conteo filtrado** | ❌ Descartada | `num_entities` es conteo total, sin filtro |
| **otra colección** | ❌ Descartada | Se usó `tebaai_breslov_chunks_v1` correctamente |
| **solo citables** | ❌ Descartada | Todos los ready chunks son `citable=True` en PG (5102/5102). Milvus no almacena citable como filtro explícito para estos chunks |
| **documentos excluidos** | ✅ **Confirmado** | 3 documentos perdieron entidades por `source_type=''` |
| **baseline cambió** | ❌ No | 5102 sigue siendo baseline PG oficial. No hay documento que lo reemplace |
| **drift real** | ✅ **Confirmado** | Milvus tiene 3274 activos vs 5102 esperados. Diferencia = 1828 entidades eliminadas en FASE D del cleanup |

## 9. Causa Raíz

La limpieza `FASE D — Delete 1828 stale entities (empty source_type)` del 2026-07-05 eliminó entidades con `source_type=''`. Los documentos Likutey Halajot, La Potencia de la Plegaria y El Jardín de las Almas fueron originalmente ingestados por un pipeline anterior que no poblaba el campo `source_type`, por lo que todas sus entidades en Milvus tenían `source_type=''`. Al eliminarlas —aunque la intención era limpiar entidades huérfanas— también se eliminaron las copias canónicas de estos 3 documentos.

Las entidades de los 5 documentos restantes (Kokhavey Ohr, KITZUR, Cruzando el Puente, El Alma del Rebe Najmán, Un Día en la Vida) fueron ingestadas por el pipeline más reciente que sí pobló `source_type='book'`, por lo que sobrevivieron.

Además, la re-embedding FASE C solo recuperó 70 chunks de Likutey (que están entre los 166 sobrevivientes). Los 3 de Potencia y 1 de Jardín sobrevivieron probablemente porque tenían `source_type` distinto de vacío por alguna razón (reescritura manual, batch específico).

La compactación automática de Milvus posterior al 2026-07-05 removió físicamente las entidades ghost (deleted pero contadas), exponiendo el verdadero conteo activo de 3274.

**La documentación post-cleanup del 2026-07-05 declaró "100% PG↔Milvus match" basándose en ANN search contra entidades aún no compactadas, que incluían las ghosts. La compactación reveló el desajuste.**

## 10. Impacto sobre Relation QA Lab

El lab del 2026-07-08 usó Milvus productivo como fuente vectorial y reportó correctamente el estado real. **El lab NO está invalidado** —sus hallazgos sobre sangre/habla son correctos, aunque la cobertura vectorial para los 3 documentos afectados es parcial.

## 11. Guardrails

- ✅ No productivo modificado (solo consultas read-only)
- ✅ No PG modificado
- ✅ No Milvus modificado
- ✅ No status cambiado
- ✅ No reingesta
- ✅ No embeddings nuevos
- ✅ No frontend
- ✅ No Team360
- ✅ Servicios no reiniciados
- ✅ Sin OpenAI directa

## 12. Archivos creados/modificados

- `docs/breslov_milvus_productive_count_reconciliation_2026-07-08.md` (nuevo — este informe)

## 13. Fase recomendada en ese corte (completada)

**Breslov Milvus Productive Repair Plan**

Dado que es DRIFT_REAL con causa conocida y documentada, se requiere:

1. Re-embed desde PG para Likutey Halajot LM II 8 (faltan 1039 embeddings, existen en PG)
2. Re-embed desde PG para La Potencia de la Plegaria (faltan 643 embeddings, existen en PG)
3. Re-embed desde PG para El Jardín de las Almas (faltan 146 embeddings, existen en PG)
4. Total a re-embed: **1828 vectores** vía LiteLLM + upsert directo a `tebaai_breslov_chunks_v1`
5. PG `milvus_primary_key` backfill tras upsert
6. Golden queries finales para confirmar match PG↔Milvus
7. Dry-run + rollback plan antes de aplicar

En ese corte, todo esto requería autorización explícita y quedaba fuera de la reconciliación read-only. La reparación y su cleanup posterior ya fueron completados; el cierre se documenta en `docs/breslov_milvus_productive_baseline_restoration_2026-07-08.md`.
