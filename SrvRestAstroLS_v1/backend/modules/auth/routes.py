from __future__ import annotations

from datetime import datetime as dt
from uuid import UUID

from litestar import Request, get, patch, post
from litestar.exceptions import HTTPException, NotAuthorizedException

from core.dependencies import get_pg_pool
from infrastructure.postgres.transaction import transaction
from modules.auth.domain import User, UserRole
from modules.auth.guards import require_roles
from modules.auth.password import hash_password
from modules.auth.repository import UserRepository
from modules.auth.schemas import (
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from modules.auth.service import AuthService
from modules.auth.session_repository import AuthSessionRepository
from modules.auth.tokens import decode_access_token


async def _get_user_id(request: Request) -> UUID:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise NotAuthorizedException("Missing or invalid Authorization header")
    token = auth.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise NotAuthorizedException(str(exc))
    return UUID(payload["sub"])


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


@post("/auth/login")
async def login(request: Request, data: LoginRequest) -> LoginResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        service = AuthService(
            user_repo=UserRepository(conn),
            session_repo=AuthSessionRepository(conn),
        )
        try:
            result = await service.login(
                email=data.email,
                password=data.password,
                user_agent=request.headers.get("user-agent"),
                ip_address=request.client.host if request.client else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
    return result


@post("/auth/refresh")
async def refresh(request: Request, data: RefreshRequest) -> TokenResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        service = AuthService(
            user_repo=UserRepository(conn),
            session_repo=AuthSessionRepository(conn),
        )
        try:
            result = await service.refresh(data.refresh_token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
    return result


@post("/auth/logout")
async def logout(request: Request, data: LogoutRequest) -> dict:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        service = AuthService(
            user_repo=UserRepository(conn),
            session_repo=AuthSessionRepository(conn),
        )
        await service.logout(data.refresh_token)
    return {"status": "ok"}


@get("/auth/me")
async def me(request: Request) -> UserResponse:
    user_id = await _get_user_id(request)
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        user = await repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
    return _user_to_response(user)


@get("/users", guards=[require_roles(UserRole.ADMIN)])
async def list_users(request: Request) -> UserListResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        users, total = await repo.list()
    return UserListResponse(
        items=[_user_to_response(u) for u in users],
        total=total,
    )


@post("/users", guards=[require_roles(UserRole.ADMIN)])
async def create_user(request: Request, data: CreateUserRequest) -> UserResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        existing = await repo.get_by_email(data.email)
        if existing:
            raise HTTPException(status_code=409, detail="A user with this email already exists")

        pw_hash = hash_password(data.password)
        user = User.create(
            email=data.email,
            password_hash=pw_hash,
            username=data.username,
            role=data.role,
        )
        if not data.is_active:
            user.is_active = False
        await repo.create(user)
    return _user_to_response(user)


@get("/users/{user_id:str}", guards=[require_roles(UserRole.ADMIN)])
async def get_user(request: Request, user_id: str) -> UserResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        user = await repo.get_by_id(UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    return _user_to_response(user)


@patch("/users/{user_id:str}", guards=[require_roles(UserRole.ADMIN)])
async def patch_user(request: Request, user_id: str, data: UpdateUserRequest) -> UserResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        user = await repo.get_by_id(UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if data.email is not None:
            user.email = data.email.strip().lower()
        if data.username is not None:
            user.username = data.username.strip() if data.username else None
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        user.updated_at = dt.utcnow()
        await repo.update(user)
    return _user_to_response(user)


@post("/users/{user_id:str}/activate", guards=[require_roles(UserRole.ADMIN)])
async def activate_user(request: Request, user_id: str) -> UserResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        user = await repo.get_by_id(UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_active = True
        user.updated_at = dt.utcnow()
        await repo.update(user)
    return _user_to_response(user)


@post("/users/{user_id:str}/deactivate", guards=[require_roles(UserRole.ADMIN)])
async def deactivate_user(request: Request, user_id: str) -> UserResponse:
    pool = await get_pg_pool(request)
    async with transaction(pool) as conn:
        repo = UserRepository(conn)
        user = await repo.get_by_id(UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_active = False
        user.updated_at = dt.utcnow()
        await repo.update(user)
    return _user_to_response(user)
