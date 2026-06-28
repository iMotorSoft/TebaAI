# Status actual - TebaAI

Objetivo: `desarrollo`

Ultima actualizacion: 2026-06-28 (consolidacion documental y retrieval bibliografico)

Este tablero contiene solo el estado tecnico vigente. La evolucion previa esta resumida en `status_historico_hasta_2026-06-28.md` y conservada con detalle en Git.

## Directorio y rama

- raiz: `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI`;
- rama funcional: `feature/console-backend-core`;
- la rama local esta un commit por delante de `origin/feature/console-backend-core` al iniciar esta consolidacion.

## Estado general

- Backend Litestar con configuracion tipada, lifecycle y PostgreSQL 18 mediante `psycopg 3 async`.
- Frontend Astro 7 + Svelte 5, Tailwind CSS 4 y DaisyUI 5.
- Autenticacion con Argon2id, access JWT, refresh token opaco, rotacion, deteccion de reutilizacion y roles `admin`, `editor`, `viewer`.
- Biblioteca con ingesta de Markdown, texto y PDF, chunking, PostgreSQL FTS y busqueda HTTP autenticada.
- Milvus 2.6 funciona como indice vectorial derivado; PostgreSQL conserva texto y metadata como fuente de verdad.
- LiteLLM se usa para embeddings `text-embedding-3-small`; no existe modelo generativo ni RAG conversacional.

Referencias canonicas:

- `lat.md/global-configuration-facade-policy.md`;
- `lat.md/authentication-security-policy.md`;
- `lat.md/library-retrieval-models-policy.md`;
- `lat.md/postgres-driver-policy.md`;
- `lat.md/service-preflight-methodology.md`.

## Runtime validado

- migraciones `001` a `007` disponibles;
- 1.990 chunks bibliograficos vigentes y 1.991 vectores registrados por la ejecucion historica inicial;
- 284 chunks enriquecidos con metadata de pagina de alta confianza;
- modos de busqueda textual: `auto`, `fts`, `phrase`, `trigram`;
- modo `hybrid`: PostgreSQL FTS + Milvus, deduplicado por `chunk_id`;
- endpoint `POST /library/search` protegido por autenticacion;
- UI disponible para login, administracion de usuarios y busqueda bibliografica.

La diferencia 1.990/1.991 queda como deuda de reconciliacion: no debe normalizarse documentalmente sin auditar PostgreSQL y Milvus.

## Validacion actual

- backend: `uv run pytest` = 197 PASS, 48 warnings preexistentes;
- frontend: `pnpm check` = 0 errores, 0 warnings, 0 hints;
- frontend: `pnpm build` = 4 paginas, PASS;
- Playwright: 12 tests descubiertos correctamente; no se ejecutaron contra servicios reales en esta consolidacion;
- Playwright sin credenciales: 3 tests autenticados seleccionados, 3 skips esperados y cero intentos con fallback;
- Playwright autenticado requiere credenciales E2E cargadas por entorno;
- evaluacion bibliografica hibrida: 26/30 PASS;
- `lat check`: PASS, cero errores;
- `git diff --check`: PASS.

La suite reporta deuda preexistente por `datetime.utcnow()` y claves JWT cortas usadas en tests; no afecta el PASS, pero debe corregirse.

## Calidad documental y operativa

- `AGENTS.md` es la fuente operativa canonica.
- el status runtime fue compactado; el status duplicado de Astro fue retirado.
- las credenciales E2E no tienen fallback versionado y deben venir del entorno.
- LAT enlaza configuracion, auth y retrieval con referencias `@lat` en codigo.
- `lat check` es gate obligatorio para cambios documentales.
- `lat search` requiere `LAT_LLM_KEY`, `LAT_LLM_KEY_FILE` o `LAT_LLM_KEY_HELPER`; sin clave se usa `lat locate`.

## Pendientes prioritarios

1. Reconciliar la diferencia entre 1.990 chunks vigentes y 1.991 vectores historicos.
2. Reejecutar backend, frontend y E2E con servicios reales disponibles.
3. Sustituir almacenamiento frontend de tokens por cookies `httpOnly` con proteccion CSRF documentada.
4. Implementar refresh automatico y expiracion de sesion visible.
5. Completar paginacion y busqueda en administracion de usuarios.
6. Definir el limite entre plataforma generica TebaAI y la vertical Breslov.
7. Evaluar OCR para PDF escaneado y metadata de confianza media.
8. Diseñar cualquier RAG generativo mediante ADR, sin incorporarlo al endpoint de retrieval existente.
9. Eliminar `datetime.utcnow()` y usar claves JWT de test de al menos 32 bytes.

## Seguridad

- No guardar secretos ni credenciales de prueba en codigo o documentacion.
- Las variables `TEBAAI_E2E_ADMIN_EMAIL` y `TEBAAI_E2E_ADMIN_PASSWORD` son obligatorias para E2E autenticado.
- PostgreSQL, Milvus y LiteLLM son servicios externos; no gestionarlos automaticamente.
- No imprimir DSN, tokens ni API keys completos.

## Historial

- resumen tecnico previo: `status_historico_hasta_2026-06-28.md`;
- arquitectura viva: `../../lat.md/lat.md`;
- Git conserva el detalle exacto de cada fase.
