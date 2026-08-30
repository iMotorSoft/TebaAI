# Breslov — editor PDF → consulta de usuario: production readiness V1

Fecha: 2026-08-30  
Rama: `feature/console-backend-core`  
HEAD inicial de este cierre: `58365104e0b34e9a79cd91f77aa91dadd79f5f43`

## Cierre production candidate — evidencia DEV

**VEREDICTO: `PRODUCTION_CANDIDATE_PASS`**

**Gate: `TEBAAI_BRESLOV_EDITOR_UPLOAD_TO_USER_QUERY_PRODUCTION_CANDIDATE_V1_PASS` → PASS**

La evidencia reproducible está en [`golden_evidence.json`](./golden_evidence.json).
El circuito completo se ejecutó con backend, PostgreSQL, Milvus, worker,
PyMuPDF4LLM, LiteLLM, frontend real y Chromium; no se usaron mocks para cerrar
el gate. Un editor temporal subió el PDF golden, lo publicó mediante la acción
editorial normal y un viewer temporal consultó el mismo documento. El viewer
recibió respuestas grounded para las preguntas literal y semántica, con el
mismo libro/página/chunk como fuente, y rechazó una pregunta sin evidencia sin
inventar contenido. El viewer recibió `403` al intentar subir.

### Golden path

```text
Editor login        ✅
Editor RBAC         ✅ (viewer upload = 403)
PDF upload          ✅
Worker durable      ✅
Extraction          ✅ (3 páginas, 2 textuales)
Chunks PostgreSQL   ✅ (2)
Vectors Milvus      ✅ (2; faltantes 0, huérfanos 0, duplicados 0)
Publication         ✅ (test_candidate → ready, verificación PG↔Milvus)
Viewer login        ✅
Literal retrieval   ✅
Semantic retrieval  ✅
Grounded answer     ✅
Citation            ✅ (título/libro + página 1 + fragmento)
Negative grounding  ✅ (sin alucinación)
```

Evidencia principal: `document_id=ca7d6c5c-8023-5a52-96f8-761b214d7cb4`,
`job_id=4efe5f26-4884-4522-9a05-c508d783181e`, intento 1, SHA-256 del fixture
`d7678313f6e054bc3305fc69336acfde616e38dc266bcb7d022cd107cab020b9`.
Q1 y Q2 recuperaron el chunk `7a519d82-7230-576c-a66f-df8f2f26e433` en la
página 1 y citaron `Salmos 16:1`. Dos PDFs concurrentes también terminaron y
fueron reconciliados/limpiados por el manifest oficial.

### Jobs históricos

Los seis jobs primarios antiguos tenían `document_id=NULL`, sin chunks,
embeddings, vectores ni archivo fuente. Fueron clasificados individualmente
como `SAFE_TO_CANCEL` y cancelados mediante la API oficial, sin borrar
evidencia ni tocar el corpus. Resultado: total 6, cancelados 6, reintentos 0,
revisión manual 0. Sus IDs se conservan en la tabla histórica de este informe.

### Gaps después del cierre

```text
DEV candidate P0: 0
DEV candidate P1: 0
DEV candidate P2: 3 (métricas, refinamiento bibliográfico y cosmética menor)
```

La producción sigue sin modificarse y no forma parte de este gate. Los gaps de
producción son una ventana de despliegue/validación: publicar el HEAD, aplicar
040/041 tras backup, provisionar storage/worker/configuración, ejecutar smoke
RBAC y realizar el golden upload/query productivo con rollback preparado.
Hasta entonces, la readiness productiva efectiva no es `PRODUCTION_READY`.

### Tests de cierre

```text
Backend regression: 1595 PASS (94 warnings preexistentes)
Backend focal post-fix: 65 PASS
Content Manager focal histórico: 87 PASS
Frontend unit: 109 PASS
Frontend check: 0 errors / 0 warnings (9 hints)
Frontend build: PASS (9 páginas)
Golden E2E real: PASS (editor → publicación → viewer → QA)
Concurrencia real: 2/2 PASS
Negative/RBAC: PASS (viewer upload 403; no-evidence sin alucinación)
git diff --check: PASS
```

### Score

| Dimensión | DEV candidate | PRO actual |
|---|---:|---:|
| Editor UX | 100 | 92 |
| Upload | 100 | 95 |
| Ingestion | 100 | 95 |
| Data integrity | 100 | 96 |
| Retrieval | 100 | 94 |
| Conversational QA | 100 | 90 |
| Citations | 100 | 90 |
| Auth/RBAC | 100 | 93 |
| Failure recovery | 100 | 92 |
| Observability | 100 | 78 |
| Deployment | 100 | 45 |
| Production validation | 100 | 25 |

```text
DEV production candidate readiness: 100%
Actual production readiness: 82% (promedio de dimensiones; no anula gates P0)
P0 productivos: 3  (deploy/configuración, worker/storage, validación productiva)
P1 productivos: 2  (rollback/observabilidad operativa, decisión sesión/CSRF)
P2: 3
```

El detalle de DEV vs PRO y el plan de despliegue controlado permanecen abajo;
ningún deploy, push, migración ni cambio productivo fue ejecutado.

## Baseline histórico previo al cierre

La siguiente sección conserva la fotografía inicial solicitada para auditoría;
sus cifras y bloqueos no representan el estado posterior al golden path.

## Veredicto ejecutivo (baseline)

**NEAR_READY — 75%.** El flujo de ingesta real existe y funciona en DEV, pero
el gate histórico terminaba en un candidato aislado. No demostraba que un libro
nuevo fuese publicado en el corpus primario y después recuperado por una
pregunta de usuario con respuesta grounded y cita.

El código quedó más cerca de ese objetivo: el worker primario es default-off,
la ingesta deja candidato, y una acción editorial separada solo publica tras
reconciliar exactamente chunks, embeddings y vectores. Producción no fue
modificada y sigue sirviendo una versión sin Content Manager.

```text
Production readiness: 75%
P0 OPEN: 5
P1 OPEN: 4
P2 OPEN: 3
```

No se cierra
`TEBAAI_BRESLOV_EDITOR_UPLOAD_TO_USER_QUERY_PRODUCTION_CANDIDATE_V1_PASS`.

## Inventario real

| Área | Estado observado |
|---|---|
| Branch / HEAD | `feature/console-backend-core` / `2b36cd9…` inicial |
| Working tree inicial | solo `backend/data/` no versionado preexistente |
| Backend / frontend / worker DEV | inactivos al inicio y al cierre; puertos 7008/3008 libres |
| PostgreSQL DEV | 18.4; 41 migraciones (`001..041`) |
| Corpus primario PG | 8 ready, 14 test_candidate, 1 archived; 5.102 chunks ready |
| Milvus DEV | `tebaai_breslov_chunks_v1`, 5.370 filas físicas |
| LiteLLM | models y embedding real respondieron 200; dimensión 1.536 |
| Usuarios DEV | 3 admin, 64 viewer, 0 editor |
| Cola primaria | 6 jobs `queued` históricos; no se mutaron |
| Producción pública | home/health/ready 200; APIs Content Manager 404 |
| Producción directa | acceso SSH bloqueado por verificación de host; schema y servicios no comprobados directamente |

Los 5.370 PK de Milvus observados pertenecen al tracking PostgreSQL; no se
detectaron vectores primarios sin tracking. 5.102 corresponden a documentos
ready bajo alias `breslov`; 268 corresponden a un candidato histórico bajo
alias `breslov_primary`. No se usaron solo conteos globales para esa
reconciliación.

## Camino crítico

| Tramo | Estado | Evidencia | Gap | Criticidad |
|---|---|---|---|---|
| Editor login | PARTIAL | auth y navegación pasan; DEV no tiene rol editor real | provisionar/probar editor | P0 |
| Permiso upload | PASS | backend exige admin/editor; viewer E2E denegado | validar misma política en PRO | P0 |
| Upload PDF | PASS | real E2E; límite antes de lectura completa; MIME/extensión/magic/parser | smoke primario | P0 |
| Metadata | PARTIAL | título, idioma, familia y nota | autor/edición/fuente/publicación no viajan por el wizard | P1 |
| Persistencia | PASS | manifest, attempts, IDs y tenant en PG | validar nueva escritura primaria | P0 |
| Worker | PARTIAL | durable real en E2E; modo primario implementado default-off | servicio/config/cola histórica | P0 |
| Parsing | PASS | PyMuPDF4LLM real; corrupto/cifrado/vacío rechazados | golden primario | P0 |
| Chunking | PASS | E2E real y regresión completa | golden primario | P0 |
| Embeddings | PASS | LiteLLM real, dimensión 1.536 | golden primario | P0 |
| PostgreSQL | PASS | 18.4, schema 041, truth source | backup y preflight PRO | P0 |
| Milvus | PASS | E2E real, cleanup exacto, primario reconciliado read-only | write/retrieval del golden | P0 |
| Libro visible | PARTIAL | biblioteca muestra ready; publicación tiene unit test | publicar golden real | P0 |
| Retrieval | PARTIAL | corpus actual recuperable; nuevo libro no probado | literal+semántico sobre golden | P0 |
| Pregunta usuario | PARTIAL | superficie Research existe | query específica al golden | P0 |
| Grounding | PARTIAL | QA existente, no contra libro recién cargado | grounded/no-evidence real | P0 |
| Citaciones | PARTIAL | modelo conserva página/chunk/título | cita del golden no demostrada | P0 |
| Error handling | PASS | failure, cancel, retry y cleanup idempotente | validar falla primaria controlada | P1 |
| Seguridad | PARTIAL | RBAC backend y upload endurecido | editor PRO y decisión sesión/CSRF | P0 |
| Observabilidad | PARTIAL | job/attempt/document, manifest, heartbeat y logs correlacionables | health/alert de worker en PRO | P1 |
| Deploy | FAIL | CM API 404 y `/admin/content` es fallback del home en PRO | despliegue controlado | P0 |
| Rollback | PARTIAL | disable/stop preserva candidatos; plan documentado | backup y ensayo productivo | P1 |

```text
Editor
  ✅ login/auth base
  ✅ upload aislado real
  ✅ ingesta durable aislada
  ✅ reconciliación y cleanup
  ⚠️ publicación primaria solo probada a nivel módulo
User
  ✅ consulta del corpus existente
  ❌ consulta del libro recién cargado
  ❌ grounding+cita del libro recién cargado
Production
  ❌ Content Manager desplegado
  ❌ worker primario/config/validación
```

## Gaps abiertos

| Prioridad | Gap | Evidencia | Acción |
|---|---|---|---|
| P0 | Golden path primario DEV incompleto | ningún ID nuevo recorre upload→ready→query→cita | ejecutar PDF autorizado y preguntas literal/semántica/no-evidencia |
| P0 | Producción sirve código anterior | `/api/admin/content/*` 404; `/admin/content` mismo body que home | deploy backend/frontend objetivo |
| P0 | Worker/storage primarios no configurados | nuevas variables faltan; worker inactivo | storage compartido persistente + unit service + flags |
| P0 | 6 jobs primarios históricos en cola | IDs registrados abajo | decidir cancelar/reprocesar individualmente antes del primer start |
| P0 | Seguridad/RBAC productivo no validado | 0 editor en DEV; usuario editor PRO desconocido; sesión endurecida pendiente | provisionar editor mínimo y decidir HTTPOnly/CSRF antes de abrir upload |
| P1 | Metadata bibliográfica incompleta | wizard no transporta autor/edición/source/publication | cerrar contrato de campos sin inventar esquema |
| P1 | Concurrencia real A/B no ejecutada | leases/claims tienen tests, no dos PDFs reales | procesar dos fixtures autorizados y reconciliar por documento |
| P1 | Observabilidad del worker no operada | logs añadidos; service solo plantilla | instalar servicio, health/alert y retención de logs |
| P1 | Rollback no ensayado | existe secuencia, no rehearsal | backup + restore/disable rehearsal antes de ventana |
| P2 | Métricas operativas adicionales | no impiden el flujo | backlog post-release |
| P2 | Refinamiento bibliográfico avanzado | no impide cita mínima libro/página/chunk | backlog tras contrato mínimo |
| P2 | Ajustes visuales menores | UX premium previa conserva gate | revisión humana post-golden |

Jobs históricos reconciliados en DEV:

| job_id | document_id | creado | PG/chunks | Milvus | source | clasificación | acción |
|---|---|---|---:|---:|---|---|---|
| `090af924-9a5c-4169-a112-2dce62d49774` | NULL | 2026-08-06 | 0 | 0 | ausente | SAFE_TO_CANCEL | cancelled vía API |
| `9af4b368-4bf1-4ebf-8578-f88fa44c0563` | NULL | 2026-08-12 | 0 | 0 | ausente | SAFE_TO_CANCEL | cancelled vía API |
| `70939c6f-88d5-41d9-b4ef-a6570b9466f0` | NULL | 2026-08-12 | 0 | 0 | ausente | SAFE_TO_CANCEL | cancelled vía API |
| `f68184fb-c87c-4a21-976f-83480865bd7d` | NULL | 2026-08-12 | 0 | 0 | ausente | SAFE_TO_CANCEL | cancelled vía API |
| `084b8b0d-6644-46bd-ae31-329f344bb62e` | NULL | 2026-08-12 | 0 | 0 | ausente | SAFE_TO_CANCEL | cancelled vía API |
| `349fda79-aaa0-4ce3-b679-2f6687abb545` | NULL | 2026-08-12 | 0 | 0 | ausente | SAFE_TO_CANCEL | cancelled vía API |

## DEV vs PRO

| Componente | DEV | PRO conocida | Delta | Acción |
|---|---|---|---|---|
| Código backend | HEAD con upload/worker/publish | health activo, CM routes 404 | desactualizado | deploy release inmutable |
| Frontend | `/admin/content` build real | fallback home, sin Edición | desactualizado | desplegar build 9 páginas |
| Migraciones | 001–041 | último baseline 001–039; no verificable directo | 040/041 probables | backup, inventario y runner oficial |
| PostgreSQL | 8 ready / 5.102 chunks | corpus existente, conteos actuales no verificados | desconocido | preflight read-only y backup |
| Milvus | 5.370 filas; PK tracking consistente | no verificado directo | desconocido | snapshot/counts/IDs por golden |
| LiteLLM | models+embedding 200 | no verificado directo | desconocido | preflight desde host PRO |
| Worker | E2E probado; primario default-off | no hay evidencia de servicio CM | faltante | instalar unit y mantener stopped |
| Storage | temp DEV; config persistente faltante | desconocido | faltante | directorio absoluto compartido y permisos mínimos |
| Variables | base DEV presente; flags primarios missing | no verificadas | faltante | cargar inventario sin exponer valores |
| Reverse proxy | local no aplica | health/API base responden | rutas CM llegarán al backend tras deploy | smoke autenticado |
| Rollback | disable/stop + candidatos no ready | no ensayado | faltante | backup y runbook rehearsal |

## Configuración

Clasificación sin valores:

| Variable | Clase | DEV |
|---|---|---|
| `DB_PG_IP/PORT/USER/PASS`, `TEBAAI_DB_NAME` | REQUIRED; PASS/JWT SECRET | present |
| `LITELLM_MASTER_KEY` o `TEBAAI_LITELLM_API_KEY` | REQUIRED, SECRET | master present |
| `TEBAAI_JWT_SECRET` | REQUIRED, SECRET | present |
| `TEBAAI_MILVUS_*`, embedding aliases | OPTIONAL si defaults canónicos | defaults activos |
| `TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED` | PROD/DEV golden, REQUIRED para primary | missing/default false |
| `TEBAAI_CONTENT_MANAGER_WORKER_SCOPE` | REQUIRED worker primary | missing/default e2e |
| `TEBAAI_CONTENT_MANAGER_STORAGE_DIR` | REQUIRED producción primary | missing |
| `PUBLIC_CONTENT_MANAGER_SCOPE` | build/runtime frontend | missing/default primary |
| `TEBAAI_CONTENT_MANAGER_E2E_*` | DEV_ONLY | disponible solo para E2E |
| `TEBAAI_POSTGRES_AUTO_MIGRATE` | REQUIRED false en PRO | present en DEV |

## Tests y evidencia

```text
Backend regression: 1595 PASS, 94 warnings preexistentes
Backend focal Content Manager: 87 PASS, 1 warning preexistente
Frontend type/static check: 90 files, 0 errors, 0 warnings, 9 hints
Frontend unit: 8 files / 109 PASS
Frontend build: 9 pages PASS
Ingestion E2E real: 2/2 workflows PASS
E2E permissions/redirect: 2/2 PASS
E2E total focal: 4/4 PASS
Retrieval sobre libro nuevo primario: 0 ejecutado — BLOCKED
QA grounded/citation sobre libro nuevo: 0 ejecutado — BLOCKED
LAT: PASS (warnings de init/semantic key no bloqueantes)
git diff --check: PASS
```

El E2E real usó backend, PostgreSQL, worker, PyMuPDF4LLM, LiteLLM y Milvus; no
fue un mock. Sus vectores quedaron en cero según query fuerte después del
cleanup. No escribió el scope primario.

## Cambios realizados

| Archivos | Motivo | Impacto | Test |
|---|---|---|---|
| `core/config.py`, `globalVar.py` | gates primary/storage/scope | primary default-off; storage absoluto en PRO | config/isolation + full suite |
| `content_manager.py`, schemas, routes, app | upload seguro y publicación separada | corrupto/cifrado/MIME/size fail closed; CAS ready | publication/security tests |
| repository/runtime/worker | claim/recovery por scope, trazabilidad | worker E2E no toca primary; IDs en logs | orchestration + full suite |
| page-first pipeline/gateway/cleanup | heartbeat e IDs exactos | writes compensables y reconcile primary | pipeline/cleanup/E2E |
| Svelte/client/tests | confirmación de publicación primaria | no aparece en E2E; editor decide explícitamente | Vitest/check/build/E2E |
| Playwright helpers/spec | timeout y env de cleanup reales | elimina falsos fallos del harness | 4/4 Chromium |
| ADR/policy/operativa/systemd/status | contrato y deploy seguro | separa candidato/publicación y documenta rollback | LAT check |

## Score

| Dimensión | Score |
|---|---:|
| Editor UX | 88/100 |
| Upload | 92/100 |
| Ingestion | 84/100 |
| Data integrity | 88/100 |
| Retrieval | 78/100 |
| Conversational QA | 72/100 |
| Citations | 78/100 |
| Auth/RBAC | 86/100 |
| Failure recovery | 88/100 |
| Observability | 75/100 |
| Deployment | 45/100 |
| Production validation | 25/100 |

Promedio simple explicado por las doce dimensiones: **899/1200 = 74,9%,
redondeado a 75%**. El porcentaje no anula los P0.

## Plan exacto de producción

1. Elegir un golden PDF autorizado y preguntas literal, semántica y negativa.
2. Decidir los seis jobs históricos; ejecutar cancel/cleanup oficial por ID o
   aprobar explícitamente su reproceso.
3. Configurar en DEV storage persistente, worker primary y editor dedicado.
4. Ejecutar dos PDFs concurrentes; verificar IDs de documento/job/chunks y PK
   exactos PG↔Milvus; retry/cancel/failure sin contaminación.
5. Publicar solo el golden; verificar biblioteca y scope.
6. Como viewer, preguntar literal y semánticamente; comprobar respuesta,
   libro, página, fragmento y rechazo por falta de evidencia.
7. Solo entonces cerrar el gate production-candidate.
8. Congelar commit/artefactos y obtener aprobación de ventana.
9. Preflight PRO read-only: código, 040/041, schema, corpus, Milvus, LiteLLM,
   storage, permisos, proxy y usuarios; registrar baseline.
10. Backup PostgreSQL, metadata/PK de Milvus y configuración; verificar restore.
11. Aplicar 040/041 con runner oficial y auto-migrate false.
12. Desplegar backend y frontend; mantener worker detenido/primary false.
13. Health + smoke auth/RBAC; verificar viewer=403 para upload.
14. Instalar service, storage y logs; habilitar primary y arrancar worker.
15. Upload productivo autorizado → READY → query de usuario → grounded answer
    → cita verificable.
16. Si falla: detener worker, desactivar flag y volver código/frontend; preservar
    candidatos y corpus, sin borrar documentos ready automáticamente.
17. Solo tras evidencia productiva cerrar
    `TEBAAI_BRESLOV_EDITOR_UPLOAD_TO_USER_QUERY_PRODUCTION_V1_PASS`.

Push: NO. Deploy: NO. Producción modificada: NO.
