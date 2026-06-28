from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from psycopg import AsyncConnection

from modules.auth.domain import AuthSession
from infrastructure.postgres.transaction import execute, fetch_all, fetch_one


class AuthSessionRepository:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def create(self, session: AuthSession) -> AuthSession:
        await execute(
            self._conn,
            """
            INSERT INTO auth_sessions (id, user_id, refresh_token_hash, token_family_id,
                                       expires_at, user_agent, ip_address)
            VALUES (%(id)s, %(user_id)s, %(refresh_token_hash)s, %(token_family_id)s, %(expires_at)s, %(user_agent)s, %(ip_address)s)
            """,
            {
                "id": str(session.id),
                "user_id": str(session.user_id),
                "refresh_token_hash": session.refresh_token_hash,
                "token_family_id": str(session.token_family_id),
                "expires_at": session.expires_at,
                "user_agent": session.user_agent,
                "ip_address": session.ip_address,
            },
        )
        return session

    async def get_by_refresh_hash(self, refresh_hash: str) -> AuthSession | None:
        row = await fetch_one(
            self._conn,
            "SELECT * FROM auth_sessions WHERE refresh_token_hash = %(refresh_token_hash)s",
            {"refresh_token_hash": refresh_hash},
        )
        return _row_to_session(row) if row else None

    async def revoke(self, session_id: UUID, replaced_by: UUID | None = None) -> None:
        now = datetime.now(timezone.utc)
        if replaced_by:
            await execute(
                self._conn,
                """
                UPDATE auth_sessions SET revoked_at = %(revoked_at)s, replaced_by_session_id = %(replaced_by_session_id)s
                WHERE id = %(id)s
                """,
                {
                    "revoked_at": now,
                    "replaced_by_session_id": str(replaced_by),
                    "id": str(session_id),
                },
            )
        else:
            await execute(
                self._conn,
                "UPDATE auth_sessions SET revoked_at = %(revoked_at)s WHERE id = %(id)s",
                {"revoked_at": now, "id": str(session_id)},
            )

    async def revoke_family(self, token_family_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        await execute(
            self._conn,
            "UPDATE auth_sessions SET revoked_at = %(revoked_at)s WHERE token_family_id = %(token_family_id)s AND revoked_at IS NULL",
            {"revoked_at": now, "token_family_id": str(token_family_id)},
        )

    async def get_active_by_family(self, token_family_id: UUID) -> AuthSession | None:
        row = await fetch_one(
            self._conn,
            """
            SELECT * FROM auth_sessions
            WHERE token_family_id = %(token_family_id)s AND revoked_at IS NULL AND expires_at > now()
            ORDER BY created_at DESC LIMIT 1
            """,
            {"token_family_id": str(token_family_id)},
        )
        return _row_to_session(row) if row else None

    async def update_last_used(self, session_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        await execute(
            self._conn,
            "UPDATE auth_sessions SET last_used_at = %(last_used_at)s WHERE id = %(id)s",
            {"last_used_at": now, "id": str(session_id)},
        )


def _row_to_session(row: dict) -> AuthSession:
    return AuthSession(
        id=row["id"] if isinstance(row["id"], UUID) else UUID(row["id"]),
        user_id=row["user_id"] if isinstance(row["user_id"], UUID) else UUID(row["user_id"]),
        refresh_token_hash=row["refresh_token_hash"],
        token_family_id=row["token_family_id"] if isinstance(row["token_family_id"], UUID) else UUID(row["token_family_id"]),
        expires_at=row["expires_at"],
        revoked_at=row.get("revoked_at"),
        replaced_by_session_id=row["replaced_by_session_id"] if isinstance(row.get("replaced_by_session_id"), UUID) else UUID(row["replaced_by_session_id"]) if row.get("replaced_by_session_id") else None,
        created_at=row.get("created_at"),
        last_used_at=row.get("last_used_at"),
        user_agent=row.get("user_agent"),
        ip_address=row.get("ip_address"),
    )
