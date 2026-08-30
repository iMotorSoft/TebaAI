#!/usr/bin/env python3
"""Run one explicitly scoped durable Content Manager worker."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from globalVar import (
    CONTENT_MANAGER_E2E_ENABLED,
    CONTENT_MANAGER_E2E_SCOPE,
    CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED,
    CONTENT_MANAGER_WORKER_POLL_SECONDS,
    CONTENT_MANAGER_WORKER_SCOPE,
    TEBAAI_ENV,
)
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
from modules.library.content_manager_runtime import PsycopgWorkerStore
from modules.library.content_manager_worker import ContentManagerWorker
from modules.library.page_first_gateway import PostgresMilvusPageFirstGateway
from modules.library.page_first_pipeline import ConcretePageFirstPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tebaai.content-manager-worker")


async def main() -> None:
    if CONTENT_MANAGER_WORKER_SCOPE == CONTENT_MANAGER_E2E_SCOPE:
        if TEBAAI_ENV != "development" or not CONTENT_MANAGER_E2E_ENABLED:
            raise SystemExit("Isolated Content Manager worker requires explicit DEV E2E enablement")
    elif CONTENT_MANAGER_WORKER_SCOPE == "breslov_primary":
        if not CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED:
            raise SystemExit("Primary Content Manager ingestion requires explicit enablement")
    else:
        raise SystemExit("Unsupported Content Manager worker scope")
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    pool = create_pool_from_settings()
    await open_pool(pool)
    worker = ContentManagerWorker(
        worker_id=worker_id,
        store=PsycopgWorkerStore(pool, allowed_scope_code=CONTENT_MANAGER_WORKER_SCOPE),
        pipeline=ConcretePageFirstPipeline(PostgresMilvusPageFirstGateway(pool)),
    )
    logger.info("Worker active for scope %s", CONTENT_MANAGER_WORKER_SCOPE)
    try:
        while True:
            processed = await worker.run_once()
            if not processed:
                await asyncio.sleep(CONTENT_MANAGER_WORKER_POLL_SECONDS)
    finally:
        await close_pool(pool)


if __name__ == "__main__":
    asyncio.run(main())
