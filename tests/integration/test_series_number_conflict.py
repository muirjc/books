"""books-cay: a book removed from every list still holds its number in the series.

The catalog book stays when it leaves a list (constitution Principle I: removing a book
MUST NOT delete the catalog book), so its number stays taken. The fix makes that book
reachable: the conflict links to the book holding the number, and the series page lists
every catalog book in the series.
"""

from __future__ import annotations

import html
import uuid
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


@pytest.fixture
async def dresden(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    """Blood Rites wrongly numbered 5, on nobody's list (the reported case)."""
    author = await factory.author("Jim Butcher", alice)
    series = await factory.series("The Dresden Files", alice)
    storm = await factory.book(
        "Storm Front", alice, author_ids=[author], series_id=series, series_number="1"
    )
    rites = await factory.book(
        "Blood Rites", alice, author_ids=[author], series_id=series, series_number="5"
    )
    await factory.entry(alice, storm)
    return {"author": author, "series": series, "rites": rites, "storm": storm}


def _death_masks(ids: dict[str, uuid.UUID], number: str = "5") -> dict[str, str]:
    return {
        "title": "Death Masks",
        "author_id_0": str(ids["author"]),
        "author_name_0": "Jim Butcher",
        "series_id": str(ids["series"]),
        "series_name": "The Dresden Files",
        "series_number": number,
        "status": "finished",
    }


def _edit_link(book: uuid.UUID) -> str:
    return f'href="/catalog/books/{book}/edit"'


async def test_add_book_conflict_links_to_the_book_holding_the_number(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    page = await member.post("/books/add", data=_death_masks(dresden))
    assert page.status_code == 409
    text = html.unescape(page.text)
    assert "Another book already has this number in the series" in text
    assert _edit_link(dresden["rites"]) in page.text
    assert "Change the number of “Blood Rites”" in text


async def test_edit_pages_conflict_links_to_the_book_holding_the_number(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    masks = await factory.book("Death Masks", alice, author_ids=[dresden["author"]])
    entry = await factory.entry(alice, masks)
    data = _death_masks(dresden)
    for path in (f"/catalog/books/{masks}/edit", f"/entries/{entry}"):
        page = await member.post(path, data=data)
        assert page.status_code == 409, path
        assert _edit_link(dresden["rites"]) in page.text, path


async def test_series_page_lists_every_catalog_book_in_the_series(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    page = await member.get(f"/catalog/series/{dresden['series']}/edit")
    assert page.status_code == 200
    text = html.unescape(page.text)
    assert "Books in this series" in text
    # Blood Rites is on nobody's list, but still listed and reachable, in number order.
    assert text.index("Storm Front") < text.index("Blood Rites")
    assert "#5" in text and "#1" in text
    assert _edit_link(dresden["rites"]) in page.text
    assert _edit_link(dresden["storm"]) in page.text


async def test_renumbering_the_held_book_frees_the_number(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    fixed = await member.post(
        f"/catalog/books/{dresden['rites']}/edit",
        data={
            "title": "Blood Rites",
            "author_id_0": str(dresden["author"]),
            "author_name_0": "Jim Butcher",
            "series_id": str(dresden["series"]),
            "series_name": "The Dresden Files",
            "series_number": "6",
        },
    )
    assert fixed.status_code == 303
    added = await member.post("/books/add", data=_death_masks(dresden))
    assert added.status_code == 303
    assert (await factory.scalar("SELECT series_number FROM book WHERE title = 'Death Masks'")) == 5
