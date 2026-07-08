# Auditoría de adopción documental Team360 → TebaAI

Fecha: 2026-07-06. Alcance: documentación y contratos útiles para orientar implementación; no se copiaron runtime, datos ni decisiones de producto específicas de Team360.

## Método y Cobertura

Se inventariaron 270 archivos Markdown de Team360 frente a 74 de TebaAI, incluyendo 32 documentos LAT Team360 y 92 documentos de `docs/` más `SrvRestAstroLS_v1/docs/`.

La revisión profunda se concentró en fuentes canónicas y diseños con correspondencia real en el stack TebaAI. Documentación de clientes, reportes históricos, fixtures y skills de terceros se clasificó por inventario, sin importarla.

| Capacidad | Fuentes Team360 principales |
| --- | --- |
| documentación viva | `lat-documentation-policy.md`, `lat.md`, `status_actual.md` |
| scopes y retrieval | `knowledge-scope-contract.md`, `knowledge-rag-graphrag.md`, `knowledge_ingestion_multiscope_design_20260607.md` |
| IA | `ai-litellm.md`, `model-selection-routing.md`, `ai-diagnosis-rag-runtime.md` |
| tenant y permisos | `console-multi-organization.md`, `postgresql_002_rbac_packages_workers_knowledge_design.md` |
| frontend | `team360-frontend-ui-policy.md`, `team360-frontend-url-source-of-truth.md`, ADR-004/005 |
| PASETO | ADR v4.public, inventario, bootstrap token, verifier y plan de migración embed |
| operación | preflight, PostgreSQL driver, browser QA, debugging y Mermaid |

## Resultado

La comparación encontró cinco áreas reutilizables que faltaban o estaban subespecificadas en TebaAI, más PASETO como activo portable que debe conservarse sin sustituir JWT de forma inmediata.

| Área | Decisión | Destino TebaAI |
| --- | --- | --- |
| gobernanza Markdown/LAT | adoptar y adaptar | `lat.md/lat-documentation-policy.md` |
| contrato multi-scope | adoptar con PostgreSQL como autoridad | `lat.md/knowledge-scope-contract.md` |
| LiteLLM, adapters y routing | adoptar sin precios ni providers directos | `lat.md/ai-gateway-model-routing-policy.md` |
| multi-organización y autorización | adoptar como frontera previa a exposición multi-tenant | `lat.md/tenant-context-authorization-policy.md` |
| pnpm, UI wrappers y URLs | adoptar según Astro 7 y configuración TebaAI | `lat.md/frontend-implementation-policy.md` |
| PASETO v4.public | preservar como referencia portable y evaluar por ADR | `docs/paseto-v4-public-portability-assessment.md` |

## Ya Estaba Incorporado

TebaAI ya tenía versiones adaptadas de varias políticas Team360 y no necesita duplicarlas.

| Tema Team360 | Equivalente TebaAI | Evaluación |
| --- | --- | --- |
| service preflight | `service-preflight-methodology` | frontera correcta; ampliar cuando exista automatización de preflight |
| PostgreSQL driver | `postgres-driver-policy` | alineado con psycopg 3 async y repositories |
| browser validation | `browser-mcp-validation-policy` | Playwright es gate y Browser MCP exploratorio |
| root-cause debugging | `root-cause-debugging-policy` | conserva la cadena síntoma → regresión |
| Mermaid | `mermaid-diagram-policy` | fuente versionada, renders derivados |
| bootstrap/ADR/status templates | `docs/templates/`, `docs/adr/` | ya adaptados y deliberadamente compactos |
| frontend stack | runtime y `package.json` | pnpm, Svelte 5, Tailwind 4 y DaisyUI 5; Astro es 7, no 6 |

## Adoptado con Cambios Estructurales

El valor transferido se conserva, pero las fronteras se reescribieron para la arquitectura real de TebaAI.

### Knowledge

Team360 propone `KnowledgeScope → KnowledgeDocument → KnowledgeChunk → VectorEmbedding`, filtros obligatorios y revalidación del resultado vectorial. TebaAI adopta ese patrón sobre sus tablas existentes.

Se descartaron ArangoDB como autoridad, pgvector como fallback primario y colecciones físicas por cliente. En TebaAI PostgreSQL conserva texto y metadata, y Milvus sigue siendo índice derivado.

### IA

Se adoptaron adapters tipados, aliases, validación de salida estructurada, telemetría, fallback observable y separación entre interpretación del modelo y decisión de plataforma.

Se descartaron slugs y precios de modelos Team360, OpenAI directo, OpenRouter y reglas para automatización SAP/browser. TebaAI usa LiteLLM exclusivamente y evalúa aliases por capacidad.

### Multi-Tenancy

Team360 distingue organización, workspace, autorización backend y navegación contextual. Esto es aplicable porque la migración 009 de TebaAI ya creó organizaciones, workspaces, projects y memberships.

El contrato TebaAI explicita una brecha: tener tablas y foreign keys no equivale a aislamiento. La exposición multi-tenant queda bloqueada hasta implementar contexto efectivo, repositories scoped y pruebas negativas.

### Frontend

Se adoptaron pnpm único, lockfile canónico, configuración URL centralizada, sincronización de tipos y wrappers UI propios.

La regla se adaptó a `PUBLIC_TEBAAI_API_BASE_URL`, puertos 7008/3008 y Astro 7. Como la UI actual usa DaisyUI directamente, los wrappers serán incrementales y no una reescritura cosmética.

## PASETO como Activo Portable

PASETO v4.public es una incorporación nueva de Team360 que conviene mantener y preparar para otros proyectos.

Team360 aporta emisión/verificación Ed25519, `kid`, claims base, TTL y pruebas. Antes de extraerlo deben eliminarse identidad Team360, rutas Console y lectura directa de entorno; además debe cerrarse el hardening fail-closed y temporal detallado en la evaluación portable.

TebaAI ya tiene JWT access y refresh opaco con rotación. La adopción de PASETO se difiere hasta un ADR que defina caso de uso, compatibilidad, key rotation, revocación y regresiones de sesión. No se clasifica como descartado.

## Diferido con Criterio de Activación

Estas ideas son potencialmente útiles, pero documentarlas como decisión vigente hoy crearía arquitectura especulativa.

| Tema Team360 | Activador en TebaAI | Requisito previo |
| --- | --- | --- |
| PASETO en runtime | nuevo token portable o migración justificada de access auth | ADR, convivencia, rotación y revocación |
| GraphRAG | preguntas multi-hop con mejora medible frente a hybrid | ADR, dataset dorado y modelo de relaciones |
| assistant instances | más de una experiencia configurada sobre el mismo core | contrato de tenant, configuración y ownership |
| package workers | ejecución de herramientas o procesos externos | dominio de jobs, permisos, idempotencia y auditoría |
| HITL/MFA para acciones | TebaAI pueda ejecutar mutaciones sensibles | threat model, aprobación auditable y política de acciones |
| Console bootstrap contextual | UI multi-workspace | autorización tenant implementada y DTO server-side |
| Playwright MCP server | exploración MCP compartida | launcher versionado; Playwright CLI sigue siendo gate |
| deploy por rsync | exista destino y procedimiento TebaAI aprobado | política propia de backup, secrets, rollback y health |
| componentes embebibles | exista un caso de integración externa | origin, auth, versionado e integridad |

## Rechazado para TebaAI

Los siguientes elementos son específicos o incompatibles y no deben migrarse por semejanza superficial.

- identidad, rutas, ramas, puertos, dominios y variables `TEAM360_*`;
- ArangoDB como fuente del texto o grafo;
- pgvector como reemplazo actual de Milvus;
- Vera, Diagnosis, Packs, Workers, SAP B1, Mercado Libre y mensajería;
- autenticación HMAC específica del embed Team360;
- Astro 6 y toggles dev/pro particulares de Team360;
- aliases, providers, precios o fallbacks de modelos sin evaluación TebaAI;
- despliegues y rutas Nginx/rsync de `team360.live`.

## Brechas de Implementación Detectadas

La primera fase cerró varias brechas y dejó explícitas las que requieren migración real o trabajo posterior.

1. Implementado: contexto tenant y scope autorizado en `/library/search`, con migración 012 pendiente de aplicación real.
2. Implementado: eliminación del fallback Breslov hardcodeado en la ingesta genérica.
3. Pendiente: validar versión en rehidratación PostgreSQL↔Milvus.
4. Pendiente: encapsular llamadas generativas detrás de adapters tipados y registrar fallback efectivo.
5. Implementado: el validador LiteLLM no imprime ninguna parte de la API key.
6. Implementado: `HomePanel.svelte` consume `global.js`.
7. Pendiente incremental: wrappers UI para primitives repetidos.
8. Implementado para scope: pruebas negativas y cadena completa de memberships; faltan otras superficies multi-tenant futuras.
9. Implementado en TebaAI: primitive PASETO neutral y endurecido; queda decidir su empaquetado/backport.

## Orden Recomendado

La secuencia reduce riesgo de fuga de datos y evita construir generación sobre retrieval ambiguo.

1. Aplicar la migración 012 con autorización y ejecutar tests HTTP contra PostgreSQL real.
2. Integridad de versiones PostgreSQL↔Milvus y fallback explícito.
3. Adapter generativo, telemetría y evaluación real LiteLLM.
4. UX conversacional y wrappers UI.
5. Empaquetar o backportar el primitive PASETO; activarlo solo mediante ADR.
6. Recién después, evaluar assistant instances, GraphRAG o workers.
