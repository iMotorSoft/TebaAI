#! /usr/bin/env python3
"""
Create the initial admin user for TebaAI.

Usage:
    export TEBAAI_BOOTSTRAP_ADMIN_EMAIL=admin@tebaai.ai
    export TEBAAI_BOOTSTRAP_ADMIN_USERNAME=admin
    export TEBAAI_BOOTSTRAP_ADMIN_PASSWORD=<secure-password>
    uv run -- python scripts/create_admin_user.py

Requirements:
    - PostgreSQL must be running and accessible
    - TEBAAI_POSTGRES_ENABLED must be true
    - TEBAAI_BOOTSTRAP_ADMIN_EMAIL, _USERNAME, _PASSWORD must be set
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    email = os.environ.get("TEBAAI_BOOTSTRAP_ADMIN_EMAIL", "")
    username = os.environ.get("TEBAAI_BOOTSTRAP_ADMIN_USERNAME", "")
    password = os.environ.get("TEBAAI_BOOTSTRAP_ADMIN_PASSWORD", "")

    if not email or not password:
        print("ERROR: TEBAAI_BOOTSTRAP_ADMIN_EMAIL and TEBAAI_BOOTSTRAP_ADMIN_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    import asyncio

    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from modules.auth.domain import User, UserRole
    from modules.auth.password import hash_password
    from modules.auth.repository import UserRepository

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
        sys.exit(1)

    async def _run() -> int:
        pool = create_pool_from_settings()
        await open_pool(pool)
        try:
            async with pool.connection() as conn:
                cur = conn.cursor()
                await cur.execute("SELECT current_database()")
                row = await cur.fetchone()
                db_name = row[0] if row else "unknown"
                if db_name != "tebaai":
                    print(f"ERROR: Connected to '{db_name}' but expected 'tebaai'. Aborting.", file=sys.stderr)
                    return 1

                repo = UserRepository(conn)
                existing = await repo.get_by_email(email)
                if existing:
                    if existing.role != UserRole.ADMIN:
                        print(f"WARNING: User '{email}' exists with role '{existing.role.value}' (not admin)", file=sys.stderr)
                    else:
                        print(f"Admin user '{email}' already exists. Nothing to do.")
                    return 0

                pw_hash = hash_password(password)
                user = User.create(
                    email=email,
                    password_hash=pw_hash,
                    username=username or None,
                    role=UserRole.ADMIN,
                )
                await repo.create(user)
                print(f"Admin user '{email}' created successfully.")
                return 0
        finally:
            await close_pool(pool)

    exit_code = asyncio.run(_run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
