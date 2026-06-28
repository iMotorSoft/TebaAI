from __future__ import annotations

from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler

from modules.auth.domain import UserRole


def require_auth(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    auth_header = connection.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise NotAuthorizedException("Missing or invalid Authorization header")


def require_roles(*roles: UserRole):
    def guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
        from modules.auth.tokens import decode_access_token

        auth_header = connection.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise NotAuthorizedException("Missing or invalid Authorization header")

        token = auth_header.removeprefix("Bearer ")
        try:
            payload = decode_access_token(token)
        except ValueError as exc:
            raise NotAuthorizedException(str(exc))

        user_role = payload.get("role", "")
        if user_role not in [r.value for r in roles]:
            raise NotAuthorizedException("Insufficient permissions")

    return guard
