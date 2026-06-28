from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class User:
    id: UUID
    email: str
    username: str | None
    password_hash: str
    role: UserRole
    is_active: bool = True
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        email: str,
        password_hash: str,
        username: str | None = None,
        role: UserRole = UserRole.VIEWER,
    ) -> User:
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            email=email.strip().lower(),
            username=username.strip() if username else None,
            password_hash=password_hash,
            role=role,
            is_active=True,
            password_changed_at=now,
            created_at=now,
            updated_at=now,
        )


@dataclass
class AuthSession:
    id: UUID
    user_id: UUID
    refresh_token_hash: str
    token_family_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by_session_id: UUID | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = None

    @classmethod
    def create(
        cls,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        token_family_id: UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthSession:
        return cls(
            id=uuid4(),
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            token_family_id=token_family_id or uuid4(),
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
