from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException

from modules.auth.dependencies import get_current_user_payload, require_current_roles
from modules.auth.domain import User, UserRole
from modules.auth.guards import require_roles


@asynccontextmanager
async def _transaction(_pool):
    yield AsyncMock()


def _request() -> MagicMock:
    request = MagicMock()
    request.headers = {"Authorization": "Bearer signed-token"}
    return request


def _user(role: UserRole = UserRole.VIEWER, *, active: bool = True) -> User:
    return User(
        id=uuid4(),
        email="guest@tebaai.live",
        username=None,
        password_hash="hash",
        role=role,
        is_active=active,
    )


@pytest.mark.asyncio
async def test_payload_rejects_inactive_user() -> None:
    user = _user(active=False)
    repo = AsyncMock()
    repo.get_by_id.return_value = user
    with (
        patch("modules.auth.dependencies.decode_access_token", return_value={"sub": str(user.id), "role": "viewer"}),
        patch("modules.auth.dependencies.get_pg_pool", new=AsyncMock(return_value=AsyncMock())),
        patch("modules.auth.dependencies.transaction", _transaction),
        patch("modules.auth.dependencies.UserRepository", return_value=repo),
    ):
        with pytest.raises(NotAuthorizedException, match="inactive"):
            await get_current_user_payload(_request())


@pytest.mark.asyncio
async def test_payload_rejects_stale_role_claim() -> None:
    user = _user(UserRole.VIEWER)
    repo = AsyncMock()
    repo.get_by_id.return_value = user
    with (
        patch("modules.auth.dependencies.decode_access_token", return_value={"sub": str(user.id), "role": "admin"}),
        patch("modules.auth.dependencies.get_pg_pool", new=AsyncMock(return_value=AsyncMock())),
        patch("modules.auth.dependencies.transaction", _transaction),
        patch("modules.auth.dependencies.UserRepository", return_value=repo),
    ):
        with pytest.raises(NotAuthorizedException, match="role"):
            await get_current_user_payload(_request())


@pytest.mark.asyncio
async def test_current_role_check_denies_viewer_admin_access() -> None:
    user = _user(UserRole.VIEWER)
    with patch(
        "modules.auth.dependencies.get_current_user_obj",
        new=AsyncMock(return_value={"user": user, "payload": {"role": "viewer"}}),
    ):
        with pytest.raises(PermissionDeniedException, match="permissions"):
            await require_current_roles(_request(), UserRole.ADMIN)


def test_admin_guard_denies_viewer_claim_before_handler() -> None:
    connection = MagicMock()
    connection.headers = {"Authorization": "Bearer viewer-token"}
    with patch(
        "modules.auth.tokens.decode_access_token",
        return_value={"sub": str(uuid4()), "role": "viewer"},
    ):
        with pytest.raises(PermissionDeniedException, match="permissions"):
            require_roles(UserRole.ADMIN)(connection, MagicMock())


def test_admin_guard_rejects_tampered_token() -> None:
    connection = MagicMock()
    connection.headers = {"Authorization": "Bearer tampered-token"}
    with patch(
        "modules.auth.tokens.decode_access_token",
        side_effect=ValueError("Invalid access token"),
    ):
        with pytest.raises(NotAuthorizedException, match="Invalid access token"):
            require_roles(UserRole.ADMIN)(connection, MagicMock())
