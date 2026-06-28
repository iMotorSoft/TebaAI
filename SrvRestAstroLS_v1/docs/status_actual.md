# Status actual - TebaAI Runtime

Objetivo: `desarrollo`

Ultima actualizacion: 2026-06-28

## Estado general

Configuracion global y PostgreSQL 18 implementados. Bootstrap tecnico completo.

Esta es la bitacora tecnica principal del runtime TebaAI. Agrupa backend,
frontend Astro/Svelte e integracion frontend/backend para evitar bitacoras
paralelas prematuras.

## Alcance de esta bitacora

- Backend Litestar, dependencias Python, entrypoint, launchers y validaciones
  tecnicas.
- Frontend Astro/Svelte, build, check, rutas, UI y configuracion publica.
- Integracion frontend/backend, URLs, puertos, contratos HTTP, proxy local y
  validaciones Playwright.
- No cubre decisiones largas de arquitectura, que viven en `lat.md/`, ni ADRs
  resumidos, que viven en `docs/adr/`.

## Backend

- Entry point canonico:
  `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`.
- ASGI object: `app`.
- Puerto local backend: `7008`.
- Dependencias instaladas para fases futuras: `psycopg`, `psycopg-pool`,
  `pymilvus` y `litellm`.
- PostgreSQL, Milvus y LiteLLM siguen como servicios externos permanentes; esta
  fase no crea conexiones ni gestiona servicios.

## Frontend Astro

- Astro/Svelte vive en `SrvRestAstroLS_v1/astro/`.
- Puerto local Astro: `3008`.
- Stack actual: Astro 7, Svelte 5, Tailwind CSS 4 y DaisyUI 5.
- La configuracion publica frontend debe mantenerse separada de secretos.
- La fachada frontend comun debe ubicarse en
  `SrvRestAstroLS_v1/astro/src/components/global.js`, siguiendo el uso real de
  Team360.

## Integracion frontend/backend

- URL backend local esperada: `http://127.0.0.1:7008`.
- URL Astro local esperada: `http://127.0.0.1:3008`.
- Playwright + Chromium es el gate E2E oficial.
- Browser MCP puede usarse para diagnostico visual, pero no reemplaza tests
  Playwright reproducibles.

## Acciones realizadas

### 2026-06-25 - Infraestructura PostgreSQL 18

- Auditados todos los modulos PostgreSQL de Team360 (`modules/db/settings.py`,
  `pool.py`, `transaction.py`, `errors.py`, entrypoint, health, preflight).
- Identificados elementos reutilizables (pool lazy, dict_row, errores tipados,
  transacciones explicitas, startup/shutdown via Litestar lifecycle).
- Creado `infrastructure/postgres/errors.py` con jerarquia tipada.
- Creado `infrastructure/postgres/pool.py` con `create_pool`, `open_pool`,
  `close_pool`, `get_pool_from_state` (sin singleton global).
- Creado `infrastructure/postgres/transaction.py` con `fetch_one`, `fetch_all`,
  `execute`, `transaction` (async context manager).
- Creado `infrastructure/postgres/health.py` con `check_postgres_health`.
- Creado `infrastructure/postgres/migrations.py` con runner de SQL simples y
  tabla `schema_migrations`.
- Creado `core/lifespan.py` con `on_startup`/`on_shutdown`: crea pool, verifica
  conectividad, corre migraciones, asigna `app.state.pg_pool`.
- Creado `core/dependencies.py` con `get_pg_pool` para Litestar DI.
- Creado `routes/ready.py` con `GET /ready` que valida PostgreSQL via `SELECT 1`.
- Actualizado `routes/health.py` como liveness liviano (sin queries DB).
- Actualizado `ls_iMotorSoft_Srv01.py` con lifecycle y rutas `/health`, `/ready`.
- Creada migracion inicial `db/migrations/001_initialize_database.sql` con tabla
  `schema_migrations`.
- Creada base `tebaai` en PostgreSQL 18 Docker (encoding UTF8, template0).
- Actualizado `.env.example` con `TEBAAI_POSTGRES_DB=tebaai`.
- Creados `tests/test_infrastructure_postgres.py` (20 tests unitarios).
- 69 tests total (56 config + 13 globalVar + 20 infra) todos PASS.
- Smoke real: `/health` 200, `/ready` 200 con postgres up, pool creado y
  migracion aplicada. Sin secretos expuestos.
- No se modifico Team360. No se reinicio PostgreSQL. No se toco Milvus/LiteLLM.

### 2026-06-25 - Fundacion de configuracion global (core/config.py + globalVar.py)

- Creado `SrvRestAstroLS_v1/backend/core/__init__.py`.
- Creado `SrvRestAstroLS_v1/backend/core/config.py` con `AppSettings` tipado
  via `pydantic-settings`: grupos Runtime, PostgreSQL, Milvus, LiteLLM y Auth.
- Creado `SrvRestAstroLS_v1/backend/globalVar.py` como fachada estable sin
  side effects; no llama a `os.getenv()`.
- Agregada dependencia `pydantic-settings>=2.14.0` en `pyproject.toml`.
- Actualizado `.env.example` con todas las variables `TEBAAI_*`, secciones
  comentarios y precedencias.
- Creados `tests/conftest.py`, `tests/test_config.py` y
  `tests/test_global_var.py` (56 tests, todos PASS).
- `python -c "import globalVar; print(globalVar.SERVICE_NAME)"` PASS sin
  secretos visibles.
- `git diff --check`: PASS.
- No se modifico el entrypoint, no se crearon conexiones, no se toco infraestructura.

### 2026-06-27 - Auditoria de cierre (config + PostgreSQL)

- Corregida responsabilidad de `schema_migrations`: ahora solo
  `infrastructure/postgres/migrations.py` la crea y administra. El SQL
  `001_initialize_database.sql` quedo como placeholder fundacional sin objetos
  de aplicacion.
- Agregado `TEBAAI_POSTGRES_AUTO_MIGRATE=true` a `.env.example`, `core/config.py`,
  `globalVar.py` y `core/lifespan.py`. En desarrollo defaulta `true`; puede
  desactivarse via variable de entorno.
- Agregados 15 tests nuevos: `postgres_auto_migrate` (default + parsing),
  `POSTGRES_AUTO_MIGRATE` export, `create_pool_from_settings`,
  `ensure_schema_migrations_table`, `run_migrations` (aplica, skips, idempotente,
  error), lifecycle (startup migra si flag true, salta si false, salta si
  postgres disabled, shutdown cierra pool, shutdown sin pool no raisea).
- 84 tests total (todos PASS).
- Sin secretos expuestos, sin DSN real, sin TEAM360_, sin Team360 modificado,
  sin Docker restart, sin cambios Milvus/LiteLLM.
- Commits separados: config global (1) + PostgreSQL infra (2).

### 2026-06-28 - Autenticacion (usuarios, JWT, Argon2id, guards, bootstrap)

- Agregadas dependencias: `argon2-cffi==25.1.0`, `PyJWT==2.13.0`.
- Creado `modules/auth/domain.py`: `UserRole` enum (`ADMIN`, `EDITOR`, `VIEWER`),
  `User` dataclass con `.create()` factory, `AuthSession` dataclass con
  `.create()` factory.
- Creado `modules/auth/schemas.py`: `LoginRequest`, `RefreshRequest`,
  `LogoutRequest`, `CreateUserRequest`, `UpdateUserRequest`, `UserResponse`,
  `LoginResponse`, `TokenResponse`, `UserListResponse`.
- Creado `modules/auth/password.py`: `hash_password` / `verify_password` usando
  argon2-cffi (Argon2id) con soporte de pepper opcional desde `core/config.py`.
- Creado `modules/auth/tokens.py`: `create_access_token` (JWT con sub, type,
  jti, role, iat, nbf, exp, iss, aud), `decode_access_token` (valida exp, iss,
  aud, type), `generate_refresh_token` (opaco 48-bytes + SHA-256 hash).
- Creado `modules/auth/repository.py`: `UserRepository` con create,
  get_by_id, get_by_email (lower), list, update, update_password_hash,
  set_last_login.
- Creado `modules/auth/session_repository.py`: `AuthSessionRepository` con
  create, get_by_refresh_hash, revoke, revoke_family, get_active_by_family,
  update_last_used.
- Creado `modules/auth/service.py`: `AuthService` con login, refresh (rotation
  + reuse detection), logout (idempotent), get_current_user, create_user,
  list_users, get_user, update_user.
- Creado `modules/auth/guards.py`: `require_auth` (valida JWT en header),
  `require_roles(*roles)` (restringe por role).
- Creado `modules/auth/dependencies.py`: `get_current_user_payload`,
  `get_current_user_obj` (usan `get_pg_pool`, validan token, cargan user de DB).
- Creado `modules/auth/routes.py`: `POST /auth/login`, `POST /auth/refresh`,
  `POST /auth/logout`, `GET /auth/me`, `GET /users`, `POST /users`,
  `GET /users/{id}`, `PATCH /users/{id}`, `POST /users/{id}/activate`,
  `POST /users/{id}/deactivate`.
- Actualizado `ls_iMotorSoft_Srv01.py`: registradas todas las rutas auth.
- Creada migracion `db/migrations/002_create_auth_tables.sql`: tablas `users`
  y `auth_sessions` con indices unicos/lower.
- Creado `scripts/create_admin_user.py`: CLI bootstrap idempotente (Option A).
- Creados tests: `test_auth_password.py` (8 tests), `test_auth_tokens.py`
  (8 tests), `test_auth_service.py` (12 tests).
- Actualizado `.env.example` con `TEBAAI_BOOTSTRAP_ADMIN_*`.
- 116 tests total (todos PASS).
- `git diff --check`: PASS.
- Sin secretos expuestos, sin DSN real, sin Team360 modificado.
- Sin Docker restart, sin Milvus/LiteLLM, sin frontend.
- PostgreSQL (container `imotorsoft-postgres` en estado `exited`) no disponible
  en esta sesion. Migration 002, bootstrap admin y smoke backend quedan
  diferidos para cuando PostgreSQL este operativo.
- Commits separados: auth persistence (1) + auth routes (2).

### 2026-06-25 - Convencion de bitacora runtime backend + Astro

- Se formalizo que este archivo es la bitacora tecnica principal del runtime.
- Se agrego alcance explicito para backend, frontend Astro/Svelte e integracion
  frontend/backend.
- Se decidio no crear `backend/status_actual.md` ni `astro/status_actual.md`
  por ahora; se evaluara solo si el volumen tecnico lo justifica.
- Se actualizaron `AGENTS.md`, `.agents/skills/tebaai-project/SKILL.md` y
  `docs/templates/status_actual_template.md` con la convencion general de
  `status_actual.md`.
- No se modifico codigo runtime, dependencias, Docker, `.env`, migraciones ni
  servicios externos.

### 2026-06-24 - Upgrade frontend Astro 7 + Tailwind + DaisyUI

- `astro`: 6.4.2 -> 7.0.2
- `@astrojs/svelte`: 8.1.2 -> 9.0.0
- `svelte`: 5.56.0 -> 5.56.4
- `@playwright/test`: 1.60.0 -> 1.61.1
- `@types/node`: 26.0.0 -> 26.0.1
- Agregados: `tailwindcss` 4.3.1, `@tailwindcss/vite` 4.3.1, `daisyui` 5.5.23
- Creado `src/layouts/Layout.astro` (importa `src/assets/app.css`).
- Creado `src/assets/app.css` con `@import "tailwindcss"` y `@plugin "daisyui"`.
- `astro.config.mjs`: agregado plugin `@tailwindcss/vite`.
- `index.astro`: ahora usa `<Layout>` en vez de HTML directo.

### 2026-06-24 - Upgrade backend Python + librerias

- Python: 3.12.3 -> 3.12.13.
- Agregados: `psycopg` 3.3.4, `psycopg-binary` 3.3.4, `psycopg-pool` 3.3.1.
- Agregado: `pymilvus` 2.6.15 (compatible Milvus 2.6).
- Agregado: `litellm` 1.89.3 (SDK LiteLLM).

### 2026-06-24 - Agentes/Git

- AGENTS.md actualizado con convencion de ramas Git.
- Creadas y pusheadas ramas: `feature/console-backend-core`,
  `feature/knowledge-ingestion-service`, `docs/knowledge-documents-foundation`,
  `ux/team360-console-design-handoff`.

## Validacion

- `pytest`: 116 tests, todos PASS (84 existentes + 8 password + 8 tokens + 12
  service + 4 config auth).
- `git diff --check`: PASS.
- `python -c "import globalVar"`: PASS sin side effects.
- `python -c "from core.config import get_settings"`: PASS sin conexiones.
- Dependencias: `pydantic-settings==2.14.2`, `psycopg==3.3.4`,
  `psycopg-binary==3.3.4`, `psycopg-pool==3.3.1`, `argon2-cffi==25.1.0`,
  `PyJWT==2.13.0`. Sin SQLAlchemy, Alembic, ORM.
- `pnpm check`: 0 errors, 0 warnings (no changes).
- `pnpm build`: 1 page, daisyUI 5.5.23 (no changes).
- `uv sync`: PASS.

### 2026-06-28 - Frontend login minimo (global.js + auth UI)

- Revisado Team360 como referencia: `global.js` en `components/global.js` con
  exports individuales, objetos agrupados (ROUTES, BRAND), sin default export.
  Patron adoptado conceptualmente para TebaAI sin copiar datos Team360.
- Creada fachada publica frontend
  `SrvRestAstroLS_v1/astro/src/components/global.js`:
  APP_NAME, APP_PUBLIC_NAME, API_BASE_URL, DEFAULT_LOCALE, SUPPORTED_LOCALES,
  LOCALE_DIRECTION, DEFAULT_DIRECTION, AUTH_ENABLED, BRAND, ROUTES, API_ROUTES.
- Creado `global.d.ts` con tipos correspondientes.
- Creado `components/auth/authClient.ts`: login, getMe, refresh, logout,
  getStoredUser, isAuthenticated. SSR-safe (isBrowser guard). localStorage
  como almacenamiento transitorio documentado. Sin secretos ni tokens completos
  en logs. Sin password almacenado.
- Creado `components/auth/LoginForm.svelte`: Svelte 5 runes, email + password
  form, loading state, error alert, user info panel (email, role, username),
  button "Verificar sesion", "Cerrar sesion". DaisyUI classes.
- Creado `pages/login.astro`: pagina Astro que monta LoginForm con client:load
  y Layout base.
- Actualizado `index.astro`: agregado link de navegacion a /login.
- Agregado CORS al backend (`ls_iMotorSoft_Srv01.py`):
  `http://127.0.0.1:3008`, `http://localhost:3008` con allow_credentials=True.
- Creado `e2e/login.spec.ts`: 4 tests Playwright (form render, invalid error,
  login success, logout).
- Admin de prueba creado en DB: `admin@tebaai.ai` / `Admin123!`.
- Backend validado con PostgreSQL real: `/health` 200, `/ready` 200 (postgres up).
- Proxy Astro `/api` -> backend validado: login + me through proxy OK.
- CORS preflight + actual validado: headers correctos, 204/201.
- `pnpm check`: 0 errors, 0 warnings, 0 hints.
- `pnpm build`: 2 pages (/, /login) built, 1.65s.
- `pytest`: 116 passed, 35 warnings.
- Playwright E2E: 5 tests (1 home + 4 login), todos PASS, 4.8s.
- Sin secretos en diff, sin tokens completos, sin Team360, sin Milvus/LiteLLM.
- Sin Docker restart.

### 2026-06-28 - Refinamiento login frontend contra PostgreSQL 18 real

- `API_ROUTES` cambiado de paths con prefijo `/api/` (proxy Astro) a paths
  directos del backend (`/auth/login`, `/me`, etc.) para que el auth client
  construya URLs completas con `API_BASE_URL + API_ROUTES.*`.
- `authClient.ts` importa `API_BASE_URL` y construye URLs completas
  (`${BASE}${API_ROUTES.login}`) contra backend directo con CORS.
- `e2e/login.spec.ts`: credenciales via variables de entorno
  `TEBAAI_E2E_ADMIN_EMAIL` y `TEBAAI_E2E_ADMIN_PASSWORD` en vez de
  hardcodeadas. Fallback a `admin@tebaai.ai` / `Admin123!` solo para CI/dev.
- Validacion end-to-end completa contra PostgreSQL 18 real:
  migrations 001+002, usuario admin real con Argon2id, login/me/logout reales.
- 5 Playwright E2E tests PASS (4.0s), `pnpm check` 0 errors, `pnpm build` 1.44s,
  `pytest` 116 PASS.
- Sin secretos en diff, sin Team360, sin Docker restart, sin Milvus/LiteLLM.

### 2026-06-28 - Admin users UI mínimo

- Revisado Team360 como referencia de patrones: Svelte 5 runes, DaisyUI (table,
  card, badge, btn), Loading/EmptyState reutilizables, tabla con thead/tbody,
  status badges con variantes. Patron adoptado conceptualmente.
- Creado `components/auth/usersClient.ts`: listUsers, createUser, updateUser,
  activateUser, deactivateUser. Usa `API_BASE_URL + API_ROUTES.users` (ruta
  directa sin proxy). Tipos alineados con backend schemas.
- Creado `components/admin/UsersAdminPanel.svelte`: proteccion por sesion (login
  requerido), proteccion por role (solo admin), tabla con email/username/rol/
  estado/ultimo acceso/acciones, formulario crear usuario (email, username,
  password, role, is_active), edicion inline (username, role, is_active),
  activar/desactivar, loading/error/success feedback.
- Creado `pages/admin/users.astro`: pagina Astro con Layout + UsersAdminPanel
  con client:load.
- `LoginForm.svelte`: agregado link "Admin usuarios" visible solo para role
  admin.
- `authClient.ts`: exportados `getStoredAccessToken()` y `getStoredRefreshToken()`.
- Validacion contra PostgreSQL 18 real: list, create, activate, deactivate,
  patch usuarios verificados via backend.
- 9 Playwright E2E tests (5 login + 4 admin): todos PASS, 7.7s.
- `pnpm check`: 0 errors, 0 warnings, 0 hints.
- `pnpm build`: 3 pages (/, /login, /admin/users), 1.45s.
- `pytest`: 116 PASS.
- Sin secretos en diff, sin Team360, sin Docker restart, sin Milvus/LiteLLM.

### 2026-06-28 - Biblioteca/documentos base con CLI + PostgreSQL 18

- Revisada referencia Team360: `sync_v360_catalog_to_team360.py` con patrones
  de ingesta documental, CatalogDocument dataclass, chunking, argparse CLI.
  REUTILIZAR CONCEPTUALMENTE: estructura de servicio + repositorio + CLI.
  NO COPIAR: logica especifica de diagnostico Team360.
- Creada migracion `db/migrations/003_create_library_documents.sql` con 4 tablas:
  `library_collections`, `library_documents`, `library_document_texts`,
  `library_document_references`. Indices, checks, unique constraints.
- Migracion 003 aplicada en `tebaai`. Tablas verificadas con
  `information_schema.tables`.
- Creado `modules/library/domain.py`: enums (DocumentLanguage, DocumentSourceType,
  DocumentStatus, TextFormat, ExtractionMethod, RefType) y dataclasses
  (LibraryCollection, LibraryDocument, LibraryDocumentText,
  LibraryDocumentReference) con factories `.create()`.
- Creado `modules/library/schemas.py`: IngestDocumentRequest, IngestDocumentResult.
- Creado `modules/library/errors.py`: LibraryError, DocumentNotFoundError,
  DuplicateDocumentError, ExtractionError, UnsupportedFileTypeError, etc.
- Creado `modules/library/repository.py`: get_or_create_collection,
  get_document_by_sha256, get_document_by_id, create_document, list_documents,
  create_document_text, create_document_reference. JSONB serializado con
  `json.dumps()` para compatibilidad psycopg 3.
- Creado `modules/library/extractors.py`: extract_text para .md (raw_markdown),
  .txt (raw_text), .pdf (pymupdf4llm). compute_sha256, compute_file_sha256.
- Creado `modules/library/service.py`: ingest_document orquesta extraccion,
  hashing, creacion de coleccion, prevencion de duplicados, dry-run.
- Creado `scripts/ingest_document.py`: CLI con argparse, 7 argumentos requeridos
  + 9 opcionales, dry-run, resumen humano, deteccion de duplicados.
- Agregado `get_user_by_email` standalone en `modules/auth/repository.py` para
  uso cross-module desde library service.
- Agregado `pytest-asyncio` como dependencia dev, configurado `asyncio_mode=auto`.
- 24 tests unitarios para library (domain, extractors, schemas, repository,
  service, CLI). Todos PASS.
- Smoke CLI real contra PostgreSQL 18: carga `.md`, `.txt`, duplicate detection,
  dry-run, verificacion de texto en DB.
- No se toco Milvus, LiteLLM, Astro, frontend, admin UI, dashboard.
- Sin secretos en diff, sin Team360, sin Docker restart.

### 2026-06-28 - Chunking documental + embeddings + Milvus real

- Revisado Team360 como referencia de infraestructura: patron de chunking por
  parrafos, embeddings via OpenAI/LiteLLM. REUTILIZAR CONCEPTUALMENTE.
- Revisado JudaismoenVivo `markdown_milvus_v3.py` como referencia operativa
  fuerte: pymilvus, schema Milvus, COSINE metric, text-embedding-3-small.
  ADAPTAR: chunking propio, LiteLLM proxy, PostgreSQL como fuente de verdad.
- NO COPIAR: ArangoDB, chonkie, OpenAI directo, IVF_FLAT.
- Migracion 004 aplicada en `tebaai` (3 tablas).
- Infraestructura Milvus + embeddings + chunking + indexing service + CLIs.
- 3 PDFs Breslov cargados (1991 chunks, 1991 vectores indexados).
- Busqueda real PASS con queries relevantes.
- 83 tests PASS. Sin secretos.

## Pendientes recomendados

- Conectar backend con Milvus 2.6 (infrastructure/milvus/).
- Integrar LiteLLM para llamadas a modelos LLM.
- Reemplazar localStorage con cookies httpOnly para tokens.
- Agregar refresh automatico de tokens.
- Implementar dashboard principal.
- Chunking documental + preparacion Milvus.
- API HTTP minima para documentos.
- Definir primera vertical Breslov en fase posterior.
- Hardening de global.js.
- Agregar paginacion/busqueda a tabla de usuarios.
- Implementar OCR para PDFs escaneados.

## Notas de seguridad

- No se tocaron servicios externos.
- No se cargaron corpus reales.
- No se imprimieron ni leyeron secretos.
- Sin DSN real completo en diff.
- Sin valores TEAM360_ en TebaAI.
- Sin cambios a Team360.
- Sin operaciones destructivas.
- Sin Docker restart.
- Sin cambios Milvus/LiteLLM.
- Password oculto en DSN_DISPLAY via sanitize_dsn.
- SecretStr usado para passwords, tokens, API keys en core/config.py.
