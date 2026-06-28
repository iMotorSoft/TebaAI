from __future__ import annotations

from litestar import Litestar
from litestar.config.cors import CORSConfig

from core.lifespan import on_shutdown, on_startup
from modules.auth.routes import (
    activate_user,
    create_user,
    deactivate_user,
    get_user,
    list_users,
    login,
    logout,
    me,
    patch_user,
    refresh,
)
from modules.library.routes import library_search
from routes.health import health
from routes.ready import ready

cors_config = CORSConfig(
    allow_origins=[
        "http://127.0.0.1:3008",
        "http://localhost:3008",
    ],
    allow_credentials=True,
)

app = Litestar(
    route_handlers=[
        health,
        ready,
        login,
        refresh,
        logout,
        me,
        list_users,
        create_user,
        get_user,
        patch_user,
        activate_user,
        deactivate_user,
        library_search,
    ],
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
    cors_config=cors_config,
)
