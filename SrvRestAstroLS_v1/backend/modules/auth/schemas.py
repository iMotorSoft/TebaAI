from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from modules.auth.domain import UserRole


# ── Request ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class CreateUserRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    username: str | None = Field(None, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    email: str | None = Field(None, min_length=1, max_length=255)
    username: str | None = Field(None, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None


# ── Response ──────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str | None
    role: UserRole
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
