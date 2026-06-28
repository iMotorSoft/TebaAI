from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.parse import urlparse, urlunparse

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def sanitize_dsn(dsn: str) -> str:
    if not dsn:
        return ""
    try:
        parsed = urlparse(dsn)
        if parsed.password:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{parsed.hostname}:{parsed.port}"
            if parsed.username:
                netloc = f"{parsed.username}@{netloc}"
            parsed = parsed._replace(netloc=netloc)
        return urlunparse(parsed)
    except Exception:
        return "<invalid-dsn>"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEBAAI_",
        env_file=None,
        extra="ignore",
    )

    # ── Runtime ─────────────────────────────────────────────────
    env: str = "development"
    debug: bool = False
    service_name: str = "tebaai-backend"
    service_version: str = "0.1.0"
    default_language: str = "es"
    supported_languages: str = "es,en,he"

    # ── PostgreSQL ──────────────────────────────────────────────
    postgres_enabled: bool = False
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = ""
    postgres_user: str = ""
    postgres_password: SecretStr = SecretStr("")
    postgres_dsn: str = ""
    postgres_min_pool_size: int = 1
    postgres_max_pool_size: int = 10
    postgres_connect_timeout_seconds: int = 10
    postgres_application_name: str = "tebaai-backend"
    postgres_auto_migrate: bool = True

    # ── Milvus ──────────────────────────────────────────────────
    milvus_enabled: bool = False
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_uri: str = ""
    milvus_token: SecretStr = SecretStr("")
    milvus_connect_timeout_seconds: int = 10
    milvus_collection_breslov: str = "tebaai_breslov_chunks_v1"

    # ── LiteLLM ─────────────────────────────────────────────────
    litellm_enabled: bool = False
    litellm_base_url: str = "http://127.0.0.1:4000"
    litellm_api_key: SecretStr = SecretStr("")
    litellm_default_model_alias: str = ""
    litellm_timeout_seconds: int = 60

    # ── Embeddings ───────────────────────────────────────────────
    embeddings_enabled: bool = False
    embeddings_provider: str = "litellm"
    embeddings_base_url: str = "http://127.0.0.1:4000"
    embeddings_api_key: SecretStr = SecretStr("")
    embeddings_model_alias: str = "openai_text_embedding_3_small"
    embeddings_dimension: int = 1536
    embeddings_batch_size: int = 16
    embeddings_timeout_seconds: int = 60

    # ── Auth ────────────────────────────────────────────────────
    auth_enabled: bool = False
    auth_jwt_secret: SecretStr = SecretStr("")
    auth_jwt_algorithm: str = "HS256"
    auth_access_token_ttl_minutes: int = 15
    auth_refresh_token_ttl_days: int = 30
    auth_issuer: str = "tebaai-api"
    auth_audience: str = "tebaai-web"
    auth_password_pepper: SecretStr = SecretStr("")

    @field_validator("supported_languages", mode="before")
    @classmethod
    def _normalize_supported_languages(cls, v: str) -> str:
        langs = [lang.strip() for lang in v.split(",") if lang.strip()]
        return ",".join(langs) if langs else "es"

    @model_validator(mode="after")
    def _validate_postgres(self) -> AppSettings:
        if not self.postgres_enabled:
            return self
        if self.postgres_dsn:
            return self
        if not self.postgres_db or not self.postgres_user:
            raise ValueError(
                "PostgreSQL is enabled (TEBAAI_POSTGRES_ENABLED=true) but "
                "missing required fields. Set TEBAAI_POSTGRES_DSN or provide "
                "TEBAAI_POSTGRES_DB, TEBAAI_POSTGRES_USER and "
                "TEBAAI_POSTGRES_PASSWORD."
            )
        return self

    @model_validator(mode="after")
    def _validate_auth(self) -> AppSettings:
        if not self.auth_enabled:
            return self
        if not self.auth_jwt_secret.get_secret_value():
            raise ValueError(
                "Auth is enabled (TEBAAI_AUTH_ENABLED=true) but "
                "TEBAAI_AUTH_JWT_SECRET is not set."
            )
        return self

    # ── Derived accessors ───────────────────────────────────────

    def postgres_resolved_dsn(self) -> str:
        if self.postgres_dsn:
            return self.postgres_dsn
        pw = self.postgres_password.get_secret_value()
        return (
            f"postgresql://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def postgres_dsn_display(self) -> str:
        return sanitize_dsn(self.postgres_resolved_dsn())

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",")]

    @property
    def is_development(self) -> bool:
        return self.env.strip().lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.env.strip().lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
