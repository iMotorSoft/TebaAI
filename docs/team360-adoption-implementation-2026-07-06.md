# Implementación de adopciones Team360 en TebaAI

Fecha: 2026-07-06. Esta fase implementa los primeros contratos priorizados por la auditoría Team360 → TebaAI sin modificar servicios externos ni activar PASETO en autenticación productiva.

## Seguridad Inmediata

El validador LiteLLM dejó de imprimir un prefijo de la API key y ahora informa únicamente si existe configuración.

`HomePanel.svelte` dejó de leer y duplicar la URL del backend; consume `API_BASE_URL` desde `global.js`, la fuente pública única del frontend.

## Scope y Tenant

`POST /library/search` ahora decodifica el access token y resuelve el scope mediante la cadena completa de memberships activa.

```text
user
  -> organization_members
  -> workspace_members
  -> project_members
  -> active knowledge_scope
```

La consulta valida coherencia organization/workspace/project, usuario activo y estados activos. Un scope inexistente o ajeno devuelve el mismo error genérico y nunca inicia retrieval.

La migración `012_backfill_default_tenant_memberships.sql` marca el proyecto bootstrap como contexto default y prepara memberships para usuarios existentes. Los usuarios nuevos resuelven ese contexto desde metadata, sin lógica Breslov en auth, y reciben la cadena dentro de la misma transacción.

La creación falla cerrada si no existe exactamente un contexto default activo; así no persiste usuarios aparentemente válidos pero sin autorización determinística.

La migración fue creada y validada estáticamente, pero no se aplicó sobre PostgreSQL porque esta fase no recibió autorización para operar el servicio real.

## Scope Canónico

La UI y el schema de búsqueda usan `breslov_primary` como scope canónico y el cliente TypeScript consume `knowledge_scope_code`.

La ingesta ya no contiene un fallback Breslov hardcodeado. Los aliases legacy se resuelven exclusivamente desde metadata read-only de `library_collections_legacy`; si no existe mapping, la operación falla explícitamente.

## PASETO Portable

Se agregó `modules/security/paseto_v4_public.py` como núcleo neutral sin entorno, HTTP, PostgreSQL, Console ni identidad TebaAI/Team360.

Incluye:

- emisión Ed25519 v4.public con `iss`, `aud`, `sub`, `typ`, `iat`, `exp`, `jti` y footer `kid`;
- verificación multi-`kid` con keyring inyectado;
- validación estricta de tipos, clock skew, expiración y UUID `jti`;
- protección de claims reservados;
- validación de coherencia private/public key;
- límites de token/footer y errores públicos sanitizados;
- configuración fail-closed para TTL, leeway, keys y keyring.

El módulo no está conectado a login, refresh ni guards. JWT access y refresh opaco siguen siendo el contrato productivo vigente.

## Validación

Las verificaciones focalizadas cubren seguridad, scope, memberships, PASETO y frontend.

| Gate | Resultado |
| --- | --- |
| pytest focalizado ampliado | 83 PASS |
| pytest backend completo | 596 PASS, 79 warnings conocidos |
| PASETO/scope/secret inicial | 14 PASS |
| `pnpm check` | PASS, 0 errores/warnings/hints |
| `pnpm build` | PASS, 4 páginas |
| servicios PostgreSQL/Milvus/LiteLLM | no tocados |

La suite conserva warnings conocidos por `datetime.utcnow()`; no fueron introducidos por esta fase.

## Activación Pendiente

El código queda listo, pero el enforcement real requiere que la migración 012 se aplique antes de desplegar o reiniciar el backend actualizado.

PASETO requiere un ADR separado y configuración tipada de key storage/rotation antes de conectarse a cualquier endpoint.
