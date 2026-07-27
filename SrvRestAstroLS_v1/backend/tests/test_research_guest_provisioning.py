from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.auth.domain import User, UserRole
from scripts.provision_research_guest import normalize_email, provision_guest


def _user(role: UserRole = UserRole.VIEWER, *, active: bool = True) -> User:
    return User(
        id=uuid4(),
        email="guest@tebaai.live",
        username="private_beta_guest",
        password_hash="canonical-hash",
        role=role,
        is_active=active,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_normalize_email_is_case_insensitive() -> None:
    assert normalize_email(" Guest@TebaAI.Live ") == "guest@tebaai.live"


@pytest.mark.asyncio
async def test_creates_active_viewer_with_canonical_hasher() -> None:
    users = AsyncMock()
    users.get_by_email.return_value = None
    sessions = AsyncMock()
    with (
        patch("scripts.provision_research_guest.UserRepository", return_value=users),
        patch("scripts.provision_research_guest.AuthSessionRepository", return_value=sessions),
        patch("scripts.provision_research_guest.hash_password", return_value="argon2id-hash") as hasher,
    ):
        result = await provision_guest(
            AsyncMock(), email="Guest@TebaAI.Live", password="secret-from-environment"
        )

    assert result.status == "created"
    created = users.create.await_args.args[0]
    assert created.email == "guest@tebaai.live"
    assert created.role is UserRole.VIEWER
    assert created.is_active is True
    hasher.assert_called_once_with("secret-from-environment")
    sessions.revoke_for_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_correct_guest_is_idempotent() -> None:
    guest = _user()
    users = AsyncMock()
    users.get_by_email.return_value = guest
    with (
        patch("scripts.provision_research_guest.UserRepository", return_value=users),
        patch("scripts.provision_research_guest.AuthSessionRepository", return_value=AsyncMock()),
    ):
        result = await provision_guest(
            AsyncMock(), email=guest.email, password="unused-environment-secret"
        )

    assert result.status == "already_correct"
    users.update.assert_not_awaited()
    users.update_password_hash.assert_not_awaited()
    users.sync_membership_roles.assert_awaited_once_with(guest)


@pytest.mark.asyncio
async def test_elevated_existing_account_fails_closed() -> None:
    users = AsyncMock()
    users.get_by_email.return_value = _user(UserRole.ADMIN)
    with (
        patch("scripts.provision_research_guest.UserRepository", return_value=users),
        patch("scripts.provision_research_guest.AuthSessionRepository", return_value=AsyncMock()),
    ):
        with pytest.raises(PermissionError, match="elevated privileges"):
            await provision_guest(
                AsyncMock(), email="guest@tebaai.live", password="unused"
            )


@pytest.mark.asyncio
async def test_explicit_demotion_and_rotation_revoke_sessions() -> None:
    guest = _user(UserRole.EDITOR, active=False)
    users = AsyncMock()
    users.get_by_email.return_value = guest
    sessions = AsyncMock()
    with (
        patch("scripts.provision_research_guest.UserRepository", return_value=users),
        patch("scripts.provision_research_guest.AuthSessionRepository", return_value=sessions),
        patch("scripts.provision_research_guest.hash_password", return_value="new-hash"),
    ):
        result = await provision_guest(
            AsyncMock(),
            email=guest.email,
            password="secret-from-environment",
            rotate_password=True,
            allow_demotion=True,
        )

    assert result.status == "updated"
    assert guest.role is UserRole.VIEWER
    assert guest.is_active is True
    users.update.assert_awaited_once_with(guest)
    users.update_password_hash.assert_awaited_once_with(guest.id, "new-hash")
    sessions.revoke_for_user.assert_awaited_once_with(guest.id)
