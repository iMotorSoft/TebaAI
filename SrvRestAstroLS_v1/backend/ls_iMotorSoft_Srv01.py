from __future__ import annotations

from litestar import Litestar, get


@get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "tebaai-backend",
    }


app = Litestar(route_handlers=[health])
