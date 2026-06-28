from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from modules.auth.domain import AuthSession, User, UserRole
from modules.auth.password import hash_password, verify_password
from modules.auth.repository import UserRepository
from modules.auth.schemas import LoginResponse, TokenResponse, UserResponse
from modules.auth.session_repository import AuthSessionRepository
from modules.auth.tokens import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
)
from core.config import get_settings


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: AuthSessionRepository,
    ) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo

    async def login(
        self,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> LoginResponse:
        email = email.strip().lower()
        user = await self._user_repo.get_by_email(email)

        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is inactive")

        settings = get_settings()
        access_token = create_access_token(str(user.id), user.role.value)
        raw_refresh, refresh_hash = generate_refresh_token()
        refresh_ttl = timedelta(days=settings.auth_refresh_token_ttl_days)
        session = AuthSession.create(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            expires_at=datetime.now(timezone.utc) + refresh_ttl,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self._session_repo.create(session)
        await self._user_repo.set_last_login(user.id)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=settings.auth_access_token_ttl_minutes * 60,
            user=_user_to_response(user),
        )

    async def refresh(self, raw_refresh: str) -> TokenResponse:
        refresh_hash = _hash_refresh(raw_refresh)
        session = await self._session_repo.get_by_refresh_hash(refresh_hash)

        if not session:
            raise ValueError("Invalid refresh token")

        if session.revoked_at is not None:
            await self._session_repo.revoke_family(session.token_family_id)
            raise ValueError("Refresh token has been revoked")

        if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            await self._session_repo.revoke(session.id)
            raise ValueError("Refresh token has expired")

        user = await self._user_repo.get_by_id(session.user_id)
        if not user or not user.is_active:
            await self._session_repo.revoke(session.id)
            raise ValueError("User is inactive or not found")

        settings = get_settings()
        new_access = create_access_token(str(user.id), user.role.value)
        new_raw, new_hash = generate_refresh_token()
        refresh_ttl = timedelta(days=settings.auth_refresh_token_ttl_days)
        new_session = AuthSession.create(
            user_id=user.id,
            refresh_token_hash=new_hash,
            expires_at=datetime.now(timezone.utc) + refresh_ttl,
            token_family_id=session.token_family_id,
            user_agent=session.user_agent,
            ip_address=session.ip_address,
        )
        await self._session_repo.create(new_session)
        await self._session_repo.revoke(session.id, replaced_by=new_session.id)
        await self._session_repo.update_last_used(new_session.id)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_raw,
            expires_in=settings.auth_access_token_ttl_minutes * 60,
        )

    async def logout(self, raw_refresh: str) -> None:
        refresh_hash = _hash_refresh(raw_refresh)
        session = await self._session_repo.get_by_refresh_hash(refresh_hash)
        if session:
            await self._session_repo.revoke(session.id)

    async def get_current_user(self, user_id: UUID) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("User is inactive")
        return user

    async def create_user(
        self,
        email: str,
        password: str,
        username: str | None = None,
        role: UserRole = UserRole.VIEWER,
        is_active: bool = True,
    ) -> User:
        email = email.strip().lower()
        existing = await self._user_repo.get_by_email(email)
        if existing:
            raise ValueError("A user with this email already exists")

        pw_hash = hash_password(password)
        user = User.create(
            email=email,
            password_hash=pw_hash,
            username=username,
            role=role,
        )
        if not is_active:
            user.is_active = False
        await self._user_repo.create(user)
        return user

    async def list_users(self, offset: int = 0, limit: int = 100) -> tuple[list[User], int]:
        users, total = await self._user_repo.list(offset=offset, limit=limit)
        return users, total

    async def get_user(self, user_id: UUID) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        return user

    async def update_user(
        self,
        user_id: UUID,
        email: str | None = None,
        username: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if email is not None:
            user.email = email.strip().lower()
        if username is not None:
            user.username = username.strip() if username else None
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        user.updated_at = datetime.utcnow()
        await self._user_repo.update(user)
        return user


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _hash_refresh(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode()).hexdigest()
