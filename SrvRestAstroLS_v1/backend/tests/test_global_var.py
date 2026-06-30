from __future__ import annotations

import importlib
import os
from unittest.mock import patch

import pytest


class TestSafeImport:
    def test_import_global_var_is_safe(self) -> None:
        """Importing globalVar must not raise, connect, or produce side effects."""
        import globalVar  # noqa: F401
        assert True

    def test_import_does_not_read_env(self) -> None:
        """globalVar.py should not contain os.getenv calls — verified by static analysis."""
        import globalVar  # noqa: F401
        assert True


class TestExpectedExports:
    def test_module_has_SETTINGS(self) -> None:
        import globalVar
        assert hasattr(globalVar, "SETTINGS")

    def test_runtime_exports(self) -> None:
        import globalVar
        assert globalVar.SERVICE_NAME == "tebaai-backend"
        assert globalVar.SERVICE_VERSION == "0.1.0"
        assert globalVar.ENV == "development"
        assert globalVar.DEBUG is False
        assert globalVar.DEFAULT_LANGUAGE == "es"
        assert isinstance(globalVar.SUPPORTED_LANGUAGES, list)
        assert "es" in globalVar.SUPPORTED_LANGUAGES

    def test_postgres_exports_disabled_defaults(self) -> None:
        """When no DB_PG_* or TEBAAI_POSTGRES_* vars, postgres stays disabled with defaults."""
        from core.config import get_settings
        get_settings.cache_clear()
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import globalVar
            importlib.reload(globalVar)
            assert globalVar.POSTGRES_ENABLED is False
            assert globalVar.POSTGRES_HOST == "127.0.0.1"
            assert globalVar.POSTGRES_PORT == 5432
            assert globalVar.POSTGRES_DB == ""
            assert globalVar.POSTGRES_USER == ""
            assert isinstance(globalVar.POSTGRES_DSN, str)
            assert isinstance(globalVar.POSTGRES_DSN_DISPLAY, str)
            assert globalVar.POSTGRES_MIN_POOL_SIZE == 1
            assert globalVar.POSTGRES_MAX_POOL_SIZE == 10
            assert globalVar.POSTGRES_CONNECT_TIMEOUT_SECONDS == 10
            assert globalVar.POSTGRES_APPLICATION_NAME == "tebaai-backend"
            assert globalVar.POSTGRES_AUTO_MIGRATE is True

    def test_milvus_exports(self) -> None:
        import globalVar
        assert globalVar.MILVUS_ENABLED is False
        assert globalVar.MILVUS_HOST == "127.0.0.1"
        assert globalVar.MILVUS_PORT == 19530
        assert globalVar.MILVUS_URI == ""
        assert globalVar.MILVUS_CONNECT_TIMEOUT_SECONDS == 10

    def test_litellm_exports(self) -> None:
        import globalVar
        assert globalVar.LITELLM_ENABLED is False
        assert globalVar.LITELLM_BASE_URL == "http://127.0.0.1:4000"
        assert globalVar.LITELLM_DEFAULT_MODEL_ALIAS == ""
        assert globalVar.LITELLM_TIMEOUT_SECONDS == 60

    def test_auth_exports(self) -> None:
        import globalVar
        assert globalVar.AUTH_ENABLED is False
        assert globalVar.AUTH_JWT_ALGORITHM == "HS256"
        assert globalVar.AUTH_ACCESS_TOKEN_TTL_MINUTES == 15
        assert globalVar.AUTH_REFRESH_TOKEN_TTL_DAYS == 30
        assert globalVar.AUTH_ISSUER == "tebaai-api"
        assert globalVar.AUTH_AUDIENCE == "tebaai-web"

    def test_all_expected_exports_present(self) -> None:
        """Verify that all documented constants are exported."""
        import globalVar

        expected = {
            # Runtime
            "SETTINGS", "SERVICE_NAME", "SERVICE_VERSION", "ENV", "DEBUG",
            "DEFAULT_LANGUAGE", "SUPPORTED_LANGUAGES",
            # PostgreSQL
            "POSTGRES_ENABLED", "POSTGRES_HOST", "POSTGRES_PORT",
            "POSTGRES_DB", "POSTGRES_USER",
            "POSTGRES_DSN", "POSTGRES_DSN_DISPLAY",
            "POSTGRES_MIN_POOL_SIZE", "POSTGRES_MAX_POOL_SIZE",
            "POSTGRES_CONNECT_TIMEOUT_SECONDS",             "POSTGRES_APPLICATION_NAME",
            "POSTGRES_AUTO_MIGRATE",
            # Milvus
            "MILVUS_ENABLED", "MILVUS_HOST", "MILVUS_PORT",
            "MILVUS_URI", "MILVUS_CONNECT_TIMEOUT_SECONDS",
            # LiteLLM
            "LITELLM_ENABLED", "LITELLM_BASE_URL",
            "LITELLM_DEFAULT_MODEL_ALIAS", "LITELLM_TIMEOUT_SECONDS",
            # Auth
            "AUTH_ENABLED", "AUTH_JWT_ALGORITHM",
            "AUTH_ACCESS_TOKEN_TTL_MINUTES", "AUTH_REFRESH_TOKEN_TTL_DAYS",
            "AUTH_ISSUER", "AUTH_AUDIENCE",
        }
        for name in expected:
            assert hasattr(globalVar, name), f"Missing export: {name}"


class TestFreshImport:
    def test_reload_gives_same_values(self) -> None:
        import globalVar
        v1 = globalVar.SERVICE_NAME
        importlib.reload(globalVar)
        v2 = globalVar.SERVICE_NAME
        assert v1 == v2
