# TebaAI — globalVar PostgreSQL Config Policy

Estado: accepted.

Fecha: 2026-07-28.

## Contexto

TebaAI usa una sola convención de configuración PostgreSQL en todos los
entornos.

`globalVar.py` es la fachada estable y `core/config.py` es la única capa que
lee variables de entorno. Cada servidor define valores distintos bajo los
mismos nombres.

## Fuente canónica

La conexión PostgreSQL se resuelve exclusivamente desde:

| Variable | Propósito | Default |
| --- | --- | --- |
| `DB_PG_IP` | Host PostgreSQL | obligatorio al configurar PostgreSQL |
| `DB_PG_PORT` | Puerto PostgreSQL | `5432` |
| `DB_PG_USER` | Usuario PostgreSQL | obligatorio |
| `DB_PG_PASS` | Password PostgreSQL | obligatorio, sin fallback |
| `TEBAAI_DB_NAME` | Base exclusiva de TebaAI | `tebaai` |

`TEBAAI_POSTGRES_HOST`, `TEBAAI_POSTGRES_DB`, `TEBAAI_POSTGRES_USER`,
`TEBAAI_POSTGRES_PASSWORD` y `TEBAAI_POSTGRES_DSN` ya no son fuentes de
conexión. Se evita así mantener dos configuraciones activas o aceptar un DSN
arbitrario.

La configuración operativa adicional usa:

- `TEBAAI_ENV`: `development`, `staging` o `production`; se normalizan también
  `dev`, `stg` y `prod`;
- `TEBAAI_AUTH_PEPPER`;
- `TEBAAI_JWT_SECRET`;
- `TEBAAI_POSTGRES_AUTO_MIGRATE`;
- `TEBAAI_E2E_GUEST_PASSWORD`.

`TEBAAI_AUTH_PASSWORD_PEPPER`, `TEBAAI_AUTH_JWT_SECRET` y
`TEBAAI_GUEST_PASSWORD` permanecen sólo como aliases transitorios de
compatibilidad para consumidores existentes.

## URLs derivadas

Las credenciales se codifican como componentes URL con escaping estricto. No
se concatenan valores sin codificar.

`globalVar.py` expone:

- `TEBAAI_DB_URL`: `postgresql+psycopg://...`, para SQLAlchemy con Psycopg 3;
- `TEBAAI_DB_URL_PSQL`: `postgresql://...`, para Psycopg, `psql`, `pg_dump` y
  `pg_restore`;
- `POSTGRES_DSN`: alias runtime de `TEBAAI_DB_URL_PSQL`, porque el backend usa
  directamente Psycopg 3;
- `POSTGRES_DSN_DISPLAY`: variante sanitizada sin password.

Helpers canónicos:

- `get_tebaai_db_url()`;
- `get_tebaai_db_url_psql()`;
- `get_tebaai_auth_pepper()`;
- `get_tebaai_jwt_secret()`;
- `is_tebaai_production()`;
- `get_tebaai_config_summary()`.

No se imprime ninguna URL operativa. Para herramientas CLI se obtiene la URL
desde el proceso y se entrega directamente al cliente, sin registrarla en
logs, historial ni documentación.

## Validación

La configuración falla temprano ante valores incompletos o inseguros.

- host, usuario y password son obligatorios cuando existe cualquier `DB_PG_*`;
- el puerto debe ser entero entre 1 y 65535;
- el nombre de base usa un identificador acotado y rechaza explícitamente
  `postgres`, `team360` y `v360`;
- no existe fallback hardcodeado de credenciales;
- un entorno inválido falla temprano;
- producción requiere `TEBAAI_JWT_SECRET`, rechaza valores débiles conocidos y
  exige `TEBAAI_POSTGRES_AUTO_MIGRATE=false`;
- un pepper vacío se conserva como decisión explícita compatible con hashes
  históricos; este gate no modifica hashes ni habilita pepper automáticamente.

## Seguridad y lifecycle

Los secretos se representan con `SecretStr`. El resumen de arranque informa
únicamente presencia, entorno, host configurado, puerto, base y estado de
auto-migración. Nunca contiene password, pepper, JWT, DSN ni parámetros
sensibles.

`globalVar.py` no crea conexiones ni pools. El pool Psycopg 3 permanece en el
lifecycle Litestar y consume `POSTGRES_DSN`.

PostgreSQL es un servicio permanente. No iniciar, detener, reiniciar,
reconfigurar ni migrar sin instrucción explícita.
