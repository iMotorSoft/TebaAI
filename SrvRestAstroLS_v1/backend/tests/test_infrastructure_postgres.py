from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrastructure.postgres.errors import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseExecutionError,
    DatabaseMigrationError,
    DatabasePoolNotInitializedError,
)


def _mock_cursor() -> AsyncMock:
    """Create a mock psycopg async cursor.

    In psycopg 3, cursor.execute() and cursor.fetchone() are async methods.
    """
    cur = AsyncMock()
    cur.fetchone = AsyncMock()
    cur.fetchall = AsyncMock()
    cur.rowcount = None
    return cur


def _mock_conn(cursor: AsyncMock | None = None) -> MagicMock:
    """Create a mock AsyncConnection for psycopg 3.

    conn.cursor() is sync, returns an async context manager.
    """
    conn = MagicMock()
    if cursor is None:
        cursor = _mock_cursor()
    conn.cursor.return_value.__aenter__.return_value = cursor
    return conn


def _run(coro: Any) -> Any:
    import asyncio
    return asyncio.run(coro)


class TestErrors:
    def test_hierarchy(self) -> None:
        assert issubclass(DatabaseConfigurationError, DatabaseError)
        assert issubclass(DatabaseConnectionError, DatabaseError)
        assert issubclass(DatabasePoolNotInitializedError, DatabaseError)
        assert issubclass(DatabaseExecutionError, DatabaseError)
        assert issubclass(DatabaseMigrationError, DatabaseError)

    def test_instantiation(self) -> None:
        err = DatabaseError("test")
        assert str(err) == "test"


class TestPool:
    def test_create_pool_parameters(self) -> None:
        with patch("infrastructure.postgres.pool.AsyncConnectionPool") as mock_cls:
            from infrastructure.postgres.pool import create_pool

            create_pool(
                dsn="postgresql://u:p@h:5432/db",
                min_size=2,
                max_size=5,
                timeout=15,
                application_name="test-app",
            )

            mock_cls.assert_called_once()
            _, kwargs = mock_cls.call_args
            assert kwargs["conninfo"] == "postgresql://u:p@h:5432/db"
            assert kwargs["min_size"] == 2
            assert kwargs["max_size"] == 5
            assert kwargs["timeout"] == 15
            assert kwargs["open"] is False
            assert kwargs["kwargs"]["application_name"] == "test-app"

    def test_get_pool_from_state_missing(self) -> None:
        from infrastructure.postgres.pool import get_pool_from_state

        with pytest.raises(DatabasePoolNotInitializedError):
            get_pool_from_state({})

    def test_get_pool_from_state_ok(self) -> None:
        from infrastructure.postgres.pool import get_pool_from_state

        mock_pool = MagicMock()
        result = get_pool_from_state({"pg_pool": mock_pool})
        assert result is mock_pool


class TestTransaction:
    def test_fetch_one_returns_dict(self) -> None:
        from infrastructure.postgres.transaction import fetch_one

        cur = _mock_cursor()
        cur.fetchone = AsyncMock(return_value={"id": 1, "name": "test"})
        conn = _mock_conn(cur)

        result = _run(fetch_one(conn, "SELECT 1"))
        assert result == {"id": 1, "name": "test"}
        cur.execute.assert_called_once_with("SELECT 1", None)

    def test_fetch_one_none(self) -> None:
        from infrastructure.postgres.transaction import fetch_one

        cur = _mock_cursor()
        cur.fetchone = AsyncMock(return_value=None)
        conn = _mock_conn(cur)

        result = _run(fetch_one(conn, "SELECT 1"))
        assert result is None

    def test_fetch_one_raises_db_error(self) -> None:
        from infrastructure.postgres.transaction import DatabaseExecutionError, fetch_one

        cur = _mock_cursor()
        cur.execute = AsyncMock(side_effect=RuntimeError("query failed"))
        conn = _mock_conn(cur)

        with pytest.raises(DatabaseExecutionError):
            _run(fetch_one(conn, "SELECT 1"))

    def test_fetch_all_returns_list(self) -> None:
        from infrastructure.postgres.transaction import fetch_all

        cur = _mock_cursor()
        cur.fetchall = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        conn = _mock_conn(cur)

        result = _run(fetch_all(conn, "SELECT 1"))
        assert len(result) == 2

    def test_execute_returns_rowcount(self) -> None:
        from infrastructure.postgres.transaction import execute

        cur = _mock_cursor()
        cur.rowcount = 5
        conn = _mock_conn(cur)

        result = _run(execute(conn, "UPDATE t SET x=1"))
        assert result == 5

    def test_execute_raises_db_error(self) -> None:
        from infrastructure.postgres.transaction import DatabaseExecutionError, execute

        cur = _mock_cursor()
        cur.execute = AsyncMock(side_effect=RuntimeError("update failed"))
        conn = _mock_conn(cur)

        with pytest.raises(DatabaseExecutionError):
            _run(execute(conn, "UPDATE t SET x=1"))


class TestMigrationsPool:
    def test_get_pool_from_state_no_pool(self) -> None:
        from infrastructure.postgres.pool import get_pool_from_state

        with pytest.raises(DatabasePoolNotInitializedError):
            get_pool_from_state({})

    def test_get_pool_from_state_with_pool(self) -> None:
        from infrastructure.postgres.pool import get_pool_from_state

        mock_pool = MagicMock()
        result = get_pool_from_state({"pg_pool": mock_pool})
        assert result is mock_pool

    def test_create_pool_from_settings_calls_create_pool(self) -> None:
        with patch(
            "infrastructure.postgres.pool.create_pool"
        ) as mock_create, patch(
            "infrastructure.postgres.pool.POSTGRES_DSN", "pg://u:p@h:1/d"
        ), patch(
            "infrastructure.postgres.pool.POSTGRES_MIN_POOL_SIZE", 2
        ), patch(
            "infrastructure.postgres.pool.POSTGRES_MAX_POOL_SIZE", 8
        ):
            from infrastructure.postgres.pool import create_pool_from_settings

            pool = create_pool_from_settings()
            mock_create.assert_called_once_with(
                dsn="pg://u:p@h:1/d",
                min_size=2,
                max_size=8,
                timeout=10,
                application_name="tebaai-backend",
            )


class TestMigrations:
    def test_ensure_table_creates_schema_migrations(self) -> None:
        from infrastructure.postgres.migrations import ensure_schema_migrations_table

        conn = AsyncMock()
        _run(ensure_schema_migrations_table(conn))
        conn.execute.assert_called_once()
        call_sql = conn.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS schema_migrations" in call_sql

    def test_ensure_table_is_idempotent(self) -> None:
        from infrastructure.postgres.migrations import ensure_schema_migrations_table

        conn = AsyncMock()
        _run(ensure_schema_migrations_table(conn))
        _run(ensure_schema_migrations_table(conn))
        assert conn.execute.call_count == 2

    def _make_mock_conn(self, existing_versions: list[dict] | None = None) -> MagicMock:
        conn = MagicMock()
        conn.execute = AsyncMock()
        cur = MagicMock()
        cur.execute = AsyncMock()
        cur.__aiter__.return_value = iter(existing_versions or [])
        conn.cursor.return_value.__aenter__.return_value = cur
        return conn

    def test_run_migrations_applies_pending(self) -> None:
        from infrastructure.postgres.migrations import run_migrations

        conn = self._make_mock_conn()
        pool = MagicMock()
        pool.connection.return_value.__aenter__.return_value = conn

        with patch(
            "infrastructure.postgres.migrations._discover_migrations"
        ) as mock_discover:
            mock_discover.return_value = [
                ("001", "001_test.sql", "SELECT 1"),
            ]
            applied = _run(run_migrations(pool))

        assert applied == ["001_test.sql"]

    def test_run_migrations_skips_existing(self) -> None:
        from infrastructure.postgres.migrations import run_migrations

        conn = self._make_mock_conn(existing_versions=[{"version": "001"}])
        pool = MagicMock()
        pool.connection.return_value.__aenter__.return_value = conn

        with patch(
            "infrastructure.postgres.migrations._discover_migrations"
        ) as mock_discover:
            mock_discover.return_value = [
                ("001", "001_test.sql", "SELECT 1"),
            ]
            applied = _run(run_migrations(pool))

        assert applied == []

    def test_run_migrations_idempotent(self) -> None:
        from infrastructure.postgres.migrations import run_migrations

        conn = self._make_mock_conn()
        pool = MagicMock()
        pool.connection.return_value.__aenter__.return_value = conn

        with patch(
            "infrastructure.postgres.migrations._discover_migrations"
        ) as mock_discover:
            mock_discover.return_value = [
                ("001", "001_test.sql", "SELECT 1"),
            ]
            applied1 = _run(run_migrations(pool))
            conn.cursor.return_value.__aenter__.return_value.__aiter__.return_value = iter([
                {"version": "001"},
            ])
            applied2 = _run(run_migrations(pool))

        assert applied1 == ["001_test.sql"]
        assert applied2 == []

    def test_run_migrations_failure_raises_migration_error(self) -> None:
        from infrastructure.postgres.errors import DatabaseMigrationError
        from infrastructure.postgres.migrations import run_migrations

        conn = self._make_mock_conn()
        conn.execute = AsyncMock(side_effect=RuntimeError("SQL failure"))
        pool = MagicMock()
        pool.connection.return_value.__aenter__.return_value = conn

        with patch(
            "infrastructure.postgres.migrations._discover_migrations"
        ) as mock_discover:
            mock_discover.return_value = [
                ("001", "001_test.sql", "SELECT 1"),
            ]
            with pytest.raises(DatabaseMigrationError):
                _run(run_migrations(pool))


class TestLifecycle:
    def test_startup_opens_pool_and_runs_migrations(self) -> None:
        from core.lifespan import on_startup

        app = MagicMock()
        app.state = MagicMock()

        with patch(
            "core.lifespan.POSTGRES_ENABLED", True
        ), patch(
            "core.lifespan.POSTGRES_AUTO_MIGRATE", True
        ), patch(
            "core.lifespan.create_pool_from_settings"
        ) as mock_create, patch(
            "core.lifespan.open_pool"
        ) as mock_open, patch(
            "core.lifespan.run_migrations"
        ) as mock_migrate:
            pool = MagicMock()
            conn = AsyncMock()
            conn.execute = AsyncMock(return_value=MagicMock())
            pool.connection.return_value.__aenter__.return_value = conn
            mock_create.return_value = pool
            mock_open.return_value = None

            _run(on_startup(app))

            mock_create.assert_called_once()
            mock_open.assert_called_once_with(pool)
            mock_migrate.assert_called_once_with(pool)
            assert app.state.pg_pool is pool

    def test_startup_skips_migrations_when_disabled(self) -> None:
        from core.lifespan import on_startup

        app = MagicMock()
        app.state = MagicMock()

        with patch(
            "core.lifespan.POSTGRES_ENABLED", True
        ), patch(
            "core.lifespan.POSTGRES_AUTO_MIGRATE", False
        ), patch(
            "core.lifespan.create_pool_from_settings"
        ) as mock_create, patch(
            "core.lifespan.open_pool"
        ) as mock_open, patch(
            "core.lifespan.run_migrations"
        ) as mock_migrate:
            pool = MagicMock()
            conn = AsyncMock()
            conn.execute = AsyncMock(return_value=MagicMock())
            pool.connection.return_value.__aenter__.return_value = conn
            mock_create.return_value = pool

            _run(on_startup(app))

            mock_migrate.assert_not_called()
            assert app.state.pg_pool is pool

    def test_startup_skips_when_postgres_disabled(self) -> None:
        from core.lifespan import on_startup

        state = MagicMock(spec=[])
        app = MagicMock(spec=["state"])
        app.state = state
        with patch("core.lifespan.POSTGRES_ENABLED", False):
            _run(on_startup(app))
        assert not hasattr(state, "pg_pool")

    def test_shutdown_closes_pool(self) -> None:
        from core.lifespan import on_shutdown

        pool = AsyncMock()
        app = MagicMock()
        app.state.pg_pool = pool

        _run(on_shutdown(app))
        pool.close.assert_awaited_once()

    def test_shutdown_no_pool_does_not_raise(self) -> None:
        from core.lifespan import on_shutdown

        app = MagicMock()
        app.state = MagicMock(spec=[])
        _run(on_shutdown(app))
