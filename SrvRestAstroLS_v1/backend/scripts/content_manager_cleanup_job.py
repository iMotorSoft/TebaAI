#!/usr/bin/env python3
"""Exact manifest cleanup for Content Manager jobs.

Compensates the resources of one job/attempt via the official
ManifestCleanupService (Milvus-first, idempotent, audit-logged). Only known
E2E or primary scope/collection mappings are accepted.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from globalVar import (
    CONTENT_MANAGER_E2E_ENABLED,
    CONTENT_MANAGER_E2E_SCOPE,
    CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED,
    TEBAAI_ENV,
)
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
from modules.library.content_manager_cleanup import ManifestCleanupService


async def cleanup(job_id: str, attempt: int, *, second_run: bool = False) -> dict:
    if TEBAAI_ENV != "development":
        raise SystemExit("Content Manager cleanup is DEV-only")
    if not CONTENT_MANAGER_E2E_ENABLED and not CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED:
        raise SystemExit("Content Manager cleanup requires explicit scope enablement")
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        service = ManifestCleanupService(pool)
        result = await service.cleanup(job_id, attempt, remove_temporary=True)
        return {
            "scope": CONTENT_MANAGER_E2E_SCOPE,
            "job_id": job_id,
            "attempt_number": attempt,
            "run": "second" if second_run else "first",
            "status": result.status,
            "items": [
                {"resource_type": i.resource_type, "resource_id": str(i.resource_id), "result": i.result}
                for i in result.items
            ],
        }
    finally:
        await close_pool(pool)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("attempt", type=int, nargs="?", default=1)
    parser.add_argument("--twice", action="store_true", help="run cleanup a second time (idempotency check)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    first = asyncio.run(cleanup(args.job_id, args.attempt))
    second = None
    if args.twice:
        second = asyncio.run(cleanup(args.job_id, args.attempt, second_run=True))

    if args.json:
        print(json.dumps({"first": first, "second": second}, ensure_ascii=False, indent=2))
    else:
        print(f"first={first['status']} job={first['job_id']} attempt={first['attempt_number']}")
        if second:
            print(f"second={second['status']}")


if __name__ == "__main__":
    main()
