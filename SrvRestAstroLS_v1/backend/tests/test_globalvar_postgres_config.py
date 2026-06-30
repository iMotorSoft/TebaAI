"""Tests for PostgreSQL config resolution from DB_PG_* environment variables."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.config import get_settings


def _clear_settings_cache():
    get_settings.cache_clear()


class TestPostgresConfigFromDBPG:
    def setup_method(self):
        _clear_settings_cache()

    def test_db_pg_resolves_dsn(self):
        """DB_PG_* vars construct a working config for db=tebaai."""
        with patch.dict(os.environ, {
            "DB_PG_IP": "pg.example.com",
            "DB_PG_PORT": "5432",
            "DB_PG_USER": "testuser",
            "DB_PG_PASS": "testpass",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_enabled is True
            assert s.postgres_host == "pg.example.com"
            assert s.postgres_port == 5432
            assert s.postgres_db == "tebaai"
            assert s.postgres_user == "testuser"
            dsn = s.postgres_resolved_dsn()
            assert dsn.startswith("postgresql://")
            assert "testuser" in dsn
            assert "testpass" in dsn

    def test_db_pg_defaults_localhost(self):
        """DB_PG_IP defaults to localhost when not set."""
        with patch.dict(os.environ, {
            "DB_PG_USER": "u",
            "DB_PG_PASS": "p",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_host == "127.0.0.1"
            assert s.postgres_port == 5432
            assert s.postgres_db == "tebaai"

    def test_db_pg_port_defaults_5432(self):
        """DB_PG_PORT defaults to 5432 when not set."""
        with patch.dict(os.environ, {
            "DB_PG_IP": "localhost",
            "DB_PG_USER": "u",
            "DB_PG_PASS": "p",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_port == 5432

    def test_db_pg_port_from_env(self):
        """DB_PG_PORT is parsed correctly."""
        with patch.dict(os.environ, {
            "DB_PG_PORT": "6543",
            "DB_PG_USER": "u",
            "DB_PG_PASS": "p",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_port == 6543

    def test_no_credentials_disables_postgres(self):
        """Without DB_PG_USER or DB_PG_PASS, postgres stays disabled."""
        with patch.dict(os.environ, {}, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_enabled is False
            assert s.postgres_db == ""
            assert s.postgres_user == ""

    def test_empty_user_keeps_disabled(self):
        """Empty DB_PG_USER string does not enable postgres."""
        with patch.dict(os.environ, {
            "DB_PG_USER": "",
            "DB_PG_PASS": "",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_enabled is False

    def test_tebaai_override_takes_precedence(self):
        """TEBAAI_POSTGRES_HOST overrides DB_PG_IP when set."""
        with patch.dict(os.environ, {
            "TEBAAI_POSTGRES_HOST": "override-host",
            "TEBAAI_POSTGRES_DB": "override_db",
            "TEBAAI_POSTGRES_USER": "override_user",
            "TEBAAI_POSTGRES_PASSWORD": "override_pass",
            "DB_PG_IP": "pg-default",
            "DB_PG_USER": "pg-user",
            "DB_PG_PASS": "pg-pass",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_host == "override-host"
            assert s.postgres_db == "override_db"
            assert s.postgres_user == "override_user"

    def test_tebaai_enabled_stops_dbpg_fallback(self):
        """When TEBAAI_POSTGRES_ENABLED=true, DB_PG_* fallback is skipped."""
        with patch.dict(os.environ, {
            "TEBAAI_POSTGRES_ENABLED": "true",
            "TEBAAI_POSTGRES_HOST": "tebaai-host",
            "TEBAAI_POSTGRES_DB": "tebaai_db",
            "TEBAAI_POSTGRES_USER": "tebaai_user",
            "TEBAAI_POSTGRES_PASSWORD": "tebaai_pass",
            "DB_PG_IP": "ignored",
            "DB_PG_USER": "ignored",
            "DB_PG_PASS": "ignored",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            assert s.postgres_host == "tebaai-host"
            assert s.postgres_db == "tebaai_db"
            assert s.postgres_user == "tebaai_user"

    def test_dsn_sanitized_no_password(self):
        """DSN display does not leak password."""
        with patch.dict(os.environ, {
            "DB_PG_USER": "secretuser",
            "DB_PG_PASS": "supersecret",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            display = s.postgres_dsn_display()
            assert "supersecret" not in display
            assert "secretuser" in display

    def test_dsn_operational_contains_password(self):
        """Operational DSN contains password for connection."""
        with patch.dict(os.environ, {
            "DB_PG_USER": "opuser",
            "DB_PG_PASS": "oppass",
        }, clear=True):
            _clear_settings_cache()
            dsn = get_settings().postgres_resolved_dsn()
            assert dsn.startswith("postgresql://")
            assert "opuser" in dsn
            assert "oppass" in dsn


class TestPostgresConfigDisplaySafety:
    def test_password_not_in_repr(self):
        """Password fields do not appear in repr()."""
        with patch.dict(os.environ, {
            "DB_PG_USER": "u",
            "DB_PG_PASS": "should-not-appear",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            r = repr(s)
            assert "should-not-appear" not in r

    def test_password_not_in_str(self):
        """Password fields do not appear in str()."""
        with patch.dict(os.environ, {
            "DB_PG_USER": "u",
            "DB_PG_PASS": "should-not-appear-either",
        }, clear=True):
            _clear_settings_cache()
            s = get_settings()
            r = str(s)
            assert "should-not-appear-either" not in r
