# TebaAI — globalVar PostgreSQL Config Policy

Estado: accepted.
Fecha: 2026-06-30.

## Contexto

TebaAI sigue la convención iMotorSoft: `globalVar.py` como fachada única de configuración.
PostgreSQL se resuelve desde variables `DB_PG_*` estándar del entorno local.

## Fuente de configuración

| Variable | Propósito | Default |
|----------|-----------|---------|
| `DB_PG_IP` | Host PostgreSQL | `127.0.0.1` |
| `DB_PG_PORT` | Puerto PostgreSQL | `5432` |
| `DB_PG_USER` | Usuario PostgreSQL | — |
| `DB_PG_PASS` | Password PostgreSQL | — |

La base de datos del proyecto TebaAI es siempre `tebaai`.

## Reglas de resolución

1. `globalVar.py` expone `POSTGRES_ENABLED`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_DSN`, `POSTGRES_DSN_DISPLAY` y demás constantes PostgreSQL.
2. La resolución ocurre en `core/config.py` vía `AppSettings._validate_postgres()`.
3. Si `TEBAAI_POSTGRES_*` están definidas, tienen prioridad (override explícito).
4. Si no hay `TEBAAI_POSTGRES_*`, se intenta resolver desde `DB_PG_*`.
5. Si `DB_PG_USER` y `DB_PG_PASS` están presentes, `postgres_enabled=True` y se construye DSN con db=`tebaai`.
6. Si no hay credenciales disponibles, `postgres_enabled=False`.
7. Ningún script de library lee variables de entorno directamente.

## Seguridad

- `core/config.py` es la única fuente que lee variables de entorno.
- `POSTGRES_DSN_DISPLAY` tiene el password sanitizado.
- No se imprimen passwords ni DSN completos.
- Los secretos se representan como `SecretStr`.

## Scripts

Todos los scripts de library usan `from core.config import get_settings` y resuelven el pool vía `infrastructure/postgres/pool.py` que importa `POSTGRES_DSN` desde `globalVar`.

## Tests

- `test_globalvar_postgres_config.py` (12 tests) cubre DB_PG_* resolution, defaults, override y sanitización.
- `test_global_var.py` cubre la fachada `globalVar.py`.

## Servicios permanentes

PostgreSQL es un servicio permanente. No iniciar, detener, reiniciar ni migrar sin instrucción explícita.
