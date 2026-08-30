# Gestor de Contenidos — documentación operativa

Ruta: `/admin/content` (protegida por rol admin/editor; backend guarda con
`require_auth` + roles y scope autorizado).

## Flujo visible

Cinco etapas guiadas:

1. **Archivo** — dropzone accesible (drag, click, teclado Enter/Space) con
   selector nativo; ficha del archivo con nombre, tamaño, páginas, tipo,
   estado de validación; SHA-256 abreviado en "Detalles técnicos" contraíble.
2. **Información** — título de la obra, idioma principal (Automático,
   Español, Inglés, Hebreo, Mixto, Desconocido), familia documental opcional,
   nota administrativa opcional. Los parámetros técnicos resueltos por el
   backend quedan fuera del formulario.
3. **Confirmación** — ficha legible (archivo, título, idioma, páginas,
   tamaño, familia, duplicados, proceso propuesto, estado final esperado);
   mensajes: "El documento será procesado y quedará como candidato para
   revisión." y "Esta operación no publica ni aprueba el documento."
   Acción principal: **Iniciar procesamiento** (nunca Publicar/Aprobar).
4. **Procesamiento** — siete etapas editoriales (Validando el archivo,
   Extrayendo las páginas, Normalizando el contenido, Organizando las
   secciones, Preparando la búsqueda, Generando el índice, Verificando el
   resultado) con estado real (pendiente/en curso/completada/fallida); barra
   porcentual secundaria con valores reales del backend; nota de persistencia
   ("Podés salir de esta pantalla…") respaldada por el job durable.
5. **Resultado** — Documento procesado / con observaciones / No se pudo
   completar; resumen real (páginas, páginas con contenido, fragmentos,
   registros de búsqueda); acciones: Abrir diagnóstico, Probar en
   Investigación (navega a `/research`; nota "Este documento todavía no fue
   aprobado."), Volver al gestor, Reintentar (job fallido/cancelado). En scope
   primario, un candidato reconciliado ofrece una decisión posterior y
   confirmada: **Publicar para consulta**.

## Componentes reutilizados

- `Layout.astro` (app.css + research.css) y tokens `--navy-*`, `--ivory-*`,
  `--paper-200`, `--gold-*`, `--ink-*`, `--line`, `--serif`, `--sans`.
- Identidad `רבי נחמן · REBE NAJMÁN · BRESLOV RESEARCH` (patrón research-brand).
- Acordeones `details/summary`, pills de estado, tratamiento RTL de
  `research.css` (Noto Serif Hebrew, unicode-bidi plaintext).
- `textDirection.ts` para dirección de títulos/filenames hebreos.
- Estrategia responsive tabla-desktop / cards-móvil.

## Componentes nuevos (justificación)

| Componente | Razón |
|---|---|
| `contentManagerClient.ts` | Capa API tipada única; auth, errores y polling centralizados |
| `contentManagerLabels.ts` | Vocabulario editorial + códigos → mensajes; i18n-ready |
| `content-manager.css` | Capa premium delgada sobre tokens existentes |
| `ContentManager.svelte` | Lista/resumen/detalle premium (reemplaza la versión genérica) |
| `ContentManagerWizard.svelte` | Flujo de cinco etapas con estados reales |
| `cm-dropzone`, `cm-stepper`, `cm-status`, `cm-message`, `cm-timeline` | Superficies que no existían y son específicas del flujo |

## Estados visuales

Vacío, Validando, Archivo válido, Archivo inválido (INVALID_PDF,
PDF_ENCRYPTED, FILE_TOO_LARGE, PAGE_LIMIT_EXCEEDED), Duplicado exacto
(EXACT_DUPLICATE, sin segundo job), Esperando confirmación, En procesamiento,
Candidato para revisión, Con observaciones, Fallido (INGESTION_FAILED,
REUPLOAD_REQUIRED), Cancelado, Retry (nuevo attempt, historial conservado).

## Polling

2 s sobre `GET /admin/content/jobs/{id}`; se detiene en estado terminal y al
destruir el componente; 401 redirige a `/login`; errores transitorios
continúan el polling; al volver al detalle se reanuda.

## Retry y cancelación

- Retry: `POST /admin/content/jobs/{id}/retry` (solo failed/cancelled); crea
  un nuevo attempt con historial conservado. Si el archivo temporal expiró:
  "El archivo original ya no está disponible. Volvé a cargarlo para intentar
  nuevamente."
- Cancelación: `POST /admin/content/jobs/{id}/cancel` solo en uploaded /
  ready_to_ingest / queued. En etapas posteriores se explica que el
  procesamiento ya comenzó y no puede cancelarse de forma segura.

## Responsive / RTL / accesibilidad

- 1440×900 y 1024×768: tabla editorial; 768×1024: grid 2 columnas;
  390×844: cards, sin overflow horizontal, flujo completo operable.
- Hebreo: `dir=rtl` solo en el contenido que lo requiere (título/filename),
  interfaz LTR; niqqud preservado; IDs en `unicode-bidi: isolate`.
- Teclado completo, focus visible gold, aria-live para progreso/resultado,
  estados por texto+icono+color, `prefers-reduced-motion` respetado.

## E2E browser

Suites `astro/e2e/content-manager-*.spec.ts` (Playwright chromium):

- `premium`: flujo real (backend + worker `breslov_e2e` + fixture autorizado
  de sha único por corrida), cancel+retry real, duplicado, permisos.
- `mobile`: 390×844 con fixtures tipados (sin escrituras reales).
- `rtl`: hebreo/niqqud/filename + accesibilidad (teclado, focus, aria-live).
- `captures`: 13 capturas de evidencia en 1440/1024/768/390.

## Restricción de scope y modo primario

El modo por defecto solo procesa `breslov_e2e` (claim filtrado) y el gateway exige
DEV + flag E2E + sha de fixture autorizado + colección
`tebaai_content_manager_e2e_v1`. El frontend fija el scope por configuración
de despliegue (`PUBLIC_CONTENT_MANAGER_SCOPE`, default `breslov_primary`); no
existe selector de scope/colección en la UI.

El modo primario es default-off y requiere en el proceso worker:

```text
TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED=true
TEBAAI_CONTENT_MANAGER_WORKER_SCOPE=breslov_primary
TEBAAI_CONTENT_MANAGER_STORAGE_DIR=/ruta/absoluta/persistente
```

El backend que recibe uploads debe usar el mismo storage persistente y tener
acceso de escritura; el worker necesita leer y eliminar esos archivos. En
producción `TEBAAI_POSTGRES_AUTO_MIGRATE=false`. El scope E2E nunca se habilita
fuera de DEV. No se debe iniciar el worker primario mientras existan jobs
históricos en cola sin una decisión individual documentada.

## Publicación y rollback

`POST /admin/content/jobs/{job_id}/publish` exige rol `admin|editor`, scope
autorizado, job terminal, documento `test_candidate`, manifest consistente y
coincidencia exacta PostgreSQL↔Milvus. Solo entonces cambia a `ready`.

Rollback operativo antes de publicar: detener el worker y desactivar el flag;
los candidatos no participan del retrieval normal. Después de publicar, no se
debe borrar ni degradar el documento automáticamente: conservarlo o ejecutar
un plan específico respaldado y auditado para ese `document_id`.

La unidad de servicio de referencia está en
`ops/systemd/tebaai-content-manager-worker.service.example`; debe adaptarse a
paths, usuario y archivo de entorno del host.
