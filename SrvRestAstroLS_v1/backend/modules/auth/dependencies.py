from __future__ import annotations

from uuid import UUID

from litestar import Request
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException

from core.dependencies import get_pg_pool
from infrastructure.postgres.transaction import transaction
from modules.auth.domain import UserRole
from modules.auth.repository import UserRepository
from modules.auth.tokens import decode_access_token


async def get_current_user_payload(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise NotAuthorizedException("Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise NotAuthorizedException(str(exc))

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthorizedException("Invalid authenticated subject") from exc
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        user = await UserRepository(conn).get_by_id(user_id)
    if not user or not user.is_active:
        raise NotAuthorizedException("User not found or inactive")
    if payload.get("role") != user.role.value:
        raise NotAuthorizedException("Session role is no longer valid")
    return payload


async def get_current_user_obj(request: Request) -> dict:
    pool = await get_pg_pool(request)
    payload = await get_current_user_payload(request)
    user_id = UUID(payload["sub"])
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise NotAuthorizedException("User not found or inactive")
    return {"user": user, "payload": payload}


async def require_current_roles(request: Request, *roles: UserRole) -> dict:
    current = await get_current_user_obj(request)
    if current["user"].role not in roles:
        raise PermissionDeniedException("Insufficient permissions")
    return current
