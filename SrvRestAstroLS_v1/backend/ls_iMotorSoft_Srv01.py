from __future__ import annotations

from litestar import Litestar

from core.lifespan import on_shutdown, on_startup
from routes.health import health
from routes.ready import ready

app = Litestar(
    route_handlers=[health, ready],
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
)
