from __future__ import annotations

from datetime import datetime
from uuid import UUID

from psycopg import AsyncConnection

from modules.auth.domain import User, UserRole
from infrastructure.postgres.transaction import execute, fetch_all, fetch_one


class TenantContextConfigurationError(RuntimeError):
    """The data-configured default tenant context is missing or ambiguous."""


class UserRepository:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def create(self, user: User) -> User:
        await execute(
            self._conn,
            """
            INSERT INTO users (id, email, email_normalized, username, password_hash, role, is_active,
                               password_changed_at, created_at, updated_at)
            VALUES (%(id)s, %(email)s, %(email_normalized)s, %(username)s, %(password_hash)s, %(role)s, %(is_active)s, %(password_changed_at)s, %(created_at)s, %(updated_at)s)
            """,
            {
                "id": str(user.id),
                "email": user.email,
                "email_normalized": user.email.strip().lower(),
                "username": user.username,
                "password_hash": user.password_hash,
                "role": user.role.value,
                "is_active": user.is_active,
                "password_changed_at": user.password_changed_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            },
        )
        await self._assign_default_tenant_memberships(user)
        return user

    async def _assign_default_tenant_memberships(self, user: User) -> None:
        """Assign new users to the data-configured default tenant context."""
        context = await fetch_one(
            self._conn,
            """
            WITH candidates AS (
                SELECT o.id AS organization_id, w.id AS workspace_id, p.id AS project_id
                FROM organizations o
                JOIN workspaces w
                  ON w.organization_id = o.id
                JOIN projects p
                  ON p.workspace_id = w.id
                 AND p.organization_id = o.id
                WHERE p.metadata @> '{"default_user_context": true}'::jsonb
                  AND o.status = 'active'
                  AND w.status = 'active'
                  AND p.status = 'active'
            )
            SELECT organization_id, workspace_id, project_id
            FROM candidates
            WHERE (SELECT count(*) FROM candidates) = 1
            """,
        )
        if context is None:
            raise TenantContextConfigurationError(
                "Exactly one active default tenant context is required"
            )

        membership_role = {
            UserRole.ADMIN: "admin",
            UserRole.EDITOR: "member",
            UserRole.VIEWER: "viewer",
        }[user.role]
        params = {
            "user_id": str(user.id),
            "membership_role": membership_role,
            **context,
        }
        await execute(
            self._conn,
            """
            INSERT INTO organization_members (organization_id, user_id, role, status)
            VALUES (%(organization_id)s, %(user_id)s, %(membership_role)s::member_role, 'active')
            ON CONFLICT (organization_id, user_id) DO NOTHING
            """,
            params,
        )
        await execute(
            self._conn,
            """
            INSERT INTO workspace_members (workspace_id, user_id, role, status)
            VALUES (%(workspace_id)s, %(user_id)s, %(membership_role)s::member_role, 'active')
            ON CONFLICT (workspace_id, user_id) DO NOTHING
            """,
            params,
        )
        await execute(
            self._conn,
            """
            INSERT INTO project_members (project_id, user_id, role, status)
            VALUES (%(project_id)s, %(user_id)s, %(membership_role)s::member_role, 'active')
            ON CONFLICT (project_id, user_id) DO NOTHING
            """,
            params,
        )

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await fetch_one(
            self._conn,
            "SELECT * FROM users WHERE id = %(id)s",
            {"id": str(user_id)},
        )
        return _row_to_user(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        row = await fetch_one(
            self._conn,
            "SELECT * FROM users WHERE lower(email) = lower(%(email)s)",
            {"email": email},
        )
        return _row_to_user(row) if row else None

    async def list(self, offset: int = 0, limit: int = 100) -> tuple[list[User], int]:
        rows = await fetch_all(
            self._conn,
            "SELECT * FROM users ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s",
            {"limit": limit, "offset": offset},
        )
        total_row = await fetch_one(
            self._conn,
            "SELECT count(*) AS cnt FROM users",
        )
        total = total_row["cnt"] if total_row else 0
        return [_row_to_user(r) for r in rows], total

    async def update(self, user: User) -> User:
        await execute(
            self._conn,
            """
            UPDATE users SET email = %(email)s, username = %(username)s, role = %(role)s, is_active = %(is_active)s,
                             updated_at = %(updated_at)s
            WHERE id = %(id)s
            """,
            {
                "email": user.email,
                "username": user.username,
                "role": user.role.value,
                "is_active": user.is_active,
                "updated_at": user.updated_at,
                "id": str(user.id),
            },
        )
        return user

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        now = datetime.utcnow()
        await execute(
            self._conn,
            "UPDATE users SET password_hash = %(password_hash)s, password_changed_at = %(password_changed_at)s, updated_at = %(updated_at)s WHERE id = %(id)s",
            {
                "password_hash": password_hash,
                "password_changed_at": now,
                "updated_at": now,
                "id": str(user_id),
            },
        )

    async def set_last_login(self, user_id: UUID) -> None:
        now = datetime.utcnow()
        await execute(
            self._conn,
            "UPDATE users SET last_login_at = %(last_login_at)s, updated_at = %(updated_at)s WHERE id = %(id)s",
            {"last_login_at": now, "updated_at": now, "id": str(user_id)},
        )


def _row_to_user(row: dict) -> User:
    return User(
        id=UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
        email=row["email"],
        username=row.get("username"),
        password_hash=row["password_hash"],
        role=UserRole(row["role"]),
        is_active=row["is_active"],
        last_login_at=row.get("last_login_at"),
        password_changed_at=row.get("password_changed_at"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


# ── Standalone helpers for cross-module use ─────────────────────────────


async def get_user_by_email(conn: AsyncConnection, email: str) -> User | None:
    """Look up a user by email (case-insensitive)."""
    row = await fetch_one(
        conn,
        "SELECT * FROM users WHERE lower(email) = lower(%(email)s)",
        {"email": email},
    )
    return _row_to_user(row) if row else None
