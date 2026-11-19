"""Open Library failing changes nothing and blocks nothing else (AC-13, SC-004; T026)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from book_tracker.services.errors import SourceUnavailable
from tests.conftest import Factory
from tests.fakes import FakeBookSource
from tests.integration.import_helpers import KEY, member, stock

MESSAGE = "The book site couldn't be reached. Try again later, or add the book by hand."


@pytest.mark.ac("002/AC-13")
async def test_unreachable_site(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    book_source.error = SourceUnavailable()
    _, client = await member(factory, client_factory, "alice")

    api = await client.get("/api/v1/import/authors", params={"q": "Ann Author"})
    assert api.status_code == 503
    assert api.json() == {"code": "source_unavailable", "title": MESSAGE}

    page = await client.get("/import/authors", params={"q": "Ann Author"})
    assert page.status_code == 503
    assert "couldn&#39;t be reached" in page.text or "couldn't be reached" in page.text
    assert 'href="/books/add"' in page.text

    works = await client.get(f"/import/authors/{KEY}")
    assert works.status_code == 503

    assert await factory.scalar("SELECT count(*) FROM book") == 0
    assert await factory.scalar("SELECT count(*) FROM source_lookup_cache") == 0
    assert (await client.get("/")).status_code == 200  # the rest of the app still works
    assert (await client.get("/books/add")).status_code == 200
