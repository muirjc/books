"""Application settings from ``BOOK_TRACKER_*`` environment variables (research R19)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOOK_TRACKER_", extra="ignore")

    database_url: str
    secret_key: SecretStr
    environment: Literal["local", "test", "production"] = "production"
    session_idle_days: int = 14
    admin_login: str | None = None
    admin_display_name: str | None = None
    admin_password: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("database_url must be a PostgreSQL URL")
        # One driver (psycopg 3) for the async app and sync migrations (research R5).
        return value.replace("postgresql://", "postgresql+psycopg://", 1)

    @field_validator("secret_key")
    @classmethod
    def _long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("secret_key must be at least 32 characters")
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
