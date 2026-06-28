from __future__ import annotations

from litestar import Request
from psycopg_pool import AsyncConnectionPool

from infrastructure.postgres.errors import DatabasePoolNotInitializedError


async def get_pg_pool(request: Request) -> AsyncConnectionPool:
    pool = getattr(request.app.state, "pg_pool", None)
    if pool is None:
        raise DatabasePoolNotInitializedError(
            "PostgreSQL pool is not available. "
            "Ensure the service is started with PostgreSQL enabled."
        )
    return pool
