"""
AADAP — Configuration Management
=================================
Centralized, validated configuration with environment-based overrides.
All settings are loaded from environment variables with sensible defaults.

Usage:
    from aadap.core.config import get_settings
    settings = get_settings()
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment. Governs autonomy policy (SYSTEM_CONSTITUTION §Autonomy Policy Matrix)."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Root configuration object.

    All values can be overridden via environment variables prefixed with ``AADAP_``.
    Example: ``AADAP_DATABASE_URL=postgresql+asyncpg://...``
    """

    model_config = SettingsConfigDict(
        env_prefix="AADAP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────────────────────
    app_name: str = "aadap"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    # ── PostgreSQL (L2: Operational Store) ───────────────────────────────
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://parth:parth1806@localhost:5432/bionic"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_pool_overflow: int = Field(default=5, ge=0, le=50)
    db_echo_sql: bool = False

    # ── In-Memory Store (L2: Working Memory, Tier 1) ─────────────────────
    memory_default_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        description="Default TTL for working memory keys (seconds).",
    )

    # Legacy Redis configuration (DEPRECATED: retained for backward compatibility)
    redis_url: str = Field(default="redis://localhost:6379/0",
                           description="DEPRECATED: unused")
    redis_default_ttl_seconds: int | None = Field(
        default=None, description="DEPRECATED: use memory_default_ttl_seconds")
    redis_max_connections: int = Field(
        default=20, ge=1, le=200, description="DEPRECATED: unused")

    def model_post_init(self, __context: Any) -> None:
        """Fallback: if memory_default_ttl_seconds is default but redis_ is set, use redis_."""
        super().model_post_init(__context)
        if self.redis_default_ttl_seconds is not None:
            # If user set AADAP_REDIS_DEFAULT_TTL_SECONDS, respect it
            self.memory_default_ttl_seconds = self.redis_default_ttl_seconds

    # ── Logging & Observability ──────────────────────────────────────────
    log_level: str = Field(
        default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = "json"  # "json" or "console"

    # ── Correlation ──────────────────────────────────────────────────────
    correlation_id_header: str = "X-Correlation-ID"

    # ── Server ───────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    # ── Azure OpenAI (L3: Integration) ────────────────────────────────────
    azure_openai_api_key: SecretStr | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_deployment_name: str | None = None
    azure_openai_embedding_deployment: str | None = None

    # ── Databricks (L3: Integration) ──────────────────────────────────────
    databricks_host: str | None = None
    databricks_warehouse_id: str | None = None
    databricks_cluster_id: str | None = None
    databricks_catalog: str | None = None
    databricks_schema: str | None = None

    # ── Microsoft Fabric (L3: Integration) ────────────────────────────────
    fabric_tenant_id: str | None = None
    fabric_client_id: str | None = None
    fabric_client_secret: SecretStr | None = None
    fabric_workspace_id: str | None = None
    fabric_lakehouse_id: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Cached so environment is read exactly once per process lifetime.
    Call ``get_settings.cache_clear()`` in tests to reset.
    """
    return Settings()
