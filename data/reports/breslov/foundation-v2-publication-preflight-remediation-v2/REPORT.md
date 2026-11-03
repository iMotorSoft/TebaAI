# Foundation V2 publication preflight remediation V2

Resultado: `FAIL`
Motivo: `FAIL_SOURCE_DURABILITY_DEFECT`.

## Causa raíz de los 13 ERROR

Los 13 ERROR históricos compartían un único defecto de fixture: el INSERT de
`library_pages_v2` en `_create_synthetic` construía `layout_notes` con
`jsonb_build_object('page_status','FULL','marker', %s)` sin tipo. PostgreSQL 18
no puede inferir el tipo de un parámetro dentro del variádico `any` de
`jsonb_build_object` y rechaza la sentencia en prepare con
`IndeterminateDatatype: could not determine data type of parameter $6`.

Reproducción: `indeterminate-datatype-reproduction.json` (probe aislado en
transacción revertida). Contrato de tipos:
`publication-fixture-sql-type-contract.json` (6 binds, 1 cast explícito `::text`).
Auditoría JSONB: `jsonb-expression-audit.json` (1 FIX_REQUIRED, 6 SAFE_TYPED).
Corrección: `%s::text` en el marcador; ningún otro cast y ningún cambio de
producto (`page_first_gateway.py`, `generation.py`, migración 043 intactos).

## Segundo y tercer defectos de fixture (descubiertos al ejecutar el fix)

Con los 13 ERROR resueltos, el fixture pudo correr completo y expuso dos
problemas de harness, no de producto:

1. `_destroy_synthetic` eliminaba `library_logical_documents` antes de
   `library_documents`; el FK inmediato `library_documents_logical_document_id_fkey`
   abortaba el cleanup, dejaba el fixture vivo y rompía todos los fixtures
   siguientes con `uq_knowledge_scopes_project_code`.
2. El fixture insertaba el pointer ACTIVE inicial sin la fila de auditoría
   `BACKFILL` que sí escribe la migración 043. Un ROLLBACK posterior era
   rechazado con "Rollback requires successful prior activation and switch
   history" aunque el estado era correcto.

También se corrigió la construcción de dos escenarios, preservando la misma
verdad: el control cross-document apuntaba a un logical inexistente (no
ejercitaba el FK compuesto) y el pointer roto usaba un UUID inexistente que el
propio FK rechaza antes de llegar al reader. Ahora se ejercita un generation de
otro logical y un pointer hacia un CANDIDATE con otro generation ACTIVE.

## Resultado de la remediación

- Archivo completo del fixture antes: 2 PASS / 0 FAIL / 13 ERROR (los 13 ERROR
  son exactamente los nodos objetivo). Después: 15 PASS / 0 FAIL / 0 ERROR;
  los 13 nodos objetivo quedan 13 PASS / 0 FAIL / 0 ERROR.
- Pre-freeze run 1 y run 2: fixture/FK/binding/IndeterminateDatatype/setup/cleanup = 0.
- CUTOVER y ROLLBACK aplicados; 8 controles negativos rechazados; cleanup verificado en cero.
- Gateway: 4 PASS, 0 FAIL, 0 ERROR.
- Focused preflight: 63 PASS / 0 FAIL / 0 ERROR.
- Foundation regression: 75 PASS / 0 FAIL / 0 ERROR, sin nodos nuevos.
- Full backend: 1998 PASS / 20 FAIL / 0 ERROR.
  Los 13 ERROR históricos desaparecen; no hay FAIL/ERROR nuevos.
- C: 0 escrituras PostgreSQL y 0 escrituras Milvus; digests antes/después idénticos.

## Fuente durable

El PDF externo aprobado coincide exactamente: SHA256
`440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`, 4550267 bytes,
284 páginas.

La fuente durable del producto **no existe**: `source_path` de C es
`None`, el archivo `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/SrvRestAstroLS_v1/backend/sources/ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa/original.pdf`
no está, y el endpoint autenticado devuelve
`404`. El acceso no autenticado sí
está bloqueado (`401`).

La contradicción V1R1 queda reconciliada en un solo sentido: el JSON histórico
(`durable_source_approved_sha=false`, snapshots con `durable_source_exists=false`)
era correcto; la frase "Fuente durable presente" del REPORT.md histórico era
incorrecta. No se reparó la fuente en este gate, según el alcance.

## Límites

No se publicó Foundation V2, no se hizo commit ni push, no se reingirió C, no se
tocó Milvus ni se modificó producto. La remediación del harness queda congelada
(`frozen-manifest.json`, `frozen-hashes.txt`) y verificada byte a byte después de
la certificación.

---

GATE = TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V2
RESULT = FAIL
PUBLICATION_PREFLIGHT_READY = NO
READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2 = NO
FOUNDATION_V2_PUBLISHED = NO
INDETERMINATE_DATATYPE_REMEDIATED = YES
TARGETED_V1R1_ERROR_NODES_REMAINING = 0
PUBLICATION_FIXTURE_ERRORS = 0
PAGE_FIRST_GATEWAY_FIX_PRESERVED = YES
ROLLBACK_FIX_PRESERVED = YES
APPROVED_EXTERNAL_SHA_MATCH = YES
DURABLE_SOURCE_PRESENT = NO
DURABLE_SOURCE_RESOLVABLE = NO
DURABLE_BYTES_MATCH_APPROVED = NO
AUTHENTICATED_ACCESS = FAIL
UNAUTHENTICATED_BLOCKED = YES
CURRENT_C_PRESERVED = YES
REPORT_CONTRADICTIONS = 0
INVALID_JSON_FILES = 0
POST_FREEZE_MODIFICATIONS = 0
COMMIT = NO
PUSH = NO
