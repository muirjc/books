"""The import pages (spec 002 user story 1; contracts/ui-routes.md; T027, T028, T043)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, ui_csrf
from tests.fakes import FakeBookSource, author, listing, work
from tests.integration.import_helpers import KEY, confirm_via_page, member, stock


@pytest.mark.ac("002/AC-01")
async def test_search_page_for_any_member(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _, client = await member(factory, client_factory, "kid")  # a Member, not an Admin (FR-014)
    page = await client.get("/import")
    assert page.status_code == 200
    assert 'name="q"' in page.text
    assert 'href="/import"' in page.text  # in the main navigation


async def test_single_match_goes_straight_to_the_works(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    plain = await client.get("/import/authors", params={"q": "Ann Author"})
    assert plain.status_code == 303 and plain.headers["location"] == f"/import/authors/{KEY}"
    htmx = await client.get("/import/authors", params={"q": "Ann Author"},
                            headers={"HX-Request": "true"})  # fmt: skip
    assert htmx.headers["HX-Redirect"] == f"/import/authors/{KEY}"


@pytest.mark.ac("002/AC-01")
@pytest.mark.ac("002/AC-04")
@pytest.mark.ac("002/AC-17")
@pytest.mark.ac("002/AC-19")
async def test_works_page_shows_states_and_status_choice(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    alice, client = await member(factory, client_factory, "alice")
    ann = await factory.author("Ann Author", alice)
    mine = await factory.book("Book 1", alice, author_ids=[ann])
    await factory.entry(alice, mine)
    await factory.book("Book 2", alice, author_ids=[ann])
    page = await client.get(f"/import/authors/{KEY}")
    assert page.status_code == 200
    text = page.text
    assert "Already on your list" in text and "In the family catalog" in text
    assert 'value="OL1W"' not in text  # no checkbox for a book on my list
    assert 'value="OL2W"' in text and 'value="OL3W"' in text
    assert 'name="status" value="finished" checked' in text


@pytest.mark.ac("002/AC-02")
async def test_confirm_shows_the_summary(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    done = await confirm_via_page(client, ["OL1W", "OL2W"])
    assert done.status_code == 200
    assert "Added 2 books to your list (2 new to the family catalog)" in done.text
    assert 'aria-live="polite"' in done.text


async def test_confirm_needs_csrf_and_a_selection(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    forged = await client.post(
        f"/import/authors/{KEY}",
        data={"work": "OL1W", "status": "finished"},
        headers={"X-CSRF-Token": ""},
    )
    assert forged.status_code == 403
    token = await ui_csrf(client)
    empty = await client.post(
        f"/import/authors/{KEY}", data={"csrf_token": token, "status": "finished"},
        headers={"X-CSRF-Token": ""},
    )  # fmt: skip
    assert empty.status_code == 422
    assert "Tick at least one book" in empty.text
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 0


@pytest.mark.ac("002/AC-21")
async def test_more_than_500_on_the_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [work(n) for n in range(1, 502)])
    _, client = await member(factory, client_factory, "alice")
    refused = await confirm_via_page(client, [f"OL{n}W" for n in range(1, 502)])
    assert refused.status_code == 422
    assert "You can add up to 500 books at a time" in refused.text


@pytest.mark.ac("002/AC-23")
async def test_unknown_author_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _, client = await member(factory, client_factory, "alice")
    page = await client.get("/import/authors/OL999A")
    assert page.status_code == 404
    assert "No such author on Open Library" in page.text


@pytest.mark.ac("002/AC-07")
async def test_imported_book_shows_its_source(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await confirm_via_page(client, ["OL2W"])
    entry_id = await factory.scalar("SELECT id FROM reading_entry")
    book_id = await factory.scalar("SELECT book_id FROM reading_entry")
    link = 'href="https://openlibrary.org/works/OL2W"'
    entry = await client.get(f"/entries/{entry_id}")
    assert "Imported from Open Library" in entry.text and link in entry.text
    edit = await client.get(f"/catalog/books/{book_id}/edit")
    assert "Imported from Open Library" in edit.text and link in edit.text


_ = author  # re-exported helper used by other page tests


# --------------------------------------------------------------------------- user story 3


async def _view(client: httpx.AsyncClient, **data: object) -> httpx.Response:
    token = await ui_csrf(client)
    return await client.post(
        f"/import/authors/{KEY}/view",
        data={"csrf_token": token, **data},
        headers={"HX-Request": "true", "X-CSRF-Token": ""},
    )


@pytest.mark.ac("002/AC-10")
@pytest.mark.ac("002/AC-11")
async def test_sort_filter_and_select_all_keep_ticks(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [
        work(1, "Mist One", year=2003), work(2, "Mist Two", year=2001), work(3, "Other", year=2002),
    ])  # fmt: skip
    alice, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")

    fragment = await _view(client, sort="year", q="mist", work=["OL3W"])
    assert fragment.status_code == 200
    assert fragment.text.lstrip().startswith('<div id="import-works">')  # a fragment
    text = fragment.text
    assert text.index("Mist Two") < text.index("Mist One")  # year order
    assert "Other</label>" not in text  # filtered out, but still ticked
    selected = await _view(client, sort="year", q="mist", select="shown")
    assert 'value="OL1W" id="work-OL1W" checked' in selected.text
    assert 'value="OL2W" id="work-OL2W" checked' in selected.text

    blank = await _view(client, sort="", q="")  # blank boxes mean "not given"
    assert blank.status_code == 200 and "Other</label>" in blank.text

    done = await confirm_via_page(client, ["OL1W", "OL2W"])
    assert "Added 2 books" in done.text
    titles = await factory.scalar(
        "SELECT array_agg(b.title ORDER BY b.title) FROM reading_entry e "
        "JOIN book b ON b.id = e.book_id WHERE e.user_id = :u", u=alice.id,
    )  # fmt: skip
    assert titles == ["Mist One", "Mist Two"]


@pytest.mark.ac("002/AC-11")
async def test_select_all_ticks_at_most_500(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [work(n) for n in range(1, 601)])
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    selected = await _view(client, select="shown")
    assert selected.text.count(" checked>") == 500
    assert "Only the first 500 shown were ticked" in selected.text


@pytest.mark.ac("002/AC-20")
async def test_truncation_note(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [work(n) for n in range(1, 2001)], total=2500)
    _, client = await member(factory, client_factory, "alice")
    page = await client.get(f"/import/authors/{KEY}")
    assert "Showing the first 2,000 of 2,500 works" in page.text
    assert "add it by hand" in page.text
    api = await client.get(f"/api/v1/import/authors/{KEY}/works")
    assert api.json()["truncated"] is True and api.json()["total"] == 2500
