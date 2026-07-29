from __future__ import annotations

import logging

from litestar import Litestar

from globalVar import (
    POSTGRES_AUTO_MIGRATE,
    POSTGRES_ENABLED,
    get_tebaai_config_summary,
)
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
from infrastructure.postgres.migrations import run_migrations

logger = logging.getLogger(__name__)


async def on_startup(app: Litestar) -> None:
    logger.info("TebaAI configuration: %s", get_tebaai_config_summary())
    if not POSTGRES_ENABLED:
        return

    pool = create_pool_from_settings()
    await open_pool(pool)

    async with pool.connection() as conn:
        row = await conn.execute("SELECT 1")
        assert row is not None

    if POSTGRES_AUTO_MIGRATE:
        await run_migrations(pool)

    app.state.pg_pool = pool


async def on_shutdown(app: Litestar) -> None:
    pool = getattr(app.state, "pg_pool", None)
    await close_pool(pool)
