"""``book_tracker.main:app`` exists for uvicorn and the container entrypoint (T042)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from book_tracker import main
from book_tracker.settings import get_settings
from tests.conftest import TEST_SECRET


def test_module_app_is_built_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOK_TRACKER_DATABASE_URL", "postgresql://u@localhost/db")
    monkeypatch.setenv("BOOK_TRACKER_SECRET_KEY", TEST_SECRET)
    get_settings.cache_clear()
    monkeypatch.delitem(vars(main), "app", raising=False)
    try:
        app = main.app
        assert isinstance(app, FastAPI)
        assert main.app is app  # built once
        assert app.state.settings.environment == "production"  # the safe default
    finally:
        vars(main).pop("app", None)
        get_settings.cache_clear()


def test_unknown_attribute() -> None:
    with pytest.raises(AttributeError):
        main.not_a_thing  # noqa: B018


@pytest.mark.ac("012/AC-09")
def test_summary_generator_wiring() -> None:
    """Spec 012 R9: Claude only with a key outside tests; otherwise 'not set up'."""
    from book_tracker.settings import Settings
    from book_tracker.sources.claude import ClaudeSummaryGenerator
    from book_tracker.sources.summary_generator import UnconfiguredGenerator

    base = {"database_url": "postgresql://u@localhost/db", "secret_key": TEST_SECRET}
    plain = main.create_app(Settings(**base))  # type: ignore[arg-type]  # str to SecretStr
    assert isinstance(plain.state.summary_generator, UnconfiguredGenerator)
    keyed = Settings(**base, anthropic_api_key="sk-test")  # type: ignore[arg-type]
    assert isinstance(main.create_app(keyed).state.summary_generator, ClaudeSummaryGenerator)
    test_env = Settings(**base, anthropic_api_key="sk-test", environment="test")  # type: ignore[arg-type]
    assert isinstance(main.create_app(test_env).state.summary_generator, UnconfiguredGenerator)
    fake = UnconfiguredGenerator()
    assert main.create_app(keyed, summary_generator=fake).state.summary_generator is fake


async def test_the_ai_client_is_closed_on_shutdown() -> None:
    """PR #32 review: the app closes the Anthropic client it created."""
    from book_tracker.settings import Settings

    base = {"database_url": "postgresql://u@localhost/db", "secret_key": TEST_SECRET}
    keyed = main.create_app(Settings(**base, anthropic_api_key="sk-test"))  # type: ignore[arg-type]
    generator = keyed.state.summary_generator
    async with keyed.router.lifespan_context(keyed):
        assert not generator.closed
    assert generator.closed
