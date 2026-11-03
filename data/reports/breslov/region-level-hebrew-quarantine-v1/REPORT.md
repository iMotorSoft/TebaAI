# Region-level Hebrew Quarantine V1 — implementación parcial

## Resultado

**TEBAAI_BRESLOV_REGION_LEVEL_HEBREW_QUARANTINE_V1_BLOCKED**

No se emite PASS ni se afirma enforcement en runtime. No se ejecutó el E2E real del worker. El trabajo quedó incompleto: consumidor offline implementado y probado; integración worker/gateway, retención durable de fuente y validación real pendientes. No es un bloqueo por necesidad de perfección hebrea, nuevo holdout, investigación de lineage o servicios caídos.

## Estado inicial / protección del worktree

- Rama: `feature/console-backend-core`.
- HEAD local, tracking remoto y ls-remote inicial: `704ae24597e916b56ddec8a71fd0a30d34793aab`.
- Inventario anterior a implementación: `worktree-before.json`.
- Se preservaron cambios locales preexistentes V5/evaluator/UI/reportes.
- Sin reset/stash/clean, staging, commit, push, cambio de rama, migraciones, reinicios, reingesta de C ni producción.

## Cambios de este intento

1. `SrvRestAstroLS_v1/backend/modules/library/region_publication.py` (nuevo): consumidor de certificados regionales existentes. Sólo ACCEPTED + CERTIFIED, ligado a ownership exacto, produce texto publicable. Metadata sin extracción rechazada; bbox, fuente, página, region_id, razón y estado original preservados. FULL/PARTIAL/UNUSABLE y aviso textual. No realiza OCR, reparación, normalización hebrea, traducción ni síntesis.
2. `SrvRestAstroLS_v1/backend/tests/test_region_publication.py` (nuevo): 21 tests deterministas.
3. Este directorio: inventario, arquitectura, probes reproducibles offline, snapshots read-only y resultados crudos de tests.

No se modificó el pipeline ni se activó una implementación parcial en el worker.

## Qué se demostró, y qué no

| Propiedad | Resultado | Alcance |
|---|---|---|
| 5 casos controlados | PASS | Consumidor puro, estados declarados en fixture |
| Exclusión antes de concatenación | PASS | canonical_markdown del consumidor |
| BAD → 0 chunks | PASS | paragraph_chunks invocado por evidence_unit, sin persistencia |
| GOOD_A / BAD / GOOD_B | PASS | Dos inputs de evidencia separados, PARTIAL |
| Vecinos ACCEPTED perdidos | 0 | Fixtures y certificados actuales del probe offline |
| No perder texto bueno aún no certificado | NO DEMOSTRADO | No se redefine buena extracción como certificado positivo |
| Bbox/fuente/razón de cuarentena | PASS | Metadata del consumidor, no API runtime |
| Acceso visual durable tras worker | NO DEMOSTRADO | Source-reference no sustituye almacenamiento |
| Embeddings/vectores/retrieval/citas reales | NOT_RUN | Ningún documento E2E creado |
| Idempotencia de ingesta | NOT_RUN | Sólo determinismo del consumidor probado |
| Worker/gateway seguros por región | NO IMPLEMENTADO | Siguen usando página completa |

No extrapolar los ceros offline a Milvus, embeddings, retrieval o citas de la aplicación.

## Fuente real

C: `LIKUTEY HALAJOT (Interior Final).pdf`, SHA-256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.

Probe actual V5 en páginas físicas 55/167/168. Se preservan exactamente las unidades ACCEPTED + CERTIFIED; todas las demás quedan fuera del output del consumidor. Las tres páginas resultan PARTIAL, sin chunks derivados de unidades quarantined en el probe. Esto NO demuestra que todas las regiones visualmente correctas hayan sido aceptadas por V5.

Renderizado y revisión visual de p55/p167: panel hebreo legible sobre cuerpo y notas españoles; capturas `source-page-55.png` y `source-page-167.png`. No se transcribió ni se reparó texto. El PDF original sigue disponible en su ubicación externa durante el probe; eso no prueba retención de un upload procesado. p187/p416 no fueron revalidadas; no se las presupone corruptas.

## Pipeline real: riesgos aún abiertos

`pipeline-before.md` detalla el flujo. Hoy el worker no consulta calidad; `persist_chunks` chunkea páginas enteras. `finalize` borra el temporal sin que este camino haya guardado `source_path` documental. Persistir únicamente metadatos de bbox/hash no resuelve la segunda falla.

`architecture-decision.md` describe el handoff pendiente: una representación forward compartida, unidades separadas hasta chunking, metadata persistida y fuente durable tenant-scoped con cleanup. No aplicar certificados sobre una cadena distinta por reverse text matching. No filtrar tarde, tras embedding. No introducir rechazo global de páginas/documentos parciales.

## Validaciones

- Focalizadas: **267 PASS**, 0 fallos (`focused-tests.txt`). Incluyen calidad, provenance, V1–V5, consumer, worker/orchestration, cleanup, Milvus contract y publicación.
- Suite completa: **1911 PASS, 20 FAIL**, 94 warnings (`tests-backend-full.txt`).
- Baseline del mismo worktree excluyendo únicamente los tests nuevos: **1890 PASS, 20 FAIL**, 94 warnings (`tests-backend-baseline.txt`). Mismos IDs fallidos: **0 fallos nuevos**. No se usó el número histórico 18 como baseline actual. Dos fallos corresponden a tests del evaluator V5 local preexistente; no se editaron.
- `git diff --check`: PASS. Nuevos archivos de código revisados por separado, al no estar staged.
- Preflight TCP local: PostgreSQL/Milvus/LiteLLM alcanzables; alias/dimensión/key presente obtenidos de globalVar. No hubo llamada real de embedding; preflight no equivale a validación de proveedor/fallback.

## Stores DEV

Snapshots antes/después del probe offline y después de no-op cleanup idénticos:

- 3 documentos, 3 textos, 896 páginas;
- 2146 chunks y 2146 embeddings;
- Milvus primary 2146 identidades vivas, E2E 0;
- hashes de filas PG y de identidades Milvus sin cambios.

Los snapshots se tomaron después de las suites, antes del probe offline; no son un snapshot anterior a todo el trabajo ni un E2E de ingestión. El hash Milvus cubre IDs/chunk/documento, no los valores float del vector. No se hizo upsert/delete ni se creó test data en los stores por este probe. No hubo artifacts E2E que eliminar.

## Métricas del gate real

Todas las métricas live exigidas quedan **NO VERIFICADAS** (`null` en `gate.json`), no cero ni YES/NO inventados. Los resultados offline se registran aparte en `region-publication-results.json` y `chunk-results.json`.

`REGION_LEVEL_QUARANTINE_READY=NO`.
`FULL_C_REINGEST_READY=NO`.
`COMMIT=NO`, `PUSH=NO` por estado BLOCKED.

## Próximo paso

Completar la integración y el E2E de **este mismo gate** según `architecture-decision.md`. No ejecutar todavía `TEBAAI_BRESLOV_C_CONTROLLED_REINGEST_V1`.
