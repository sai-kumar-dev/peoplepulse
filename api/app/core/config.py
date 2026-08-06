"""Typed runtime configuration for the PeoplePulse API."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional local ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PEOPLEPULSE_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    service_name: str = "peoplepulse-api"
    environment: Literal["local", "test", "development", "production", "snowflake"] = "local"
    api_version: str = "1.0.0"
    log_level: str = "INFO"
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PEOPLEPULSE_DATABASE_URL",
            "PEOPLEPULSE_ASYNC_DATABASE_URL",
            "PEOPLEPULSE_WAREHOUSE_DATABASE_URL",
            "DATABASE_URL",
        ),
    )
    warehouse_schema: str = "marts"
    query_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    database_pool_size: int = Field(default=5, ge=1, le=30)
    demo_fallback_enabled: bool = True
    minimum_reportable_group_size: int = Field(default=5, ge=1, le=50)
    admin_token: SecretStr = Field(
        default=SecretStr("demo-admin-token"),
        validation_alias=AliasChoices("PEOPLEPULSE_ADMIN_TOKEN", "ADMIN_TOKEN"),
    )
    analyst_token: SecretStr = Field(
        default=SecretStr("demo-analyst-token"),
        validation_alias=AliasChoices("PEOPLEPULSE_ANALYST_TOKEN", "ANALYST_TOKEN"),
    )

    @field_validator("warehouse_schema")
    @classmethod
    def validate_schema_identifier(cls, value: str) -> str:
        """Prevent configuration from becoming an unsafe SQL identifier."""

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("warehouse_schema must be a valid SQL identifier")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log_level is not supported")
        return normalized

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)


@lru_cache
def get_settings() -> Settings:
    """Return the immutable process-wide settings object."""

    return Settings()
