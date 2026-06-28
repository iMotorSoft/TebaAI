from __future__ import annotations

from litestar import Request, get

from globalVar import POSTGRES_DB, POSTGRES_ENABLED
from infrastructure.postgres.errors import DatabasePoolNotInitializedError
from infrastructure.postgres.pool import get_pool_from_state
from infrastructure.postgres.transaction import fetch_one


@get("/ready")
async def ready(request: Request) -> dict:
    if not POSTGRES_ENABLED:
        return {
            "status": "ready",
            "dependencies": {
                "postgres": {
                    "status": "not_configured",
                    "required": False,
                }
            },
        }

    try:
        pool = get_pool_from_state(request.app.state)
        async with pool.connection() as conn:
            row = await fetch_one(conn, "SELECT 1 AS ok")
            if row and row.get("ok") == 1:
                return {
                    "status": "ready",
                    "dependencies": {
                        "postgres": {
                            "status": "up",
                            "required": True,
                            "database": POSTGRES_DB,
                        }
                    },
                }
        return _down_response()
    except DatabasePoolNotInitializedError:
        return _down_response()
    except Exception:
        return _down_response()


def _down_response() -> dict:
    return {
        "status": "unavailable",
        "dependencies": {
            "postgres": {
                "status": "down",
                "required": True,
            }
        },
    }
