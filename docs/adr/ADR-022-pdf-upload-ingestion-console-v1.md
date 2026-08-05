# ADR-022 — PDF Upload & Ingestion Console V1 (Content Manager)

## Estado

Aceptado como diseño; implementación DEV bloqueada (2026-08-05).

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

## Consecuencias

- La migración, los contratos HTTP y la superficie inicial sirven como baseline, no como gate cerrado.
- El pipeline page-first real continúa distribuido entre servicios parciales y scripts específicos; no existe todavía un orquestador reusable, transaccional y aislado que pueda consumir un worker web.
- Los jobs actuales no avanzan por sí mismos desde `validating`, la idempotencia no es atómica y las consultas por ID no aplican la cadena tenant completa.
- Hasta resolver esos bloqueos, no se ejecutan E2E de escritura ni se declara funcional o visualmente listo el Gestor.
- La fase futura debe extraer el pipeline reusable, añadir ownership/leases y cleanup probado, y recién después cerrar seguridad, integración y UX premium.

## Rollback

Eliminación de la migración 040, el módulo `content_manager.py`, las rutas en
`routes.py`, la página `admin/content.astro` y el componente
`ContentManager.svelte`. Sin impacto en datos existentes.
