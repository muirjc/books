"""No app built under test can call Open Library (Principle V; research R14; task T021)."""

from __future__ import annotations

from typing import Any

import pytest

from book_tracker.main import create_app
from book_tracker.services.errors import SourceUnavailable
from book_tracker.settings import Settings
from book_tracker.sources import open_library
from book_tracker.sources.base import UnavailableSource
from tests.fakes import FakeBookSource

SETTINGS: dict[str, Any] = {"database_url": "postgresql://u@h/db", "secret_key": "x" * 32}


def _refuse(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("OpenLibrarySource must not be built under test")


def test_test_environment_never_builds_the_real_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(open_library.OpenLibrarySource, "__init__", _refuse)
    app = create_app(Settings(**SETTINGS, environment="test"))
    assert isinstance(app.state.book_source, UnavailableSource)


async def test_the_test_source_fails_every_call() -> None:
    with pytest.raises(SourceUnavailable):
        await UnavailableSource().search_authors("anyone")
    with pytest.raises(SourceUnavailable):
        await UnavailableSource().author_works("OL1A")


def test_a_given_source_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(open_library.OpenLibrarySource, "__init__", _refuse)
    fake = FakeBookSource()
    app = create_app(Settings(**SETTINGS, environment="test"), book_source=fake)
    assert app.state.book_source is fake


def test_production_builds_the_open_library_source() -> None:
    app = create_app(Settings(**SETTINGS, environment="production"))
    assert isinstance(app.state.book_source, open_library.OpenLibrarySource)
