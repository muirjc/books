"""Spec 009 US2: stories on the series page, with only the viewer's own reading (T011)."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from datetime import date

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def ben(factory: Factory) -> TestUser:
    return await factory.user("ben", display_name="Ben")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture
async def other(
    ben: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), ben)


@pytest.fixture
async def dresden(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    """The spec's example: Storm Front #1, Fool Moon #2, and Side Jobs (in the series, no
    number) holding #1.5, #2.5 and #6.5. Alice finished Storm Front and Side Jobs and is
    reading Fool Moon."""
    butcher = await factory.author("Jim Butcher", alice)
    series = await factory.series("The Dresden Files", alice)
    ids = {"butcher": butcher, "series": series}
    ids["storm"] = await factory.book(
        "Storm Front", alice, author_ids=[butcher], series_id=series, series_number="1"
    )
    ids["fool"] = await factory.book(
        "Fool Moon", alice, author_ids=[butcher], series_id=series, series_number="2"
    )
    ids["side_jobs"] = await factory.book(
        "Side Jobs", alice, author_ids=[butcher], series_id=series
    )
    for title, number in (
        ("Restoration of Faith", "1.5"),
        ("Publicity and Advertising", "2.5"),
        ("Something Borrowed", "6.5"),
    ):
        ids[number] = await factory.story(
            title, alice, series_id=series, series_number=number, author_ids=[butcher],
            book_ids=[ids["side_jobs"]],
        )  # fmt: skip
    ids["storm_entry"] = await factory.entry(alice, ids["storm"], finished_on=date(2025, 3, 3))
    ids["fool_entry"] = await factory.entry(alice, ids["fool"], status="reading")
    ids["side_entry"] = await factory.entry(alice, ids["side_jobs"], finished_on=date(2025, 9, 1))
    return ids


def rows(page: httpx.Response) -> list[str]:
    found = re.search(r'<ol class="book-list series-rows"[^>]*>(.*?)</ol>', page.text, re.S)
    assert found, page.text
    return [
        " ".join(html.unescape(re.sub(r"<[^>]+>", " ", item)).split())
        for item in re.findall(r"<li\b[^>]*>(.*?)</li>", found.group(1), re.S)
    ]


def text_of(page: httpx.Response) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page.text)).split())


@pytest.mark.ac("009/AC-09")
@pytest.mark.ac("009/AC-11")
@pytest.mark.ac("009/AC-12")
@pytest.mark.ac("009/AC-14")
async def test_the_spec_example(member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]) -> None:
    page = await member.get(f"/series/{dresden['series']}")
    assert page.status_code == 200
    assert rows(page) == [
        "#1 Storm Front Jim Butcher · Finished · 3 Mar 2025",
        "#1.5 Story Restoration of Faith In Side Jobs · Finished · 1 Sep 2025",
        "#2 Fool Moon Jim Butcher · Reading",
        "#2.5 Story Publicity and Advertising In Side Jobs · Finished · 1 Sep 2025",
        "#3–#6 Not in the family catalog yet Add #3",
        "#6.5 Story Something Borrowed In Side Jobs · Finished · 1 Sep 2025",
        "No number Side Jobs Jim Butcher · Finished · 1 Sep 2025 · Contains #1.5, #2.5, #6.5",
    ]
    # The containing book links to my entry.
    assert f'<a href="/entries/{dresden["side_entry"]}">Side Jobs</a>' in page.text


@pytest.mark.ac("009/AC-10")
async def test_story_and_book_share_a_number(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    await factory.execute("UPDATE story SET series_number = 2 WHERE id = :id", id=dresden["2.5"])
    found = rows(await member.get(f"/series/{dresden['series']}"))
    assert found[2].startswith("#2 Fool Moon") and found[3].startswith("#2 Story Publicity")


@pytest.mark.ac("009/AC-13")
async def test_progress_mentions_stories(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    page = await member.get(f"/series/{dresden['series']}")
    assert "You've finished 2 of 3 books and 3 of 3 stories in this series." in text_of(page)
    await factory.execute("DELETE FROM book_story")
    await factory.execute("DELETE FROM story")
    page = await member.get(f"/series/{dresden['series']}")
    assert "You've finished 2 of 3 books in this series." in text_of(page)


@pytest.mark.ac("009/AC-15")
@pytest.mark.ac("009/AC-11")
async def test_other_members_reading_never_shows(
    other: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    """Alice finished Side Jobs; Ben hasn't got it. His story rows say Not on my list, with
    an Add link per containing book, and nothing of Alice's shows."""
    page = await other.get(f"/series/{dresden['series']}")
    found = rows(page)
    assert found[1] == (
        "#1.5 Story Restoration of Faith In Side Jobs · Not on my list Add “Side Jobs” to my list"
    )
    assert "Finished" not in page.text and "Reading" not in " ".join(found)
    assert "/entries/" not in page.text
    assert (
        f'href="/books/add?book={dresden["side_jobs"]}&amp;from_series={dresden["series"]}"'
        in page.text
    )
    assert "You've finished 0 of 3 books and 0 of 3 stories in this series." in text_of(page)


async def test_containing_book_outside_the_series(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    """A collection in no series (or another one) still gives its stories their place, and
    my entry for it counts."""
    anthology = await factory.book("Dangerous Women", alice)
    await factory.story(
        "Bombshells", alice, series_id=dresden["series"], series_number="7.5",
        author_ids=[dresden["butcher"]], book_ids=[anthology],
    )  # fmt: skip
    found = rows(await member.get(f"/series/{dresden['series']}"))
    assert (
        "#7.5 Story Bombshells In Dangerous Women · Not on my list Add “Dangerous Women” to my list"
        in found
    )
    await factory.entry(alice, anthology, status="want_to_read")
    found = rows(await member.get(f"/series/{dresden['series']}"))
    assert "#7.5 Story Bombshells In Dangerous Women · Want to read" in found
