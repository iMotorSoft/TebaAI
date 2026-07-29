"""Global configuration facade for the TebaAI backend.

This module is the stable, ergonomic entry point for common configuration
values used across the backend.

Most values flow through core/config.py (Pydantic, env_prefix="TEBAAI_").
The LiteLLM API key is an exception — it follows the shared global convention
LITELLM_MASTER_KEY, so its resolution is handled directly here via
resolve_litellm_api_key() with a fallback chain documented below.

Usage:

    import globalVar
    host = globalVar.POSTGRES_HOST

    from globalVar import SERVICE_NAME, LITELLM_API_KEY

Architecture:

    .env / env vars → core/config.py → globalVar.py → consumers
    LITELLM_MASTER_KEY → globalVar.resolve_litellm_api_key() → consumers
"""

from __future__ import annotations

import os as _os

from core.config import get_settings

# @lat: [[global-configuration-facade-policy#3. Decision Adoptada]]
SETTINGS = get_settings()

# ── Runtime general ──────────────────────────────────────────────
SERVICE_NAME: str = SETTINGS.service_name
SERVICE_VERSION: str = SETTINGS.service_version
ENV: str = SETTINGS.env
TEBAAI_ENV: str = SETTINGS.env
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
TEBAAI_DB_NAME: str = SETTINGS.db_name
TEBAAI_DB_URL: str = SETTINGS.sqlalchemy_postgres_url()
TEBAAI_DB_URL_PSQL: str = SETTINGS.postgres_resolved_dsn()
POSTGRES_MIN_POOL_SIZE: int = SETTINGS.postgres_min_pool_size
POSTGRES_MAX_POOL_SIZE: int = SETTINGS.postgres_max_pool_size
POSTGRES_CONNECT_TIMEOUT_SECONDS: int = SETTINGS.postgres_connect_timeout_seconds
POSTGRES_APPLICATION_NAME: str = SETTINGS.postgres_application_name
POSTGRES_AUTO_MIGRATE: bool = SETTINGS.postgres_auto_migrate
TEBAAI_POSTGRES_AUTO_MIGRATE: bool = SETTINGS.postgres_auto_migrate


def get_tebaai_db_url() -> str:
    """Return the escaped SQLAlchemy/Psycopg 3 database URL."""
    return SETTINGS.sqlalchemy_postgres_url()


def get_tebaai_db_url_psql() -> str:
    """Return the escaped URL accepted by Psycopg and PostgreSQL CLI tools."""
    return SETTINGS.postgres_resolved_dsn()

# ── Milvus ───────────────────────────────────────────────────────
MILVUS_ENABLED: bool = SETTINGS.milvus_enabled
MILVUS_HOST: str = SETTINGS.milvus_host
MILVUS_PORT: int = SETTINGS.milvus_port
MILVUS_URI: str = SETTINGS.milvus_uri
MILVUS_CONNECT_TIMEOUT_SECONDS: int = SETTINGS.milvus_connect_timeout_seconds
MILVUS_COLLECTION_BRESLOV: str = SETTINGS.milvus_collection_breslov

# ── Embeddings ────────────────────────────────────────────────────
EMBEDDINGS_ENABLED: bool = SETTINGS.embeddings_enabled
EMBEDDINGS_PROVIDER: str = SETTINGS.embeddings_provider
EMBEDDINGS_BASE_URL: str = SETTINGS.embeddings_base_url
EMBEDDINGS_API_KEY: str = SETTINGS.embeddings_api_key.get_secret_value()
EMBEDDINGS_MODEL_ALIAS: str = SETTINGS.embeddings_model_alias
EMBEDDINGS_MODEL_NAME: str = SETTINGS.embeddings_model_name
EMBEDDINGS_DIMENSION: int = SETTINGS.embeddings_dimension
EMBEDDINGS_BATCH_SIZE: int = SETTINGS.embeddings_batch_size
EMBEDDINGS_TIMEOUT_SECONDS: int = SETTINGS.embeddings_timeout_seconds

# ── LiteLLM key resolution ───────────────────────────────────────

def resolve_litellm_api_key() -> str:
    """Resolve the LiteLLM API key with documented precedence.

    Precedence:
      1. LITELLM_MASTER_KEY — shared global convention across iMotorSoft projects.
      2. TEBAAI_LITELLM_API_KEY — TebaAI-specific override if explicitly set.
      3. SETTINGS.litellm_api_key — Pydantic-resolved value (via TEBAAI_ prefix).

    The first non-empty value wins. Returns empty string if none found.
    """
    master = _os.environ.get("LITELLM_MASTER_KEY", "").strip()
    if master:
        return master
    tebaai = _os.environ.get("TEBAAI_LITELLM_API_KEY", "").strip()
    if tebaai:
        return tebaai
    return SETTINGS.litellm_api_key.get_secret_value()


LITELLM_ENABLED: bool = SETTINGS.litellm_enabled
LITELLM_BASE_URL: str = SETTINGS.litellm_base_url
LITELLM_API_KEY: str = resolve_litellm_api_key()
LITELLM_DEFAULT_MODEL_ALIAS: str = SETTINGS.litellm_default_model_alias
LITELLM_TIMEOUT_SECONDS: int = SETTINGS.litellm_timeout_seconds

# ── Research Conversation ─────────────────────────────────────────
RESEARCH_CONVERSATION_MODEL: str = SETTINGS.research_conversation_model
RESEARCH_EMBEDDING_MODEL_ALIAS: str = SETTINGS.research_embedding_model_alias
BRESLOV_PRODUCTIVE_COLLECTION: str = SETTINGS.breslov_productive_collection
RESEARCH_PIPELINE: str = SETTINGS.research_pipeline

# ── Auth ─────────────────────────────────────────────────────────
AUTH_ENABLED: bool = SETTINGS.auth_enabled
TEBAAI_AUTH_PEPPER = SETTINGS.auth_pepper
TEBAAI_JWT_SECRET = SETTINGS.jwt_secret
AUTH_JWT_ALGORITHM: str = SETTINGS.auth_jwt_algorithm
AUTH_ACCESS_TOKEN_TTL_MINUTES: int = SETTINGS.auth_access_token_ttl_minutes
AUTH_REFRESH_TOKEN_TTL_DAYS: int = SETTINGS.auth_refresh_token_ttl_days
AUTH_ISSUER: str = SETTINGS.auth_issuer
AUTH_AUDIENCE: str = SETTINGS.auth_audience


def get_tebaai_auth_pepper() -> str:
    """Return the configured auth pepper without logging or formatting it."""
    return SETTINGS.auth_pepper.get_secret_value()


def get_tebaai_jwt_secret() -> str:
    """Return the configured JWT secret without logging or formatting it."""
    return SETTINGS.jwt_secret.get_secret_value()


def is_tebaai_production() -> bool:
    return SETTINGS.is_production


def get_tebaai_config_summary() -> dict[str, str | int | bool]:
    """Return boot diagnostics that never contain secret values or DSNs."""
    return {
        "environment": TEBAAI_ENV,
        "database_host_configured": POSTGRES_ENABLED and bool(POSTGRES_HOST),
        "database_port": POSTGRES_PORT,
        "database_name": TEBAAI_DB_NAME,
        "database_user_configured": POSTGRES_ENABLED and bool(POSTGRES_USER),
        "database_password_configured": POSTGRES_ENABLED
        and bool(SETTINGS.postgres_password.get_secret_value()),
        "auth_pepper_configured": bool(get_tebaai_auth_pepper()),
        "jwt_secret_configured": bool(get_tebaai_jwt_secret()),
        "postgres_auto_migrate": TEBAAI_POSTGRES_AUTO_MIGRATE,
    }
