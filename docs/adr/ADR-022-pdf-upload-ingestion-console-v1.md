# ADR-022 — PDF Upload & Ingestion Console V1 (Content Manager)

## Estado

Aceptado; gates funcionales y UX premium DEV cerrados (2026-08-05).

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

## Continuación de UX premium — 2026-08-05

La UI inicial (tres etapas, DaisyUI genérico) fue reemplazada por una
superficie premium que continúa la identidad de Breslov Research: mismos
tokens (`app.css`), identidad `רבי נחמן · REBE NAJMÁN · BRESLOV RESEARCH`,
tipografía editorial, pills, acordeones y tratamiento RTL de `/research`.
Sin shell administrativo paralelo ni segundo design system.

- flujo de cinco etapas (Archivo → Información → Confirmación →
  Procesamiento → Resultado) con estados reales del backend; sin progreso
  simulado; cancelación solo en estados cancelables; retry real;
- capa API tipada y vocabulario editorial centralizados (preparación i18n);
- historial, estado vacío, detalle con diagnóstico técnico contraíble;
- responsive: tabla editorial desktop / cards móvil, sin overflow a 390px;
- accesibilidad: teclado (dropzone Enter/Space), focus visible, aria-live,
  estados por texto+icono+color, `prefers-reduced-motion`;
- Playwright Content Manager 11/11 con backend real en `breslov_e2e`;
  capturas 13 en 1440/1024/768/390;
- fix mínimo de cleanup: borrado de vectores del manifest por ID exacto
  además de attempt_key (query escalar silenciosamente vacía dejaba residuos
  en la colección aislada); test de regresión agregado (1556 PASS backend).

## Consecuencias

- Los gates funcionales y UX del Content Manager V1 quedan cerrados en DEV.
- PostgreSQL conserva verdad; Milvus E2E es derivado y totalmente compensable.
- Un fallo conserva diagnóstico y limpia únicamente recursos del attempt.
- `breslov_primary`, documentos ready e Interior Final quedan fuera del worker E2E.
- Los gates del Content Manager V1 quedan cerrados en DEV; no se habilita
  ingesta `breslov_primary`, promoción a ready, publicación ni edición manual.

## Rollback

Tras aplicar 041 no se elimina una migración versionada: cualquier rollback de
schema requiere migración forward. El runtime puede detenerse mediante
`content-worker-dev.sh stop`; los datos E2E se compensan por manifest y la
colección aislada puede quedar vacía sin afectar primary. El rollback de código
se realiza por commits, preservando 040/041 y el historial de auditoría.
