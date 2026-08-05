# ADR-022 — PDF Upload & Ingestion Console V1 (Content Manager)

## Estado

Aceptado; orquestador funcional DEV cerrado, UX premium pendiente (2026-08-05).

## Contexto

Breslov Research necesitaba una superficie administrativa para cargar nuevas
fuentes documentales (PDFs) de forma controlada, validarlas, detectar
duplicados, orquestar el pipeline de ingesta existente y dejar el documento en
estado `test_candidate` para revisión posterior.

Antes de esta fase, la ingesta solo podía ejecutarse mediante scripts
manuales. No existía un mecanismo de upload seguro, validación preliminar,
tracking de estado ni una interfaz administrativa.

## Decisión

Arquitectura en dos capas:

### Backend — módulo `content_manager.py`

- **Upload**: validación de MIME, magic bytes, tamaño, páginas, SHA-256; almacenamiento temporal con TTL; detección de duplicados por SHA-256 y filename.
- **Job**: máquina de estados explícita con 16 stages (`uploaded → … → completed`); progreso por etapas; retry y cancelación seguras; diagnóstico post-ingesta.
- **Seguridad**: roles admin/editor requeridos para todas las operaciones; `requested_status=ready` rechazado explícitamente (solo `test_candidate` en V1).
- **Idempotencia**: upload no duplica documentos con SHA-256 idéntico; job con mismo upload_id retorna el job existente.

### Frontend — `admin/content`

- Página Astro + componente Svelte (`ContentManager.svelte`)
- Flujo guiado: Archivo → Metadata → Confirmación → Progreso → Resultado
- Lista de cargas recientes con estados, resumen operativo, estado vacío
- Desktop: tabla editorial; Móvil: cards
- Reutilización del sistema de diseño existente (Layout, Tailwind/DaisyUI)

### Datos

- Migración `040_content_manager_uploads_and_jobs.sql` con tablas
  `content_manager_uploads` y `content_manager_jobs`
- Scope organizacional preparado (`organization_id`, `workspace_id`, `project_id`)
- Timestamps, auditoría y cleanup configurable

## Invariantes

- Upload ≠ publicación.
- Job status ≠ document status.
- Duplicado exacto (mismo SHA-256) no se reingiere.
- Viewer y guest no pueden acceder a rutas de admin.
- `requested_status=ready` es rechazado.
- Frontend no ejecuta scripts; toda operación pasa por API tipada.
- UX premium: misma identidad visual que `/research`.

## No decisiones

- No se implementa editor manual de páginas, chunks, embeddings ni OCR.
- No se permite promoción a `ready` desde esta consola.
- No se despliega a producción.
- No se modifica el corpus existente.

## Continuación de hardening — 2026-08-05

Se aprobó como diseño incremental la migración 041 y las capas
`content_manager_state.py`, `content_manager_repository.py` y
`content_manager_worker.py`. La decisión concreta usa PostgreSQL como cola
durable: claim exclusivo con `FOR UPDATE SKIP LOCKED`, lease/heartbeat,
compare-and-swap de transiciones, attempts y manifest normalizado. La
idempotencia activa queda protegida por índice único parcial y el acceso a
uploads/jobs se restringe por organización, workspace y proyecto resueltos
desde el scope autorizado.

La continuación funcional implementa `ConcretePageFirstPipeline` sin dispatch
por obra: extracción PyMuPDF4LLM por página, persistencia page-first, chunks,
embeddings LiteLLM, indexación y reconciliación Milvus por `attempt_key`. Los
IDs se registran incrementalmente en el manifest. El cleanup compensatorio es
Milvus-first, elimina solo IDs propios, audita cada resultado y admite repetición.

La escritura E2E queda default-off y exige DEV, flag explícito, SHA de fixture,
scope `breslov_e2e` y colección `tebaai_content_manager_e2e_v1`; el claim del
worker también filtra ese scope. Migración 041 pasó dry-run revertido y fue
aplicada con el runner oficial sin reiniciar PostgreSQL. El E2E real terminó en
`test_candidate`, reconcilió 2/2 vectores y limpió dos veces sin tocar primary.

## Consecuencias

- El gate funcional del orquestador y la consola de ingesta queda cerrado en DEV.
- PostgreSQL conserva verdad; Milvus E2E es derivado y totalmente compensable.
- Un fallo conserva diagnóstico y limpia únicamente recursos del attempt.
- `breslov_primary`, documentos ready e Interior Final quedan fuera del worker E2E.
- El gate general continúa bloqueado hasta completar la UX premium vinculante.

## Rollback

Tras aplicar 041 no se elimina una migración versionada: cualquier rollback de
schema requiere migración forward. El runtime puede detenerse mediante
`content-worker-dev.sh stop`; los datos E2E se compensan por manifest y la
colección aislada puede quedar vacía sin afectar primary. El rollback de código
se realiza por commits, preservando 040/041 y el historial de auditoría.
