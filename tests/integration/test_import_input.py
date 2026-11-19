"""Odd input to the import pages and API is refused before Open Library is asked.

PR #12 review findings 5 and 6: a blank or over-long search, an unknown status and
malformed work ids each get a 422, never a call to Open Library and never a 500.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from book_tracker.services.errors import SourceUnavailable
from tests.conftest import Factory, ui_csrf
from tests.fakes import FakeBookSource, author, listing, work
from tests.integration.import_helpers import KEY, member, stock
from tests.integration.test_import_pages import submitted

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


# --------------------------------------------------------------------------- second review


async def test_search_with_a_nul_character(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """Finding 3: PostgreSQL refuses NUL, so it is dropped rather than causing a 500."""
    book_source.authors["annauthor"] = [author(KEY, "Ann Author")]
    _, client = await member(factory, client_factory, "alice")
    api = await client.get("/api/v1/import/authors", params={"q": "ann\x00author"})
    assert api.status_code == 200, api.text
    page = await client.get("/import/authors", params={"q": "ann\x00author"})
    assert page.status_code in (200, 303), page.text


@pytest.mark.parametrize("path", [f"/import/authors/{KEY}", f"/import/authors/{KEY}/view"])
async def test_work_id_with_a_trailing_newline(
    path: str,
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
    book_source: FakeBookSource,
) -> None:
    """Finding 2: Python's ``$`` matches before a final newline; Pydantic's does not."""
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    sent = await _post(client, path, [("work", "OL1W\n")])
    assert sent.status_code == 422, sent.text
    assert "OL1W\n" not in submitted(sent.text)


async def test_author_key_with_a_trailing_newline(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """Finding 6: refused before Open Library or the import lock."""
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    assert (await client.get("/import/authors/OL1A%0A")).status_code == 404
    sent = await _post(client, "/import/authors/OL1A%0A", [("work", "OL1W")])
    assert sent.status_code == 404
    assert book_source.calls == []


async def test_a_stale_tick_does_not_get_stuck(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """Finding 1: an id that isn't in the list is dropped from the redisplayed form."""
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    refused = await _post(client, f"/import/authors/{KEY}", [("work", "OL1W"), ("work", "OL99W")])
    assert refused.status_code == 422
    assert submitted(refused.text) == ["OL1W"]
    again = await _post(
        client, f"/import/authors/{KEY}", [("work", k) for k in submitted(refused.text)]
    )
    assert again.status_code == 200 and "Added 1 book" in again.text


async def test_a_merged_id_is_accepted(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """Finding 1: a tick on an id Open Library has since merged adds the merged work."""
    book_source.works[KEY] = listing(KEY, [work(2, "Merged", aliases=("OL1W",)), work(3)])
    _, client = await member(factory, client_factory, "alice")
    view = await _post(client, f"/import/authors/{KEY}/view", [("work", "OL1W"), ("q", "Book")])
    assert view.status_code == 200
    assert submitted(view.text) == ["OL2W"]  # hidden, as the work OL1W was merged into
    sent = await _post(client, f"/import/authors/{KEY}", [("work", "OL1W"), ("work", "OL2W")])
    assert sent.status_code == 200, sent.text
    assert "Added 1 book" in sent.text
    titles = await factory.scalar("SELECT array_agg(b.title) FROM reading_entry e "
                                  "JOIN book b ON b.id = e.book_id")  # fmt: skip
    assert titles == ["Merged"]


async def _age_cache(factory: Factory, hours: float) -> None:
    await factory.execute(
        "UPDATE source_lookup_cache SET fetched_at = fetched_at - make_interval(secs => :s), "
        "expires_at = expires_at - make_interval(secs => :s)", s=hours * 3600,
    )  # fmt: skip


async def test_refresh_failure_falls_back_to_the_cache(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """Finding 5: in the cache's last hour, Open Library being down doesn't break the page."""
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    await _age_cache(factory, 23.5)
    book_source.error = SourceUnavailable()
    page = await client.get(f"/import/authors/{KEY}")
    assert page.status_code == 200
    token = await ui_csrf(client)
    fragment = await client.post(
        f"/import/authors/{KEY}/view", data={"csrf_token": token, "sort": "year"},
        headers={"HX-Request": "true", "X-CSRF-Token": ""},
    )  # fmt: skip
    assert fragment.status_code == 200
    assert fragment.text.lstrip().startswith('<div id="import-works">')


async def test_htmx_view_error_reloads_the_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """Finding 5: HTMX drops 4xx/5xx responses, so an error sends the browser to the page."""
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    await _age_cache(factory, 48)
    book_source.error = SourceUnavailable()
    token = await ui_csrf(client)
    sent = await client.post(
        f"/import/authors/{KEY}/view", data={"csrf_token": token, "q": "Book"},
        headers={"HX-Request": "true", "X-CSRF-Token": ""},
    )  # fmt: skip
    assert sent.status_code == 200
    assert sent.headers["HX-Redirect"] == f"/import/authors/{KEY}?q=Book"
