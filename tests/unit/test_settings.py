"""Settings for the Open Library source (spec 002 FR-016; research R2; task T018)."""

from __future__ import annotations

import pytest

from book_tracker.settings import Settings

BASE = {"database_url": "postgresql://u@h/db", "secret_key": "x" * 32}


def test_open_library_defaults() -> None:
    settings = Settings(**BASE)  # type: ignore[arg-type]  # pydantic converts str to SecretStr
    assert settings.openlibrary_base_url == "https://openlibrary.org"
    assert settings.source_timeout_seconds == 10.0
    assert not hasattr(settings, "openlibrary_contact")  # no contact address (Principle IX)


def test_open_library_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOK_TRACKER_DATABASE_URL", BASE["database_url"])
    monkeypatch.setenv("BOOK_TRACKER_SECRET_KEY", BASE["secret_key"])
    monkeypatch.setenv("BOOK_TRACKER_OPENLIBRARY_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("BOOK_TRACKER_SOURCE_TIMEOUT_SECONDS", "2.5")
    settings = Settings()  # type: ignore[call-arg]  # values come from the environment
    assert settings.openlibrary_base_url == "http://127.0.0.1:9"
    assert settings.source_timeout_seconds == 2.5


@pytest.mark.ac("012/AC-09")
def test_ai_settings_defaults_and_secret() -> None:
    """Spec 012 research R1, R8: the AI is off without a key; the key never shows in repr."""
    settings = Settings(**BASE)  # type: ignore[arg-type]  # pydantic converts str to SecretStr
    assert settings.anthropic_api_key is None
    assert settings.ai_model == "claude-opus-5-5"
    assert settings.ai_daily_draft_limit == 10
    assert settings.ai_timeout_seconds == 30.0
    keyed = Settings(**BASE, anthropic_api_key="sk-test-secret")  # type: ignore[arg-type]
    assert "sk-test-secret" not in repr(keyed)
    assert keyed.anthropic_api_key is not None
    assert keyed.anthropic_api_key.get_secret_value() == "sk-test-secret"


@pytest.mark.ac("012/AC-09")
def test_blank_ai_key_means_not_set_up() -> None:
    """Compose passes an unset variable as an empty string: that is no key at all."""
    for blank in ("", "   "):
        settings = Settings(**BASE, anthropic_api_key=blank)  # type: ignore[arg-type]
        assert settings.anthropic_api_key is None
