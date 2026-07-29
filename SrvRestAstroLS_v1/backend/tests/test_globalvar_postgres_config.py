"""Canonical TebaAI configuration tests for DB_PG_* and TEBAAI_* variables."""

from __future__ import annotations

import os
from unittest.mock import patch
from urllib.parse import unquote, urlparse

import pytest
from pydantic import ValidationError

from core.config import get_settings


def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _db_env(**overrides: str) -> dict[str, str]:
    env = {
        "DB_PG_IP": "pg.example.com",
        "DB_PG_PORT": "5432",
        "DB_PG_USER": "tebaai-user",
        "DB_PG_PASS": "tebaai-password",
        "TEBAAI_DB_NAME": "tebaai",
    }
    env.update(overrides)
    return env


def _settings(env: dict[str, str]):
    with patch.dict(os.environ, env, clear=True):
        _clear_settings_cache()
        return get_settings()


class TestCanonicalPostgresConfig:
    def setup_method(self) -> None:
        _clear_settings_cache()

    def test_db_pg_resolves_both_urls(self) -> None:
        settings = _settings(_db_env())

        assert settings.postgres_enabled is True
        assert settings.postgres_host == "pg.example.com"
        assert settings.postgres_port == 5432
        assert settings.postgres_db == "tebaai"
        assert settings.postgres_user == "tebaai-user"
        assert settings.sqlalchemy_postgres_url().startswith(
            "postgresql+psycopg://"
        )
        assert settings.postgres_resolved_dsn().startswith("postgresql://")

    def test_default_port_and_database_name(self) -> None:
        env = _db_env()
        env.pop("DB_PG_PORT")
        env.pop("TEBAAI_DB_NAME")

        settings = _settings(env)

        assert settings.postgres_port == 5432
        assert settings.postgres_db == "tebaai"

    def test_special_characters_are_escaped_once(self) -> None:
        settings = _settings(
            _db_env(
                DB_PG_USER="user@domain/name",
                DB_PG_PASS="p@ss:word/#% value",
            )
        )

        for url in (
            settings.sqlalchemy_postgres_url(),
            settings.postgres_resolved_dsn(),
        ):
            parsed = urlparse(url)
            assert unquote(parsed.username or "") == "user@domain/name"
            assert unquote(parsed.password or "") == "p@ss:word/#% value"
            assert "%2540" not in url

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "pg.internal"])
    def test_valid_hosts(self, host: str) -> None:
        assert _settings(_db_env(DB_PG_IP=host)).postgres_host == host

    def test_ipv6_is_bracketed_in_urls(self) -> None:
        settings = _settings(_db_env(DB_PG_IP="2001:db8::1"))
        assert "@[2001:db8::1]:5432/" in settings.postgres_resolved_dsn()

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("DB_PG_IP", ""),
            ("DB_PG_USER", ""),
            ("DB_PG_PASS", ""),
        ],
    )
    def test_required_db_values(self, name: str, value: str) -> None:
        with pytest.raises(ValidationError):
            _settings(_db_env(**{name: value}))

    @pytest.mark.parametrize("port", ["invalid", "0", "65536", "-1"])
    def test_invalid_ports(self, port: str) -> None:
        with pytest.raises(ValidationError):
            _settings(_db_env(DB_PG_PORT=port))

    @pytest.mark.parametrize(
        "name",
        ["team360", "v360", "postgres", "bad/name", "bad name", "bad?query"],
    )
    def test_invalid_database_names(self, name: str) -> None:
        with pytest.raises(ValidationError):
            _settings(_db_env(TEBAAI_DB_NAME=name))

    def test_legacy_postgres_connection_variables_are_not_a_source(self) -> None:
        settings = _settings(
            {
                "TEBAAI_POSTGRES_ENABLED": "true",
                "TEBAAI_POSTGRES_HOST": "legacy-host",
                "TEBAAI_POSTGRES_DB": "legacy-db",
                "TEBAAI_POSTGRES_USER": "legacy-user",
                "TEBAAI_POSTGRES_PASSWORD": "legacy-password",
            }
        )
        assert settings.postgres_enabled is False
        assert settings.postgres_resolved_dsn() == ""


class TestEnvironmentAndProductionGuards:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("dev", "development"),
            ("development", "development"),
            ("stg", "staging"),
            ("staging", "staging"),
            ("prod", "production"),
            ("production", "production"),
        ],
    )
    def test_environment_normalization(self, raw: str, expected: str) -> None:
        env = _db_env(
            TEBAAI_ENV=raw,
            TEBAAI_JWT_SECRET="production-jwt-value",
            TEBAAI_POSTGRES_AUTO_MIGRATE="false",
        )
        assert _settings(env).env == expected

    def test_invalid_environment_fails(self) -> None:
        with pytest.raises(ValidationError):
            _settings({"TEBAAI_ENV": "unknown"})

    def test_production_requires_database(self) -> None:
        with pytest.raises(ValidationError):
            _settings(
                {
                    "TEBAAI_ENV": "production",
                    "TEBAAI_JWT_SECRET": "production-jwt-value",
                    "TEBAAI_POSTGRES_AUTO_MIGRATE": "false",
                }
            )

    @pytest.mark.parametrize("secret", ["", "change_me", "dev", "secret"])
    def test_production_rejects_missing_or_weak_jwt(self, secret: str) -> None:
        with pytest.raises(ValidationError):
            _settings(
                _db_env(
                    TEBAAI_ENV="production",
                    TEBAAI_JWT_SECRET=secret,
                    TEBAAI_POSTGRES_AUTO_MIGRATE="false",
                )
            )

    def test_production_rejects_auto_migrate(self) -> None:
        with pytest.raises(ValidationError):
            _settings(
                _db_env(
                    TEBAAI_ENV="production",
                    TEBAAI_JWT_SECRET="production-jwt-value",
                    TEBAAI_POSTGRES_AUTO_MIGRATE="true",
                )
            )

    def test_production_accepts_explicit_safe_config(self) -> None:
        settings = _settings(
            _db_env(
                TEBAAI_ENV="production",
                TEBAAI_JWT_SECRET="production-jwt-value",
                TEBAAI_POSTGRES_AUTO_MIGRATE="false",
            )
        )
        assert settings.is_production is True
        assert settings.postgres_auto_migrate is False


class TestBooleanAndSecretCompatibility:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("true", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ],
    )
    def test_auto_migrate_boolean_values(self, raw: str, expected: bool) -> None:
        settings = _settings(
            _db_env(TEBAAI_POSTGRES_AUTO_MIGRATE=raw)
        )
        assert settings.postgres_auto_migrate is expected

    def test_canonical_auth_variables_feed_compatibility_accessors(self) -> None:
        settings = _settings(
            {
                "TEBAAI_AUTH_PEPPER": "pepper-value",
                "TEBAAI_JWT_SECRET": "jwt-value",
                "TEBAAI_E2E_GUEST_PASSWORD": "guest-value",
            }
        )
        assert settings.auth_password_pepper.get_secret_value() == "pepper-value"
        assert settings.auth_jwt_secret.get_secret_value() == "jwt-value"
        assert settings.guest_password.get_secret_value() == "guest-value"

    def test_legacy_auth_variable_names_remain_compatible(self) -> None:
        settings = _settings(
            {
                "TEBAAI_AUTH_PASSWORD_PEPPER": "legacy-pepper",
                "TEBAAI_AUTH_JWT_SECRET": "legacy-jwt",
                "TEBAAI_GUEST_PASSWORD": "legacy-guest",
            }
        )
        assert settings.auth_pepper.get_secret_value() == "legacy-pepper"
        assert settings.jwt_secret.get_secret_value() == "legacy-jwt"
        assert settings.e2e_guest_password.get_secret_value() == "legacy-guest"

    def test_secrets_are_absent_from_repr_and_display_url(self) -> None:
        env = _db_env(
            DB_PG_PASS="database-secret",
            TEBAAI_AUTH_PEPPER="pepper-secret",
            TEBAAI_JWT_SECRET="jwt-secret-value",
        )
        settings = _settings(env)
        rendered = repr(settings)
        display = settings.postgres_dsn_display()

        for secret in (
            "database-secret",
            "pepper-secret",
            "jwt-secret-value",
        ):
            assert secret not in rendered
            assert secret not in display
