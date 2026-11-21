"""T051: the list, add-book and entry pages."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


async def test_list_shows_entries(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Discworld", alice)
    author = await factory.author("Terry Pratchett", alice)
    book = await factory.book(
        "Mort", alice, author_ids=[author], series_id=series, series_number="4"
    )
    await factory.entry(alice, book, status="reading")
    page = await member.get("/")
    assert page.status_code == 200
    html = page.text
    assert "<h1>My books</h1>" in html
    assert "Mort" in html and "Terry Pratchett" in html
    assert "Discworld" in html and "#4" in html
    assert "Reading" in html


async def test_empty_list(member: httpx.AsyncClient) -> None:
    page = await member.get("/")
    assert "You haven't added any books yet" in page.text


@pytest.mark.ac("001/AC-03")
async def test_add_book_with_new_author_and_series(
    member: httpx.AsyncClient, factory: Factory
) -> None:
    form = await member.get("/books/add")
    assert form.status_code == 200
    for field in (
        "title",
        "author_name_0",
        "series_name",
        "series_number",
        "status",
        "finished_on",
        "notes",
        "isbn_13",
    ):
        assert re.search(rf'<label for="{field}"', form.text), field
    response = await member.post(
        "/books/add",
        data={
            "title": "Guards! Guards!",
            "author_name_0": "Terry Pratchett",
            "confirm_author_0": "Terry Pratchett",  # spec 005: a new name is confirmed
            "series_name": "Discworld",
            "confirm_series": "Discworld",
            "series_number": "8",
            "status": "finished",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/?msg=added"
    listed = await member.get("/?msg=added")
    assert "Guards! Guards!" in listed.text
    assert "Added to your list." in listed.text
    assert await factory.scalar("SELECT count(*) FROM author") == 1
    assert await factory.scalar("SELECT count(*) FROM series") == 1


@pytest.mark.ac("001/AC-03")
async def test_add_with_title_and_author_only(member: httpx.AsyncClient, factory: Factory) -> None:
    response = await member.post(
        "/books/add",
        data={
            "title": "The Hobbit",
            "author_name_0": "J.R.R. Tolkien",
            "confirm_author_0": "J.R.R. Tolkien",
        },  # spec 005: a new name is confirmed
    )
    assert response.status_code == 303
    assert await factory.scalar("SELECT series_id FROM book") is None


async def test_add_form_shows_validation_errors(
    member: httpx.AsyncClient, factory: Factory
) -> None:
    response = await member.post("/books/add", data={"title": "", "series_number": "2"})
    assert response.status_code == 422
    html = response.text
    assert 'class="error-summary"' in html
    assert "Enter a title" in html
    assert "Enter at least one author" in html
    assert "Choose a series first" in html
    assert 'aria-describedby="title-error"' in html
    assert await factory.scalar("SELECT count(*) FROM book") == 0


async def test_add_form_rolls_back_on_conflict(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Discworld", alice)
    await factory.book("Mort", alice, series_id=series, series_number="4")
    before = await factory.scalar("SELECT count(*) FROM author")
    response = await member.post(
        "/books/add",
        data={
            "title": "Not Mort",
            "author_name_0": "Brand New Author",
            "confirm_author_0": "Brand New Author",  # spec 005: a new name is confirmed
            "series_id": str(series),
            "series_name": "Discworld",  # the form sends the chosen series' name too
            "series_number": "4",
        },
    )
    assert response.status_code == 409
    assert "Another book already has this number in the series" in response.text
    # The new author created on the way was rolled back with the failed book.
    assert await factory.scalar("SELECT count(*) FROM author") == before


@pytest.mark.ac("001/AC-05")
async def test_duplicate_offers_read_again(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book)
    response = await member.post("/books/add", data={"book_id": str(book)})
    assert response.status_code == 409
    assert "Already on your list" in response.text
    assert f'action="/entries/{entry}/read-again"' in response.text
    assert "Read again" in response.text


@pytest.mark.ac("001/AC-08")
async def test_edit_entry(member: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book, status="reading")
    page = await member.get(f"/entries/{entry}")
    assert page.status_code == 200
    for field in ("status", "finished_on", "times_read", "notes"):
        assert re.search(rf'<label for="{field}"', page.text), field
    saved = await member.post(
        f"/entries/{entry}",
        data={
            "status": "finished",
            "finished_on": "2026-03-01",
            "times_read": "3",
            "notes": "Spice must flow",
        },
    )
    assert saved.status_code == 303
    assert saved.headers["location"] == f"/entries/{entry}?msg=saved"
    shown = await member.get(saved.headers["location"])
    assert "Spice must flow" in shown.text
    assert 'value="3"' in shown.text
    assert "Saved." in shown.text


async def test_edit_entry_validation(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book)
    response = await member.post(
        f"/entries/{entry}",
        data={"status": "finished", "finished_on": "2999-01-01", "times_read": "1", "notes": ""},
    )
    assert response.status_code == 422
    assert "can't be in the future" in html.unescape(response.text)


async def test_read_again_from_entry_page(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book)
    response = await member.post(f"/entries/{entry}/read-again", data={})
    assert response.status_code == 303
    shown = await member.get(response.headers["location"])
    assert "Started a re-read." in shown.text
    assert await factory.scalar("SELECT status FROM reading_entry") == "reading"


@pytest.mark.ac("001/AC-07")
async def test_remove_asks_for_confirmation(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book)
    confirm = await member.post(f"/entries/{entry}/remove", data={})
    assert confirm.status_code == 200
    assert "Remove “Dune” from your list?" in confirm.text
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 1
    removed = await member.post(f"/entries/{entry}/remove", data={"confirm": "yes"})
    assert removed.status_code == 303
    assert removed.headers["location"] == "/?msg=removed"
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 0
    assert await factory.scalar("SELECT count(*) FROM book") == 1


async def test_pages_require_sign_in(client: httpx.AsyncClient) -> None:
    for path in ("/", "/books/add"):
        response = await client.get(path)
        assert response.status_code == 303
        assert response.headers["location"] == "/sign-in"


@pytest.mark.ac("001/AC-35")
async def test_finishing_a_reread_on_the_page_counts_it(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    """The form always sends "Times read"; an unchanged value is not an edit (FR-029)."""
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book, status="reading", times_read=1)
    saved = await member.post(
        f"/entries/{entry}",
        data={"status": "finished", "finished_on": "2026-11-01", "times_read": "1", "notes": ""},
    )
    assert saved.status_code == 303
    assert await factory.scalar("SELECT times_read FROM reading_entry") == 2
    # Changing the number is still an explicit edit.
    await member.post(
        f"/entries/{entry}",
        data={"status": "finished", "finished_on": "2026-11-01", "times_read": "5", "notes": ""},
    )
    assert await factory.scalar("SELECT times_read FROM reading_entry") == 5
