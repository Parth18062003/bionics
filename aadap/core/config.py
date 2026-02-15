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
from typing import Annotated

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
        "postgresql+asyncpg://aadap:aadap@localhost:5432/aadap"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_pool_overflow: int = Field(default=5, ge=0, le=50)
    db_echo_sql: bool = False

    # ── Redis (L2: Working Memory, Tier 1) ──────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_default_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        description="Default TTL for working memory keys (seconds).",
    )
    redis_max_connections: int = Field(default=20, ge=1, le=200)

    # ── Logging & Observability ──────────────────────────────────────────
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = "json"  # "json" or "console"

    # ── Correlation ──────────────────────────────────────────────────────
    correlation_id_header: str = "X-Correlation-ID"

    # ── Server ───────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Cached so environment is read exactly once per process lifetime.
    Call ``get_settings.cache_clear()`` in tests to reset.
    """
    return Settings()
