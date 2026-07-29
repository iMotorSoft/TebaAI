from __future__ import annotations

import os
import re
from functools import lru_cache
from urllib.parse import quote, urlparse, urlunparse

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CANONICAL_ENVIRONMENTS = {
    "dev": "development",
    "development": "development",
    "stg": "staging",
    "staging": "staging",
    "prod": "production",
    "production": "production",
}
_FORBIDDEN_DATABASE_NAMES = {"postgres", "team360", "v360"}
_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_$-]*$")
_WEAK_JWT_SECRETS = {"change_me", "change_me_dev_only", "dev", "secret"}


def sanitize_dsn(dsn: str) -> str:
    if not dsn:
        return ""
    try:
        parsed = urlparse(dsn)
        if parsed.password:
            netloc = parsed.hostname or ""
            if ":" in netloc:
                netloc = f"[{netloc}]"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            if parsed.username:
                netloc = f"{parsed.username}@{netloc}"
            parsed = parsed._replace(netloc=netloc)
        return urlunparse(parsed)
    except Exception:
        return "<invalid-dsn>"


# @lat: [[global-configuration-facade-policy#8. Manejo De Secretos]]
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEBAAI_",
        env_file=None,
        extra="ignore",
    )

    # ── Runtime ─────────────────────────────────────────────────
    env: str = "development"
    db_name: str = Field(
        default="tebaai",
        validation_alias=AliasChoices("TEBAAI_DB_NAME"),
    )
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

    # The primary global convention for LiteLLM auth across iMotorSoft projects
    # is LITELLM_MASTER_KEY (set in .bashrc / shell environment).
    # TebaAI-specific override: TEBAAI_LITELLM_API_KEY.
    # Resolution precedence (see _validate_litellm):
    #   1. LITELLM_MASTER_KEY (shared global)
    #   2. TEBAAI_LITELLM_API_KEY (TebaAI-specific override)

    # ── Embeddings (via LiteLLM gateway) ────────────────────────
    # TebaAI does NOT manage OpenAI keys directly.
    # LiteLLM resolves the upstream key (OpenAI_Key_JAI_query) in its config.yaml.
    # TebaAI authenticates to LiteLLM via LITELLM_API_KEY (LITELLM_MASTER_KEY).
    embeddings_enabled: bool = False
    embeddings_provider: str = "litellm"
    embeddings_base_url: str = "http://127.0.0.1:4000"
    embeddings_api_key: SecretStr = SecretStr("")
    embeddings_model_alias: str = "openai_text_embedding_3_small"
    embeddings_model_name: str = "text-embedding-3-small"
    embeddings_dimension: int = 1536
    embeddings_batch_size: int = 16
    embeddings_timeout_seconds: int = 60

    # ── Research Conversation (LiteLLM generative model) ──────────
    # Model: openai_gpt-5.4-nano (via LiteLLM gateway)
    # LiteLLM params: openai/gpt-5.4-nano with OpenAI_Key_JAI_query
    # Resolution: TEBAAI_RESEARCH_CONVERSATION_MODEL env var or default below
    research_conversation_model: str = "openai_gpt-5.4-nano"
    research_embedding_model_alias: str = "openai_text_embedding_3_small"
    breslov_productive_collection: str = "tebaai_breslov_chunks_v1"

    # ── Auth ────────────────────────────────────────────────────
    auth_enabled: bool = False
    jwt_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "TEBAAI_JWT_SECRET",
            "TEBAAI_AUTH_JWT_SECRET",
        ),
    )
    auth_jwt_algorithm: str = "HS256"
    auth_access_token_ttl_minutes: int = 15
    auth_refresh_token_ttl_days: int = 30
    auth_issuer: str = "tebaai-api"
    auth_audience: str = "tebaai-web"
    auth_pepper: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "TEBAAI_AUTH_PEPPER",
            "TEBAAI_AUTH_PASSWORD_PEPPER",
        ),
    )
    e2e_guest_password: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "TEBAAI_E2E_GUEST_PASSWORD",
            "TEBAAI_GUEST_PASSWORD",
        ),
    )

    @field_validator("env", mode="before")
    @classmethod
    def _normalize_environment(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        try:
            return _CANONICAL_ENVIRONMENTS[normalized]
        except KeyError as exc:
            allowed = ", ".join(sorted(_CANONICAL_ENVIRONMENTS))
            raise ValueError(
                f"Invalid TEBAAI_ENV. Expected one of: {allowed}."
            ) from exc

    @field_validator("db_name", mode="before")
    @classmethod
    def _validate_database_name(cls, value: str) -> str:
        name = str(value).strip()
        if not name:
            raise ValueError("TEBAAI_DB_NAME must not be empty.")
        if not _DATABASE_NAME_PATTERN.fullmatch(name):
            raise ValueError(
                "TEBAAI_DB_NAME contains unsupported characters."
            )
        if name.casefold() in _FORBIDDEN_DATABASE_NAMES:
            raise ValueError(
                "TEBAAI_DB_NAME points to a database reserved for another purpose."
            )
        return name

    @field_validator("supported_languages", mode="before")
    @classmethod
    def _normalize_supported_languages(cls, v: str) -> str:
        langs = [lang.strip() for lang in v.split(",") if lang.strip()]
        return ",".join(langs) if langs else "es"

    @model_validator(mode="after")
    def _validate_postgres(self) -> AppSettings:
        raw = {
            name: os.environ.get(name)
            for name in ("DB_PG_IP", "DB_PG_PORT", "DB_PG_USER", "DB_PG_PASS")
        }
        if all(value is None for value in raw.values()):
            self.postgres_enabled = False
            self.postgres_host = "127.0.0.1"
            self.postgres_port = 5432
            self.postgres_db = self.db_name
            self.postgres_user = ""
            self.postgres_password = SecretStr("")
            if self.is_production:
                raise ValueError(
                    "Production PostgreSQL configuration requires "
                    "DB_PG_IP, DB_PG_USER and DB_PG_PASS."
                )
            return self

        host = (raw["DB_PG_IP"] or "").strip()
        user = raw["DB_PG_USER"] or ""
        password = raw["DB_PG_PASS"] or ""
        port_text = (raw["DB_PG_PORT"] or "5432").strip()

        if not host:
            raise ValueError("DB_PG_IP is required when PostgreSQL is configured.")
        if any(char.isspace() for char in host) or any(
            char in host for char in "/?#@"
        ):
            raise ValueError("DB_PG_IP is not a valid host or IP address.")
        if not user:
            raise ValueError("DB_PG_USER is required when PostgreSQL is configured.")
        if not password:
            raise ValueError(
                "DB_PG_PASS is required when PostgreSQL is configured; "
                "no password fallback is available."
            )
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("DB_PG_PORT must be an integer.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("DB_PG_PORT must be between 1 and 65535.")

        self.postgres_enabled = True
        self.postgres_host = host.removeprefix("[").removesuffix("]")
        self.postgres_port = port
        self.postgres_db = self.db_name
        self.postgres_user = user
        self.postgres_password = SecretStr(password)
        return self

    @model_validator(mode="after")
    def _validate_auth(self) -> AppSettings:
        jwt_secret = self.jwt_secret.get_secret_value()
        if self.is_production and not jwt_secret:
            raise ValueError("TEBAAI_JWT_SECRET is required in production.")
        if self.is_production and jwt_secret.strip().casefold() in _WEAK_JWT_SECRETS:
            raise ValueError("TEBAAI_JWT_SECRET is not safe for production.")
        if self.auth_enabled and not jwt_secret:
            raise ValueError(
                "Auth is enabled (TEBAAI_AUTH_ENABLED=true) but "
                "TEBAAI_JWT_SECRET is not set."
            )
        if self.is_production and self.postgres_auto_migrate:
            raise ValueError(
                "TEBAAI_POSTGRES_AUTO_MIGRATE must be false in production."
            )
        return self

    @model_validator(mode="after")
    def _validate_litellm(self) -> AppSettings:
        """Resolve LiteLLM API key from global conventions.

        Precedence:
          1. LITELLM_MASTER_KEY — shared global convention across iMotorSoft projects.
          2. TEBAAI_LITELLM_API_KEY — TebaAI-specific override if explicitly set.

        This mirrors the _validate_postgres pattern that resolves DB_PG_* vars.
        """
        if self.litellm_api_key.get_secret_value():
            return self
        master_key = os.environ.get("LITELLM_MASTER_KEY", "").strip()
        if master_key:
            self.litellm_api_key = SecretStr(master_key)
            return self
        tebaai_key = os.environ.get("TEBAAI_LITELLM_API_KEY", "").strip()
        if tebaai_key:
            self.litellm_api_key = SecretStr(tebaai_key)
            return self
        return self

    # ── Derived accessors ───────────────────────────────────────

    def postgres_resolved_dsn(self) -> str:
        """Return the canonical Psycopg/psql PostgreSQL URL."""
        return self._build_postgres_url("postgresql")

    def sqlalchemy_postgres_url(self) -> str:
        """Return the canonical SQLAlchemy URL using the Psycopg 3 dialect."""
        return self._build_postgres_url("postgresql+psycopg")

    def _build_postgres_url(self, scheme: str) -> str:
        if not self.postgres_enabled:
            return ""
        user = quote(self.postgres_user, safe="")
        pw = self.postgres_password.get_secret_value()
        password = quote(pw, safe="")
        host = self.postgres_host
        if ":" in host:
            host = f"[{host}]"
        return (
            f"{scheme}://{user}:{password}"
            f"@{host}:{self.postgres_port}/{quote(self.postgres_db, safe='')}"
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
        return self.env == "production"

    @property
    def auth_jwt_secret(self) -> SecretStr:
        """Compatibility accessor for existing auth consumers."""
        return self.jwt_secret

    @property
    def auth_password_pepper(self) -> SecretStr:
        """Compatibility accessor for existing password consumers."""
        return self.auth_pepper

    @property
    def guest_password(self) -> SecretStr:
        """Compatibility accessor for the guest provisioning script."""
        return self.e2e_guest_password


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
