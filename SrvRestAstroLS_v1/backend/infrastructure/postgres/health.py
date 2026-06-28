from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

from globalVar import POSTGRES_DB
from infrastructure.postgres.transaction import fetch_one


async def check_postgres_health(pool: AsyncConnectionPool) -> dict:
    """Return a health dict for PostgreSQL."""
    try:
        async with pool.connection() as conn:
            row = await fetch_one(conn, "SELECT 1 AS ok")
            if row is None or row.get("ok") != 1:
                return {
                    "status": "down",
                    "required": True,
                    "database": POSTGRES_DB,
                }
        return {
            "status": "up",
            "required": True,
            "database": POSTGRES_DB,
        }
    except Exception:
        return {
            "status": "down",
            "required": True,
            "database": POSTGRES_DB,
        }
