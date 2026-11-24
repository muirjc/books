"""books-cay: a book removed from every list still holds its number in the series.

The catalog book stays when it leaves a list (constitution Principle I: removing a book
MUST NOT delete the catalog book), so its number stays taken. The fix makes that book
reachable: the conflict links to the book holding the number, and the series page lists
every catalog book in the series.
"""

from __future__ import annotations

import html
import re
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
    # Opens in a new tab, so what was typed here isn't lost, and says so.
    link = re.search(rf'<a [^>]*href="/catalog/books/{dresden["rites"]}/edit"[^>]*>', page.text)
    assert link and 'target="_blank"' in link.group(0) and 'rel="noopener"' in link.group(0)
    assert "(opens in a new tab)" in text
    assert "To swap two books' numbers, clear one of them first." in text


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


def _listed(page: str) -> list[str]:
    body = page.split('<ol class="book-list series-list" role="list">', 1)[1].split("</ol>")[0]
    return [html.unescape(t) for t in re.findall(r'class="book-title"[^>]*>([^<]*)<', body)]


async def test_series_page_lists_every_catalog_book_in_the_series(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    ben = await factory.user("ben", display_name="Ben")
    guilty = await factory.book(
        "Proven Guilty", ben, author_ids=[dresden["author"]], series_id=dresden["series"],
        series_number="8",
    )  # fmt: skip
    await factory.entry(ben, guilty)  # only on Ben's list
    for title in ("Side Jobs", "Brief Cases"):  # no number: last, by title
        await factory.book(title, alice, series_id=dresden["series"])
    page = await member.get(f"/catalog/series/{dresden['series']}/edit")
    assert page.status_code == 200
    text = html.unescape(page.text)
    assert "Books in this series" in text
    # Blood Rites is on nobody's list and Proven Guilty only on Ben's: both listed.
    assert _listed(page.text) == [
        "Storm Front", "Blood Rites", "Proven Guilty", "Brief Cases", "Side Jobs"
    ]  # fmt: skip
    assert "#5" in text and "#1" in text and "No number" in text
    for book in (dresden["rites"], dresden["storm"], guilty):
        assert f'href="/books/{book}"' in page.text  # spec 016 AC-07: the book page


async def test_series_rename_errors_still_list_the_books(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    await factory.series("Cinder Spires", alice)
    path = f"/catalog/series/{dresden['series']}/edit"
    for name, status in (("", 422), ("Cinder Spires", 409)):
        page = await member.post(path, data={"name": name})
        assert page.status_code == status, name
        assert _listed(page.text) == ["Storm Front", "Blood Rites"], name


async def test_swapping_two_numbers_by_clearing_one_first(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    """The notice's advice works: Blood Rites #5 and Death Masks #6 swap numbers."""
    masks = await factory.book(
        "Death Masks", alice, author_ids=[dresden["author"]], series_id=dresden["series"],
        series_number="6",
    )  # fmt: skip

    async def number(book: uuid.UUID, title: str, value: str) -> int:
        data = _death_masks(dresden, value) | {"title": title}
        del data["status"]
        return (await member.post(f"/catalog/books/{book}/edit", data=data)).status_code

    assert await number(masks, "Death Masks", "5") == 409
    assert await number(masks, "Death Masks", "") == 303
    assert await number(dresden["rites"], "Blood Rites", "6") == 303
    assert await number(masks, "Death Masks", "5") == 303


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
