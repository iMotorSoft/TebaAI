from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from globalVar import (
    POSTGRES_CONNECT_TIMEOUT_SECONDS,
    POSTGRES_APPLICATION_NAME,
    POSTGRES_DSN,
    POSTGRES_MAX_POOL_SIZE,
    POSTGRES_MIN_POOL_SIZE,
)
from infrastructure.postgres.errors import (
    DatabaseConnectionError,
    DatabasePoolNotInitializedError,
)


def create_pool(
    dsn: str,
    min_size: int = 1,
    max_size: int = 10,
    timeout: int = 10,
    application_name: str = "tebaai-backend",
) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        conninfo=dsn,
        min_size=min_size,
        max_size=max_size,
        timeout=timeout,
        open=False,
        kwargs={
            "row_factory": dict_row,
            "application_name": application_name,
        },
    )


def create_pool_from_settings() -> AsyncConnectionPool:
    return create_pool(
        dsn=POSTGRES_DSN,
        min_size=POSTGRES_MIN_POOL_SIZE,
        max_size=POSTGRES_MAX_POOL_SIZE,
        timeout=POSTGRES_CONNECT_TIMEOUT_SECONDS,
        application_name=POSTGRES_APPLICATION_NAME,
    )


async def open_pool(pool: AsyncConnectionPool) -> None:
    try:
        await pool.open()
    except Exception as exc:
        raise DatabaseConnectionError(
            f"Failed to open database pool: {exc}"
        ) from exc


async def close_pool(pool: AsyncConnectionPool | None) -> None:
    if pool is None:
        return
    try:
        await pool.close()
    except Exception:
        pass


def get_pool_from_state(app_state: dict) -> AsyncConnectionPool:
    pool = app_state.get("pg_pool")
    if pool is None:
        raise DatabasePoolNotInitializedError(
            "PostgreSQL pool not initialized. "
            "Ensure lifecycle startup ran correctly."
        )
    return pool
