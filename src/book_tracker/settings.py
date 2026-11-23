"""Application settings from ``BOOK_TRACKER_*`` environment variables (research R19)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    # Spec 002: the only book-data source, and the 10 s budget per member request
    # (FR-016). Requests identify only the app; there is no contact setting (Principle IX).
    openlibrary_base_url: str = "https://openlibrary.org"
    source_timeout_seconds: float = 10.0
    # Spec 012: AI summary drafts. Without a key, drafting reports "not set up" (AC-09).
    anthropic_api_key: SecretStr | None = None
    ai_model: str = "claude-opus-5-5"
    ai_daily_draft_limit: int = Field(default=10, ge=1)
    ai_timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("database_url must be a PostgreSQL URL")
        # One driver (psycopg 3) for the async app and sync migrations (research R5).
        return value.replace("postgresql://", "postgresql+psycopg://", 1)

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        """Compose passes an unset variable as an empty string: no key (spec 012)."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

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
