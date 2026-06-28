from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from infrastructure.postgres.errors import DatabaseMigrationError

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "db" / "migrations"


async def ensure_schema_migrations_table(conn: AsyncConnection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     text        NOT NULL PRIMARY KEY,
            filename    text        NOT NULL,
            applied_at  timestamptz NOT NULL DEFAULT now(),
            checksum    text        NOT NULL DEFAULT ''
        )
        """
    )


async def get_applied_versions(conn: AsyncConnection) -> set[str]:
    versions: set[str] = set()
    async with conn.cursor() as cur:
        await cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        async for row in cur:
            versions.add(str(row["version"] if isinstance(row, dict) else row[0]))
    return versions


def _discover_migrations() -> list[tuple[str, str, str]]:
    if not MIGRATIONS_DIR.is_dir():
        return []
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    result: list[tuple[str, str, str]] = []
    for path in sql_files:
        version = path.stem.split("_", 1)[0]
        content = path.read_text(encoding="utf-8")
        result.append((version, path.name, content))
    return result


async def run_migrations(pool: AsyncConnectionPool) -> list[str]:
    applied: list[str] = []
    async with pool.connection() as conn:
        try:
            await ensure_schema_migrations_table(conn)
        except Exception as exc:
            raise DatabaseMigrationError(
                f"Failed to ensure schema_migrations table: {exc}"
            ) from exc
        existing = await get_applied_versions(conn)
        migrations = _discover_migrations()

        for version, filename, sql_content in migrations:
            if version in existing:
                continue
            async with conn.transaction():
                try:
                    await conn.execute(sql_content)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version, filename) "
                        "VALUES (%s, %s)",
                        (version, filename),
                    )
                except Exception as exc:
                    raise DatabaseMigrationError(
                        f"Migration {filename} (version={version}) failed: {exc}"
                    ) from exc
            applied.append(filename)
    return applied
