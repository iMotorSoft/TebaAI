# TebaAI - Instrucciones para agentes

Este archivo es la fuente operativa canonica para agentes que trabajen en TebaAI. Las politicas extensas se consultan solo cuando la tarea las necesita.

## Inicio obligatorio

1. Trabajar desde `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI`.
2. Ejecutar `git branch --show-current` y `git status --short`.
3. Leer `SrvRestAstroLS_v1/docs/status_actual.md`.
4. Para cambios de arquitectura, leer `lat.md/lat.md`, `lat.md/status_actual.md` y el documento canonico relevante.
5. No cambiar de rama ni pisar cambios existentes.
6. Un solo agente puede escribir sobre un worktree.

No hacer commit, push, merge, rebase, reset, clean, stash, checkout forzado ni borrar ramas salvo pedido explicito del usuario.

## Identidad y stack

- marca visible: `Teba AI`;
- identificador tecnico: `tebaai`;
- variables de entorno: prefijo `TEBAAI_`;
- backend: Litestar en `127.0.0.1:7008`;
- entrypoint: `SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py`;
- objeto ASGI: `app`;
- frontend: Astro 7 + Svelte 5 en `127.0.0.1:3008`;
- PostgreSQL 18: verdad persistente;
- Milvus 2.6: indice vectorial derivado;
- LiteLLM: gateway de embeddings y futuras llamadas generativas.

No crear `SrvRestAstroLS_v1/backend/app.py` sin un ADR que apruebe la excepcion.

## Ramas

| Rama | Responsabilidad |
| --- | --- |
| `main` | Snapshot estable; no desarrollar directamente salvo hotfix explicito. |
| `feature/console-backend-core` | Backend, frontend, auth, biblioteca, runtime e integracion. |
| `feature/knowledge-ingestion-service` | Ingestion, chunking, embeddings, retrieval y evaluacion. |
| `docs/knowledge-documents-foundation` | Estandares, contenido curado y documentacion de knowledge. |

`desarrollo`, `dev` y `backend` corresponden a `feature/console-backend-core`.

La rama heredada `ux/team360-console-design-handoff` tiene un nombre ajeno a TebaAI y no es canonica. No usarla ni replicar nombres `team360_*` en nuevas ramas.

## Contexto por tarea

| Tarea | Referencia obligatoria |
| --- | --- |
| Arquitectura general | `lat.md/lat.md` y `lat.md/tebaai-knowledge-map.md` |
| Configuracion, secretos o variables | `lat.md/global-configuration-facade-policy.md` |
| PostgreSQL | `lat.md/postgres-driver-policy.md` |
| Auth, tokens o roles | `lat.md/authentication-security-policy.md` |
| Biblioteca y retrieval | `lat.md/library-retrieval-models-policy.md` |
| Servicios reales o benchmarks | `lat.md/service-preflight-methodology.md` |
| Browser QA o E2E | `lat.md/browser-mcp-validation-policy.md` |
| Bugs no triviales | `lat.md/root-cause-debugging-policy.md` |
| Diagramas | `lat.md/mermaid-diagram-policy.md` |

## Limites de implementacion

- Hacer cambios pequenos y limitados al objetivo.
- PostgreSQL es la fuente de verdad; Milvus es derivado.
- No iniciar, detener, reiniciar, migrar ni reconfigurar PostgreSQL, Milvus o LiteLLM sin instruccion explicita.
- Usar `psycopg 3 async`; mantener SQL en repositories.
- No introducir ORM sin ADR.
- Solo `core/config.py` puede leer variables de entorno del backend.
- `globalVar.py` es una fachada sin conexiones ni efectos secundarios.
- Toda configuracion PostgreSQL se resuelve via `backend/globalVar.py` desde `DB_PG_*` + base `tebaai`. Los scripts no deben leer variables PostgreSQL de forma dispersa.
- `global.js` contiene solo configuracion publica y nunca secretos.
- No hardcodear credenciales, tokens, passwords, API keys ni credenciales E2E.
- No introducir logica Breslov en modulos genericos cuando pueda expresarse como datos, colecciones o configuracion.

## Validacion

Ejecutar siempre:

- `git diff --check`;
- tests focalizados del modulo afectado;
- revision del diff final;
- `lat check` si cambia `lat.md/` o una referencia `@lat`.

Segun el cambio:

- backend: `cd SrvRestAstroLS_v1/backend && uv run pytest <paths>`;
- frontend: `cd SrvRestAstroLS_v1/astro && pnpm check`;
- build o paginas: agregar `pnpm build`;
- E2E autenticado: proporcionar `TEBAAI_E2E_ADMIN_EMAIL` y `TEBAAI_E2E_ADMIN_PASSWORD` desde el entorno;
- servicios reales: ejecutar preflight y comprobar que no exista fallback silencioso.

Playwright + Chromium es el gate E2E. Browser MCP es exploratorio y no reemplaza una regresion reproducible.

## Documentacion

- `SrvRestAstroLS_v1/docs/status_actual.md`: estado tecnico vigente y compacto.
- `SrvRestAstroLS_v1/docs/status_historico_hasta_2026-06-28.md`: historia tecnica congelada.
- `lat.md/`: invariantes, contratos y decisiones estables.
- `docs/adr/`: decisiones arquitectonicas con contexto y consecuencias.
- `data/reports/`: evidencia y resultados generados.

No duplicar decisiones largas en status. Enlazar a la fuente canonica.

## Cierre

Reportar rama, archivos modificados, validaciones, impacto, riesgos y proximo paso.
