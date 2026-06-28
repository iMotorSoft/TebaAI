"""Global configuration facade for the TebaAI backend.

This module is the stable, ergonomic entry point for common configuration
values used across the backend. It does NOT read environment variables
directly — that responsibility belongs exclusively to core/config.py.

Usage:

    import globalVar
    host = globalVar.POSTGRES_HOST

    from globalVar import SERVICE_NAME, LITELLM_BASE_URL

Architecture:

    .env / env vars → core/config.py → globalVar.py → consumers
"""

from __future__ import annotations

from core.config import get_settings

SETTINGS = get_settings()

# ── Runtime general ──────────────────────────────────────────────
SERVICE_NAME: str = SETTINGS.service_name
SERVICE_VERSION: str = SETTINGS.service_version
ENV: str = SETTINGS.env
DEBUG: bool = SETTINGS.debug
DEFAULT_LANGUAGE: str = SETTINGS.default_language
SUPPORTED_LANGUAGES: list[str] = SETTINGS.supported_languages_list

# ── PostgreSQL ───────────────────────────────────────────────────
POSTGRES_ENABLED: bool = SETTINGS.postgres_enabled
POSTGRES_HOST: str = SETTINGS.postgres_host
POSTGRES_PORT: int = SETTINGS.postgres_port
POSTGRES_DB: str = SETTINGS.postgres_db
POSTGRES_USER: str = SETTINGS.postgres_user
POSTGRES_DSN: str = SETTINGS.postgres_resolved_dsn()
POSTGRES_DSN_DISPLAY: str = SETTINGS.postgres_dsn_display()
POSTGRES_MIN_POOL_SIZE: int = SETTINGS.postgres_min_pool_size
POSTGRES_MAX_POOL_SIZE: int = SETTINGS.postgres_max_pool_size
POSTGRES_CONNECT_TIMEOUT_SECONDS: int = SETTINGS.postgres_connect_timeout_seconds
POSTGRES_APPLICATION_NAME: str = SETTINGS.postgres_application_name
POSTGRES_AUTO_MIGRATE: bool = SETTINGS.postgres_auto_migrate

# ── Milvus ───────────────────────────────────────────────────────
MILVUS_ENABLED: bool = SETTINGS.milvus_enabled
MILVUS_HOST: str = SETTINGS.milvus_host
MILVUS_PORT: int = SETTINGS.milvus_port
MILVUS_URI: str = SETTINGS.milvus_uri
MILVUS_CONNECT_TIMEOUT_SECONDS: int = SETTINGS.milvus_connect_timeout_seconds

# ── LiteLLM ──────────────────────────────────────────────────────
LITELLM_ENABLED: bool = SETTINGS.litellm_enabled
LITELLM_BASE_URL: str = SETTINGS.litellm_base_url
LITELLM_DEFAULT_MODEL_ALIAS: str = SETTINGS.litellm_default_model_alias
LITELLM_TIMEOUT_SECONDS: int = SETTINGS.litellm_timeout_seconds

# ── Auth ─────────────────────────────────────────────────────────
AUTH_ENABLED: bool = SETTINGS.auth_enabled
AUTH_JWT_ALGORITHM: str = SETTINGS.auth_jwt_algorithm
AUTH_ACCESS_TOKEN_TTL_MINUTES: int = SETTINGS.auth_access_token_ttl_minutes
AUTH_REFRESH_TOKEN_TTL_DAYS: int = SETTINGS.auth_refresh_token_ttl_days
AUTH_ISSUER: str = SETTINGS.auth_issuer
AUTH_AUDIENCE: str = SETTINGS.auth_audience
