from __future__ import annotations

from litestar import get

from globalVar import SERVICE_NAME, SERVICE_VERSION


@get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
    }
