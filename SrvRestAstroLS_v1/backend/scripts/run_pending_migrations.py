"""Apply pending PostgreSQL migrations with the canonical runner (DEV only).

Usage (from SrvRestAstroLS_v1/backend):
    .venv/bin/python scripts/run_pending_migrations.py

It uses infrastructure.postgres.migrations.run_migrations, the same runner the
application lifespan uses. It never starts the application and never touches
Milvus, the worker or any content.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import globalVar as g
from infrastructure.postgres.migrations import run_migrations
from infrastructure.postgres.pool import create_pool_from_settings


async def main() -> None:
    if g.TEBAAI_ENV != "development" or g.is_tebaai_production():
        raise SystemExit("Refusing to migrate outside local development")
    pool = create_pool_from_settings()
    await pool.open(wait=True)
    try:
        applied = await run_migrations(pool)
    finally:
        await pool.close()
    print("MIGRATIONS_APPLIED", applied)


if __name__ == "__main__":
    asyncio.run(main())
