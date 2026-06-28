from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from modules.auth.domain import AuthSession, User, UserRole
from modules.auth.service import AuthService


@pytest.fixture
def mock_user_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_session_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_user_repo: MagicMock, mock_session_repo: MagicMock) -> AuthService:
    return AuthService(user_repo=mock_user_repo, session_repo=mock_session_repo)


@pytest.fixture
def example_user() -> User:
    return User(
        id=uuid4(),
        email="admin@tebaai.ai",
        username="admin",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$...",
        role=UserRole.ADMIN,
        is_active=True,
        last_login_at=None,
        password_changed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _run(coro):
    import asyncio
    return asyncio.run(coro)


class TestLogin:
    def test_success(self, service: AuthService, mock_user_repo: MagicMock, mock_session_repo: MagicMock, example_user: User) -> None:
        mock_user_repo.get_by_email = AsyncMock(return_value=example_user)
        mock_user_repo.set_last_login = AsyncMock()
        mock_session_repo.create = AsyncMock()

        with patch("modules.auth.service.verify_password", return_value=True), \
             patch("modules.auth.service.create_access_token", return_value="access-token"), \
             patch("modules.auth.service.generate_refresh_token", return_value=("raw-refresh", "hash-refresh")), \
             patch("modules.auth.service.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.auth_refresh_token_ttl_days = 30
            s.auth_access_token_ttl_minutes = 15

            result = _run(service.login("admin@tebaai.ai", "password"))

        assert result.access_token == "access-token"
        assert result.refresh_token == "raw-refresh"
        assert result.token_type == "bearer"
        assert result.expires_in == 900
        assert result.user.email == "admin@tebaai.ai"
        assert result.user.role == UserRole.ADMIN

    def test_wrong_password(self, service: AuthService, mock_user_repo: MagicMock, example_user: User) -> None:
        mock_user_repo.get_by_email = AsyncMock(return_value=example_user)

        with patch("modules.auth.service.verify_password", return_value=False):
            with pytest.raises(ValueError, match="Invalid email or password"):
                _run(service.login("admin@tebaai.ai", "wrong"))

    def test_nonexistent_user(self, service: AuthService, mock_user_repo: MagicMock) -> None:
        mock_user_repo.get_by_email = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Invalid email or password"):
            _run(service.login("nobody@tebaai.ai", "password"))

    def test_inactive_user(self, service: AuthService, mock_user_repo: MagicMock, example_user: User) -> None:
        example_user.is_active = False
        mock_user_repo.get_by_email = AsyncMock(return_value=example_user)

        with patch("modules.auth.service.verify_password", return_value=True):
            with pytest.raises(ValueError, match="Account is inactive"):
                _run(service.login("admin@tebaai.ai", "password"))


class TestRefresh:
    def test_success(self, service: AuthService, mock_user_repo: MagicMock, mock_session_repo: MagicMock, example_user: User) -> None:
        family_id = uuid4()
        session = AuthSession(
            id=uuid4(), user_id=example_user.id,
            refresh_token_hash="existing-hash",
            token_family_id=family_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        mock_session_repo.get_by_refresh_hash = AsyncMock(return_value=session)
        mock_session_repo.create = AsyncMock()
        mock_session_repo.revoke = AsyncMock()
        mock_session_repo.update_last_used = AsyncMock()
        mock_user_repo.get_by_id = AsyncMock(return_value=example_user)

        with patch("modules.auth.service.create_access_token", return_value="new-access"), \
             patch("modules.auth.service.generate_refresh_token", return_value=("new-raw", "new-hash")), \
             patch("modules.auth.service.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.auth_refresh_token_ttl_days = 30
            s.auth_access_token_ttl_minutes = 15

            result = _run(service.refresh("valid-refresh-token"))

        assert result.access_token == "new-access"
        assert result.refresh_token == "new-raw"
        mock_session_repo.revoke.assert_called_once()
        mock_session_repo.create.assert_called_once()

    def test_revoked_token(self, service: AuthService, mock_session_repo: MagicMock) -> None:
        session = AuthSession(
            id=uuid4(), user_id=uuid4(),
            refresh_token_hash="revoked-hash",
            token_family_id=uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            revoked_at=datetime.now(timezone.utc),
        )
        mock_session_repo.get_by_refresh_hash = AsyncMock(return_value=session)
        mock_session_repo.revoke_family = AsyncMock()

        with pytest.raises(ValueError, match="Refresh token has been revoked"):
            _run(service.refresh("revoked-token"))

        mock_session_repo.revoke_family.assert_called_once()

    def test_expired_token(self, service: AuthService, mock_session_repo: MagicMock, mock_user_repo: MagicMock) -> None:
        session = AuthSession(
            id=uuid4(), user_id=uuid4(),
            refresh_token_hash="expired-hash",
            token_family_id=uuid4(),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        mock_session_repo.get_by_refresh_hash = AsyncMock(return_value=session)
        mock_session_repo.revoke = AsyncMock()

        with pytest.raises(ValueError, match="Refresh token has expired"):
            _run(service.refresh("expired-token"))

    def test_user_inactive(self, service: AuthService, mock_user_repo: MagicMock, mock_session_repo: MagicMock, example_user: User) -> None:
        example_user.is_active = False
        session = AuthSession(
            id=uuid4(), user_id=example_user.id,
            refresh_token_hash="hash",
            token_family_id=uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        mock_session_repo.get_by_refresh_hash = AsyncMock(return_value=session)
        mock_session_repo.revoke = AsyncMock()
        mock_user_repo.get_by_id = AsyncMock(return_value=example_user)

        with pytest.raises(ValueError, match="User is inactive or not found"):
            _run(service.refresh("inactive-user-token"))


class TestLogout:
    def test_revokes_session(self, service: AuthService, mock_session_repo: MagicMock) -> None:
        session = AuthSession(
            id=uuid4(), user_id=uuid4(),
            refresh_token_hash="hash",
            token_family_id=uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        mock_session_repo.get_by_refresh_hash = AsyncMock(return_value=session)
        mock_session_repo.revoke = AsyncMock()

        _run(service.logout("valid-token"))
        mock_session_repo.revoke.assert_called_once_with(session.id)

    def test_idempotent(self, service: AuthService, mock_session_repo: MagicMock) -> None:
        mock_session_repo.get_by_refresh_hash = AsyncMock(return_value=None)
        _run(service.logout("unknown-token"))


class TestCreateUser:
    def test_creates_user(self, service: AuthService, mock_user_repo: MagicMock) -> None:
        mock_user_repo.get_by_email = AsyncMock(return_value=None)
        mock_user_repo.create = AsyncMock()

        with patch("modules.auth.service.hash_password", return_value="hashed-pw"), \
             patch("modules.auth.service.get_settings"):
            user = _run(service.create_user(
                email="new@tebaai.ai",
                password="secure-password-123",
                username="newuser",
                role=UserRole.EDITOR,
            ))

        assert user.email == "new@tebaai.ai"
        assert user.role == UserRole.EDITOR
        assert user.is_active is True
        assert user.username == "newuser"
        mock_user_repo.create.assert_called_once()

    def test_duplicate_email(self, service: AuthService, mock_user_repo: MagicMock, example_user: User) -> None:
        mock_user_repo.get_by_email = AsyncMock(return_value=example_user)

        with pytest.raises(ValueError, match="already exists"):
            _run(service.create_user(email="admin@tebaai.ai", password="pw"))


class TestGetCurrentUser:
    def test_returns_user(self, service: AuthService, mock_user_repo: MagicMock, example_user: User) -> None:
        mock_user_repo.get_by_id = AsyncMock(return_value=example_user)
        user = _run(service.get_current_user(example_user.id))
        assert user.id == example_user.id
        assert user.email == example_user.email

    def test_not_found(self, service: AuthService, mock_user_repo: MagicMock) -> None:
        mock_user_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="User not found"):
            _run(service.get_current_user(uuid4()))

    def test_inactive(self, service: AuthService, mock_user_repo: MagicMock, example_user: User) -> None:
        example_user.is_active = False
        mock_user_repo.get_by_id = AsyncMock(return_value=example_user)
        with pytest.raises(ValueError, match="User is inactive"):
            _run(service.get_current_user(example_user.id))
