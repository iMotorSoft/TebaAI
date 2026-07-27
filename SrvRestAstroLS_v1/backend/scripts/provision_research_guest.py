"""Idempotently provision the private-beta research guest.

The password is resolved only through typed settings from
``TEBAAI_GUEST_PASSWORD``. It is never accepted on argv or printed.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import get_settings
from infrastructure.postgres.pool import (
    close_pool,
    create_pool_from_settings,
    open_pool,
)
from modules.auth.domain import User, UserRole
from modules.auth.password import hash_password
from modules.auth.repository import UserRepository
from modules.auth.session_repository import AuthSessionRepository


@dataclass(frozen=True)
class ProvisioningResult:
    status: str
    user_id: str


def normalize_email(raw_email: str) -> str:
    normalized = raw_email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise ValueError("Invalid guest email")
    return normalized


async def provision_guest(
    conn,
    *,
    email: str,
    password: str,
    rotate_password: bool = False,
    allow_demotion: bool = False,
) -> ProvisioningResult:
    normalized = normalize_email(email)
    users = UserRepository(conn)
    sessions = AuthSessionRepository(conn)
    existing = await users.get_by_email(normalized)

    if existing is None:
        user = User.create(
            email=normalized,
            password_hash=hash_password(password),
            username="private_beta_guest",
            role=UserRole.VIEWER,
        )
        await users.create(user)
        return ProvisioningResult("created", str(user.id))

    if existing.role in {UserRole.ADMIN, UserRole.EDITOR} and not allow_demotion:
        raise PermissionError(
            "Existing guest email has elevated privileges; rerun with --allow-demotion "
            "only after verifying the account identity"
        )

    changed = False
    security_changed = False
    if existing.email != normalized:
        existing.email = normalized
        changed = True
    if existing.role != UserRole.VIEWER:
        existing.role = UserRole.VIEWER
        changed = True
        security_changed = True
    if not existing.is_active:
        existing.is_active = True
        changed = True
    if changed:
        await users.update(existing)
    else:
        await users.sync_membership_roles(existing)

    if rotate_password:
        await users.update_password_hash(existing.id, hash_password(password))
        security_changed = True
    if security_changed:
        await sessions.revoke_for_user(existing.id)

    return ProvisioningResult(
        "updated" if changed or rotate_password else "already_correct",
        str(existing.id),
    )


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    password = settings.guest_password.get_secret_value()
    if not password:
        print("ERROR: TEBAAI_GUEST_PASSWORD must be set", file=sys.stderr)
        return 2
    if not settings.postgres_enabled:
        print("ERROR: PostgreSQL is not enabled", file=sys.stderr)
        return 2

    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute("SELECT current_database() AS name")
                    row = await cur.fetchone()
                    if not row or row["name"] != "tebaai":
                        raise RuntimeError("Provisioning requires the tebaai database")
                result = await provision_guest(
                    conn,
                    email=args.email,
                    password=password,
                    rotate_password=args.rotate_password,
                    allow_demotion=args.allow_demotion,
                )
        print(f"guest user {result.status}")
        return 0
    finally:
        await close_pool(pool)


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a read-only research guest")
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--rotate-password",
        action="store_true",
        help="Replace the password of an existing guest and revoke refresh sessions",
    )
    parser.add_argument(
        "--allow-demotion",
        action="store_true",
        help="Explicitly permit demotion of an existing admin/editor account",
    )
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(_run(args)))
    except (PermissionError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
