from __future__ import annotations

from litestar import Litestar

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
from routes.health import health
from routes.ready import ready

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
    ],
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
)
