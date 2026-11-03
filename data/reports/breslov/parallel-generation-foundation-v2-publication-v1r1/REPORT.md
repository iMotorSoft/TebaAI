# Foundation V2 — Publication V1R1: FAIL temprano, antes del freeze

Resultado: `TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R1_FAIL`.

**No es una certificación congelada fallida ni una revalidación completa.** La ejecución se detuvo durante el preflight al reproducir un defecto real del producto. No hubo freeze, staging, commit ni push. Los gates posteriores son NOT_RUN; no se sustituyen por evidencia histórica.

## Base e historia

Rama: `feature/console-backend-core`.
`LOCAL_HEAD == TRACKING_HEAD == LS_REMOTE_HEAD == 9882b569e55513dc179eccdc1c465bf31b25cb6a` después de fetch.
Los 494 hashes del manifiesto certificado de Rollback Remediation V2 coinciden con el worktree actual. Esto verifica el prerrequisito, no certifica Foundation de nuevo.

- Publication V1: FAIL histórico, preservado.
- Rollback Remediation V1: INVALID histórico, preservado.
- Rollback Remediation V2: PASS histórico, preservado.
- Publication V1R1: FAIL temprano por integración de registro de generaciones.

## Defecto reproducido

`SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py`:

1. `persist_document_and_pages` inserta el documento con `logical_document_id=NULL`.
2. Llama `_register_generation` antes de insertar `library_ingestion_runs_v2`.
3. `_register_generation` inserta la generación con `run_id` todavía inexistente: PostgreSQL rechaza con SQLSTATE **23503**, constraint `library_document_generations_run_id_fkey`.
4. Aun preparando el run en el harness, se rechaza la inserción por `library_document_generations_document_logical_fkey`: el UPDATE que vincula documento e identidad lógica ocurre después del INSERT de generación.
5. El control con ambos prerrequisitos preparados previamente sí pasa con el mismo helper real y las mismas constraints.

Evidencia: `gateway-registration-results.json`; reproducción: `reproduce_gateway_registration.py` desde backend con `PYTHONPATH=. uv run python ../../data/reports/breslov/parallel-generation-foundation-v2-publication-v1r1/reproduce_gateway_registration.py`.

Los tres casos ejecutaron exclusivamente metadata sintética en transacciones revertidas. Se reutilizaron referencias tenant/job existentes sin modificarlas; la colección y los documentos eran sintéticos. C no fue ingresado, extraído, activado ni reconstruido. No se escribieron vectores. Documentos sintéticos residuales: **0**.

## Servicios y C

PostgreSQL disponible en base `tebaai`, tabla de generaciones y constraints presentes. Milvus disponible usando el cliente canónico. Un primer probe directo con `MILVUS_URI` vacío no era válido y se descartó; no se clasificó el servicio como caído.

C: documento `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`, lógico `db200a31-b547-5668-d968-06d0ec36ad95`.
Antes/después: **942 chunks / 942 vectores**. Snapshots de documento, lógico, generaciones, pointer, digests actuales de texto/páginas y metadata vectorial idénticos. Fuente durable presente y SHA aprobado `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.
No se certificó retrieval/viewer/citation/auth-source: NOT_RUN por parada temprana.

## Tests y límites

Suites focalizadas existentes: **24 PASS, 0 FAIL, 13 ERROR**. Los 13 errores son de construcción del fixture Foundation (`IndeterminateDatatype`, parámetro de `jsonb_build_object`); node IDs completos en `backend-results.json` y `focused-tests.txt`. No se ocultan ni se declaran PASS. No se corrigieron fixtures ni producto.

Backend completo pre-freeze/frozen: **NOT_RUN**. No se reprodujo el baseline histórico 1981/20/13, ni se afirma ausencia de nuevos fallos. Pruebas de migración forward/idempotencia, ciclo completo de readers, región, cleanup y árbol fresco: **NOT_RUN**.

Inventario independiente: 15 roots provisionales encontrados por referencias de schema/runtime/tests y soporte durable. 963 paths de trabajo preexistente clasificados como ajenos. La dependency closure transitiva completa no llegó a certificarse; no se afirma missing dependencies=0 ni se emite allowlist publicable.

## Integridad y alcance

Sólo se añadieron archivos bajo este directorio nuevo. Se comprobaron hashes de todos los archivos preexistentes del inventario y de los tres directorios históricos protegidos. No se modificó el fix de rollback, V5, region quarantine, readers, migraciones, expectativas ni código de producto.

No se generaron manifiestos frozen, allowlist ni reportes post-push/fresh-tree que pudieran aparentar fases ejecutadas. La lista de artefactos mínimos de una publicación completa no se completó porque esta corrida falló antes del freeze.

## Próximo paso

Autorizar una remediación separada del orden transaccional de registro y los fixtures, con regresión del gateway real. Después, abrir otra corrida de publicación identificada de forma nueva, reconstruir closure completa y revalidar desde cero. No reabrir Safety V2 ni reingestar C con este resultado.
