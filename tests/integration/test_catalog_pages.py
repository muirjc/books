"""T082: catalog edit pages and the type-ahead markup (FR-009, FR-014, FR-030)."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.mark.ac("001/AC-32")
async def test_edit_book_page(member: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    ben = await factory.user("ben", display_name="Ben")
    author = await factory.author("Terry Pratchett", alice)
    book = await factory.book("Mortt", ben, author_ids=[author])
    page = await member.get(f"/catalog/books/{book}/edit")
    assert page.status_code == 200
    for field in ("title", "author_name_0", "series_name", "series_number", "isbn_13"):
        assert re.search(rf'<label for="{field}"', page.text), field
    assert "Last edited by Ben" in page.text
    saved = await member.post(
        f"/catalog/books/{book}/edit",
        data={
            "title": "Mort",
            "author_name_0": "Terry Pratchett",
            "author_id_0": str(author),
            "series_name": "Discworld",
            "confirm_series": "Discworld",  # spec 005: a new name is confirmed
            "series_number": "4",
        },
    )
    assert saved.status_code == 303
    shown = await member.get(saved.headers["location"])
    assert "Last edited by Alice" in shown.text
    assert 'value="Mort"' in shown.text
    assert await factory.scalar("SELECT count(*) FROM series") == 1


async def test_edit_book_errors(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Discworld", alice)
    await factory.book("Mort", alice, series_id=series, series_number="4")
    book = await factory.book("Sourcery", alice)
    invalid = await member.post(
        f"/catalog/books/{book}/edit", data={"title": "", "author_name_0": ""}
    )
    assert invalid.status_code == 422
    assert "Enter a title" in invalid.text
    taken = await member.post(
        f"/catalog/books/{book}/edit",
        data={
            "title": "Sourcery",
            "author_name_0": "Terry Pratchett",
            "confirm_author_0": "Terry Pratchett",  # spec 005: a new name is confirmed
            "series_id": str(series),
            "series_name": "Discworld",
            "series_number": "4",
        },
    )
    assert taken.status_code == 409
    assert "Another book already has this number in the series" in taken.text
    assert await factory.scalar("SELECT count(*) FROM author WHERE name = 'Terry Pratchett'") == 0


@pytest.mark.ac("001/AC-17")
@pytest.mark.ac("001/AC-18")
async def test_edit_author_page(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    author = await factory.author("Robert Galbraith", alice)
    page = await member.get(f"/catalog/authors/{author}/edit")
    assert page.status_code == 200
    assert re.search(r'<input[^>]*id="is_pen_name"[^>]*type="checkbox"', page.text)
    assert re.search(r'<input[^>]*id="real_name"[^>]*disabled', page.text)
    refused = await member.post(
        f"/catalog/authors/{author}/edit",
        data={
            "name": "Robert Galbraith",
            "sort_name": "Galbraith, Robert",
            "real_name": "J.K. Rowling",
        },
    )
    assert refused.status_code == 422
    assert "Mark the author as a pen name first" in html.unescape(refused.text)
    saved = await member.post(
        f"/catalog/authors/{author}/edit",
        data={
            "name": "Robert Galbraith",
            "sort_name": "Galbraith, Robert",
            "is_pen_name": "on",
            "real_name": "J.K. Rowling",
        },
    )
    assert saved.status_code == 303
    shown = await member.get(saved.headers["location"])
    assert 'value="J.K. Rowling"' in shown.text
    assert "Last edited by Alice" in shown.text
    assert "Saved." in shown.text


async def test_edit_series_page(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Discwrold", alice)
    await factory.series("Discworld Novels", alice)
    page = await member.get(f"/catalog/series/{series}/edit")
    assert "Last edited by Alice" in page.text
    taken = await member.post(f"/catalog/series/{series}/edit", data={"name": "discworld novels"})
    assert taken.status_code == 409
    assert "already in the catalog" in taken.text
    saved = await member.post(f"/catalog/series/{series}/edit", data={"name": "Discworld"})
    assert saved.status_code == 303


async def test_unknown_catalog_pages(member: httpx.AsyncClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    for kind in ("books", "authors", "series"):
        assert (await member.get(f"/catalog/{kind}/{missing}/edit")).status_code == 404


async def test_combobox_markup(member: httpx.AsyncClient) -> None:
    page = (await member.get("/books/add")).text
    for field in ("title", "author_name_0", "series_name"):
        tag = re.search(rf'<input[^>]*id="{field}"[^>]*>', page, re.S)
        assert tag, field
        markup = tag.group(0)
        assert 'role="combobox"' in markup
        assert f'aria-controls="{field}-listbox"' in markup
        assert 'aria-autocomplete="list"' in markup
        assert 'aria-expanded="false"' in markup
    listing = (await member.get("/suggest/books", params={"q": "x"})).text
    assert 'role="listbox"' in listing
    assert 'role="status"' in listing
