from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.config import get_settings, sanitize_dsn


# ── Helpers ─────────────────────────────────────────────────────────

def _env(**kw: str) -> dict[str, str]:
    return {f"TEBAAI_{k.upper()}": v for k, v in kw.items()}


# ── Test: Defaults ──────────────────────────────────────────────────

class TestDefaults:
    def test_runtime_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.env == "development"
        assert s.debug is False
        assert s.service_name == "tebaai-backend"
        assert s.service_version == "0.1.0"
        assert s.default_language == "es"
        assert s.supported_languages == "es,en,he"

    def test_postgres_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.postgres_enabled is False
        assert s.postgres_host == "127.0.0.1"
        assert s.postgres_port == 5432
        assert s.postgres_min_pool_size == 1
        assert s.postgres_max_pool_size == 10
        assert s.postgres_connect_timeout_seconds == 10
        assert s.postgres_application_name == "tebaai-backend"

    def test_milvus_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.milvus_enabled is False
        assert s.milvus_host == "127.0.0.1"
        assert s.milvus_port == 19530
        assert s.milvus_connect_timeout_seconds == 10

    def test_litellm_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.litellm_enabled is False
        assert s.litellm_base_url == "http://127.0.0.1:4000"
        assert s.litellm_timeout_seconds == 60

    def test_simple_rag_is_the_default_research_pipeline(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.research_pipeline == "simple_rag"

    def test_research_pipeline_is_allowlisted(self) -> None:
        with patch.dict(os.environ, _env(RESEARCH_PIPELINE="compare"), clear=True):
            assert get_settings().research_pipeline == "compare"
        get_settings.cache_clear()
        with patch.dict(os.environ, _env(RESEARCH_PIPELINE="unknown"), clear=True):
            with pytest.raises(ValueError):
                get_settings()

    def test_auth_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.auth_enabled is False
        assert s.auth_jwt_algorithm == "HS256"
        assert s.auth_access_token_ttl_minutes == 15
        assert s.auth_refresh_token_ttl_days == 30
        assert s.auth_issuer == "tebaai-api"
        assert s.auth_audience == "tebaai-web"


# ── Test: Boolean parsing ───────────────────────────────────────────

class TestBooleanParsing:
    @pytest.mark.parametrize("raw,expected", [
        ("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
        ("false", False), ("False", False), ("0", False), ("no", False), ("off", False),
    ])
    def test_debug_parsing(self, raw: str, expected: bool) -> None:
        with patch.dict(os.environ, _env(DEBUG=raw), clear=True):
            s = get_settings()
        assert s.debug is expected


# ── Test: Integer parsing ───────────────────────────────────────────

class TestIntegerParsing:
    def test_port_parsing(self) -> None:
        with patch.dict(os.environ, {
            "DB_PG_IP": "localhost",
            "DB_PG_PORT": "7000",
            "DB_PG_USER": "user",
            "DB_PG_PASS": "password",
        }, clear=True):
            s = get_settings()
        assert s.postgres_port == 7000

    def test_min_pool_size(self) -> None:
        with patch.dict(os.environ, _env(POSTGRES_MIN_POOL_SIZE="5"), clear=True):
            s = get_settings()
        assert s.postgres_min_pool_size == 5


# ── Test: Languages ─────────────────────────────────────────────────

class TestLanguages:
    def test_supported_languages_parsed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.supported_languages_list == ["es", "en", "he"]

    def test_single_language(self) -> None:
        with patch.dict(os.environ, _env(SUPPORTED_LANGUAGES="fr"), clear=True):
            s = get_settings()
        assert s.supported_languages_list == ["fr"]

    def test_empty_falls_back_to_es(self) -> None:
        with patch.dict(os.environ, _env(SUPPORTED_LANGUAGES=""), clear=True):
            s = get_settings()
        assert s.supported_languages_list == ["es"]

    def test_custom_language(self) -> None:
        with patch.dict(os.environ, _env(DEFAULT_LANGUAGE="he"), clear=True):
            s = get_settings()
        assert s.default_language == "he"


# ── Test: PostgreSQL disabled ───────────────────────────────────────

class TestPostgresDisabled:
    def test_no_creds_required_when_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.postgres_enabled is False

    def test_explicit_false_ok(self) -> None:
        with patch.dict(os.environ, _env(POSTGRES_ENABLED="false"), clear=True):
            s = get_settings()
        assert s.postgres_enabled is False


# ── Test: PostgreSQL enabled ────────────────────────────────────────

class TestAutoMigrate:
    def test_auto_migrate_default_true(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.postgres_auto_migrate is True

    @pytest.mark.parametrize("raw,expected", [
        ("true", True), ("false", False),
    ])
    def test_auto_migrate_parsing(self, raw: str, expected: bool) -> None:
        with patch.dict(os.environ, _env(POSTGRES_AUTO_MIGRATE=raw), clear=True):
            s = get_settings()
        assert s.postgres_auto_migrate is expected


class TestPostgresEnabled:
    def test_individual_fields(self) -> None:
        env = {
            "DB_PG_IP": "pg.example.com",
            "DB_PG_PORT": "5433",
            "DB_PG_USER": "admin",
            "DB_PG_PASS": "s3cret",
            "TEBAAI_DB_NAME": "tebaai",
        }
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        assert s.postgres_enabled is True
        assert s.postgres_host == "pg.example.com"
        assert s.postgres_port == 5433
        assert s.postgres_db == "tebaai"
        assert s.postgres_user == "admin"

    def test_legacy_dsn_is_not_a_connection_source(self) -> None:
        env = _env(
            POSTGRES_DSN="postgresql://dsn_user:dsn_pass@dsn_host:5555/dsn_db"
        )
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        assert s.postgres_enabled is False
        assert s.postgres_resolved_dsn() == ""

    def test_resolved_dsn_from_fields(self) -> None:
        env = {
            "DB_PG_IP": "local.host",
            "DB_PG_PORT": "7777",
            "DB_PG_USER": "myuser",
            "DB_PG_PASS": "mypass",
            "TEBAAI_DB_NAME": "mydb",
        }
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        assert s.postgres_resolved_dsn() == "postgresql://myuser:mypass@local.host:7777/mydb"

    def test_missing_fields_raises(self) -> None:
        env = {
            "DB_PG_IP": "localhost",
            "DB_PG_USER": "",
            "DB_PG_PASS": "",
        }
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            get_settings()

    def test_partial_general_config_raises(self) -> None:
        env = {"DB_PG_IP": "localhost"}
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            get_settings()


# ── Test: DSN sanitize ──────────────────────────────────────────────

class TestDSNSanitize:
    def test_sanitize_removes_password(self) -> None:
        result = sanitize_dsn("postgresql://u:secret@host:5432/db")
        assert result == "postgresql://u@host:5432/db"

    def test_sanitize_without_password(self) -> None:
        result = sanitize_dsn("postgresql://host:5432/db")
        assert result == "postgresql://host:5432/db"

    def test_sanitize_empty(self) -> None:
        assert sanitize_dsn("") == ""

    def test_dsn_display(self) -> None:
        env = {
            "DB_PG_IP": "h",
            "DB_PG_PORT": "1",
            "DB_PG_USER": "u",
            "DB_PG_PASS": "secret123",
            "TEBAAI_DB_NAME": "d",
        }
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        display = s.postgres_dsn_display()
        assert display == "postgresql://u@h:1/d"
        assert "secret123" not in display


# ── Test: Milvus ────────────────────────────────────────────────────

class TestMilvus:
    def test_disabled_no_creds_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.milvus_enabled is False

    def test_uri_available(self) -> None:
        env = _env(MILVUS_URI="http://milvus-prod:19530")
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        assert s.milvus_uri == "http://milvus-prod:19530"


# ── Test: LiteLLM ───────────────────────────────────────────────────

class TestLiteLLM:
    def test_disabled_no_creds_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.litellm_enabled is False


# ── Test: Auth ──────────────────────────────────────────────────────

class TestAuth:
    def test_disabled_no_secret_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = get_settings()
        assert s.auth_enabled is False

    def test_enabled_requires_secret(self) -> None:
        env = _env(AUTH_ENABLED="true", AUTH_JWT_SECRET="")
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            get_settings()

    def test_enabled_with_secret(self) -> None:
        env = _env(AUTH_ENABLED="true", AUTH_JWT_SECRET="my-secret-key")
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        assert s.auth_enabled is True


# ── Test: Secrets hidden in repr ────────────────────────────────────

class TestSecretsHidden:
    def test_password_not_in_repr(self) -> None:
        env = _env(POSTGRES_PASSWORD="supersecret", MILVUS_TOKEN="mytoken")
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        r = repr(s.postgres_password)
        assert "supersecret" not in r
        r2 = repr(s.milvus_token)
        assert "mytoken" not in r2


# ── Test: Cache ─────────────────────────────────────────────────────

class TestCache:
    def test_get_settings_is_cached(self) -> None:
        with patch.dict(os.environ, _env(ENV="development"), clear=True):
            s1 = get_settings()
            s2 = get_settings()
        assert s1 is s2

    def test_cache_clear(self) -> None:
        with patch.dict(os.environ, _env(ENV="development"), clear=True):
            s1 = get_settings()
        get_settings.cache_clear()
        with patch.dict(os.environ, _env(ENV="staging"), clear=True):
            s2 = get_settings()
        assert s1 is not s2
        assert s2.env == "staging"


# ── Test: No side effects ───────────────────────────────────────────

class TestNoSideEffects:
    def test_import_does_not_connect(self) -> None:
        import core.config  # noqa: F401
        assert True

    def test_postgres_dsn_display_no_secret(self) -> None:
        env = {
            "DB_PG_IP": "localhost",
            "DB_PG_USER": "secretuser",
            "DB_PG_PASS": "s3cret!",
            "TEBAAI_DB_NAME": "secretdb",
        }
        with patch.dict(os.environ, env, clear=True):
            s = get_settings()
        display = s.postgres_dsn_display()
        assert "s3cret" not in display
        assert "secretdb" in display


# ── Test: sanitize_dsn standalone ───────────────────────────────────

class TestSanitizeDSN:
    def test_invalid_dsn(self) -> None:
        assert sanitize_dsn("not-a-url") == "not-a-url"

    def test_postgres_scheme(self) -> None:
        result = sanitize_dsn("postgresql://alice:pass@pg:5432/mydb")
        assert result == "postgresql://alice@pg:5432/mydb"

    def test_postgres_scheme_no_port(self) -> None:
        result = sanitize_dsn("postgresql://alice:pass@pg/mydb")
        assert result == "postgresql://alice@pg/mydb"
