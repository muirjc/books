"""Odd input to the import pages and API is refused before Open Library is asked.

PR #12 review findings 5 and 6: a blank or over-long search, an unknown status and
malformed work ids each get a 422, never a call to Open Library and never a 500.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, ui_csrf
from tests.fakes import FakeBookSource
from tests.integration.import_helpers import KEY, member, stock

# 12 × U+FDFA is 12 characters typed, 216 after NFKC; 200 × U+0390 stays 200 after NFKC
# but casefolds to 600, past the 300-character cache key.
EXPANDS_ON_NFKC = "ﷺ" * 12
EXPANDS_ON_CASEFOLD = "ΐ" * 200


@pytest.mark.parametrize("q", ["   ", "　 ", EXPANDS_ON_NFKC, EXPANDS_ON_CASEFOLD])
async def test_search_text_is_checked_after_cleaning(
    q: str,
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
    book_source: FakeBookSource,
) -> None:
    _, client = await member(factory, client_factory, "alice")
    api = await client.get("/api/v1/import/authors", params={"q": q})
    assert api.status_code == 422, api.text
    page = await client.get("/import/authors", params={"q": q})
    assert page.status_code == 422, page.text
    assert "Enter an author&#39;s name" in page.text or "Enter an author's name" in page.text
    assert book_source.calls == []
    assert await factory.scalar("SELECT count(*) FROM source_lookup_cache") == 0


async def _post(
    client: httpx.AsyncClient, path: str, data: list[tuple[str, str]]
) -> httpx.Response:
    token = await ui_csrf(client)
    return await client.post(
        path,
        content=str(httpx.QueryParams([("csrf_token", token), *data])),
        headers={"Content-Type": "application/x-www-form-urlencoded", "X-CSRF-Token": ""},
    )


async def test_confirm_page_refuses_an_unknown_status(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    sent = await _post(
        client, f"/import/authors/{KEY}", [("status", "abandoned"), ("work", "OL1W")]
    )
    assert sent.status_code == 422
    assert "Choose how to add the books" in sent.text
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 0


async def test_confirm_page_refuses_malformed_work_ids(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    sent = await _post(client, f"/import/authors/{KEY}", [("work", "OL1W"), ("work", "x' OR 1")])
    assert sent.status_code == 422
    assert "Some books aren" in sent.text
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 0


async def test_view_page_refuses_an_unknown_status(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    sent = await _post(client, f"/import/authors/{KEY}/view", [("status", "abandoned")])
    assert sent.status_code == 422
    assert "Choose how to add the books" in sent.text
