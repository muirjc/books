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
