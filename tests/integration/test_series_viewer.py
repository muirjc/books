"""Spec 006: the series page shows every catalog book in the series with my own status,
gaps in the numbering, and Add links that come back to the series."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select

from book_tracker.persistence import models
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


TITLES = {
    "1": "Storm Front", "2": "Fool Moon", "3": "Grave Peril", "4": "Summer Knight",
    "5": "Death Masks", "6.5": "Backup",
}  # fmt: skip


@pytest.fixture
async def dresden(factory: Factory, alice: TestUser, ben: TestUser) -> dict[str, uuid.UUID]:
    """#1–#5, #6.5 and an unnumbered "Side Jobs". Alice: #1 and #2 Finished, #5 Reading.
    Ben: #4 Finished on a date Alice never sees."""
    author = await factory.author("Jim Butcher", alice)
    series = await factory.series("The Dresden Files", alice)
    ids: dict[str, uuid.UUID] = {"author": author, "series": series}
    for number, title in TITLES.items():
        ids[number] = await factory.book(
            title, alice, author_ids=[author], series_id=series, series_number=number
        )
    ids["side"] = await factory.book("Side Jobs", alice, author_ids=[author], series_id=series)
    ids["e1"] = await factory.entry(alice, ids["1"], finished_on=date(2025, 3, 3))
    ids["e2"] = await factory.entry(alice, ids["2"])
    ids["e5"] = await factory.entry(alice, ids["5"], status="reading")
    ids["ben4"] = await factory.entry(ben, ids["4"], finished_on=date(2024, 7, 19))
    return ids


def rows(page: httpx.Response) -> list[str]:
    """The text of each series row, whitespace collapsed."""
    body = page.text.split('<ol class="book-list series-rows"', 1)[1].split("</ol>", 1)[0]
    items = re.findall(r"<li[^>]*>(.*?)</li>", body, flags=re.S)
    return [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", item)).split()) for item in items]


def text(page: httpx.Response) -> str:
    """The page's text; tags are dropped without adding spaces, so inline links read on."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", page.text)).split())


async def counts(factory: Factory) -> tuple[int, int]:
    async with factory._app.state.db.sessionmaker() as session:
        books = await session.scalar(select(func.count()).select_from(models.Book))
        entries = await session.scalar(select(func.count()).select_from(models.ReadingEntry))
    return int(books or 0), int(entries or 0)


# --------------------------------------------------------------------------- US1


@pytest.mark.ac("006/AC-01")
async def test_every_catalog_book_in_order(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    page = await member.get(f"/series/{dresden['series']}")
    assert page.status_code == 200
    titles = [row for row in rows(page) if "Not in the family catalog yet" not in row]
    expected = [*TITLES.values(), "Side Jobs"]
    assert len(titles) == len(expected)
    for row, title in zip(titles, expected, strict=True):
        assert title in row, (row, title)


@pytest.mark.ac("006/AC-02")
async def test_my_status_and_link(member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]) -> None:
    page = await member.get(f"/series/{dresden['series']}")
    by_title = {title: row for row in rows(page) for title in TITLES.values() if title in row}
    assert "#1 Storm Front" in by_title["Storm Front"]
    assert "Jim Butcher" in by_title["Storm Front"]
    assert "Finished · 3 Mar 2025" in by_title["Storm Front"]
    assert by_title["Fool Moon"].endswith("Finished")
    assert by_title["Death Masks"].endswith("Reading")
    assert f'href="/entries/{dresden["e1"]}"' in page.text
    assert f'href="/entries/{dresden["e5"]}"' in page.text


@pytest.mark.ac("006/AC-03")
async def test_others_reading_is_private(
    member: httpx.AsyncClient, other: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    """SC-003: nothing of Ben's shows on Alice's page, and the other way round."""
    page = await member.get(f"/series/{dresden['series']}")
    knight = next(row for row in rows(page) if "Summer Knight" in row)
    assert "Not on my list" in knight and "Finished" not in knight
    assert "Ben" not in text(page) and "19 Jul 2024" not in text(page)
    assert str(dresden["ben4"]) not in page.text
    assert "You've finished 2 of 7 books" in text(page)

    theirs = await other.get(f"/series/{dresden['series']}")
    by = {title: row for row in rows(theirs) for title in TITLES.values() if title in row}
    assert "Finished · 19 Jul 2024" in by["Summer Knight"]
    for title in ("Storm Front", "Fool Moon", "Death Masks"):
        assert "Not on my list" in by[title], title
    assert "3 Mar 2025" not in text(theirs)
    assert "You've finished 1 of 7 books" in text(theirs)


@pytest.mark.ac("006/AC-04")
async def test_progress_line(member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]) -> None:
    page = await member.get(f"/series/{dresden['series']}")
    assert "You've finished 2 of 7 books in this series." in text(page)


@pytest.mark.ac("006/AC-05")
async def test_unknown_series_404(member: httpx.AsyncClient) -> None:
    assert (await member.get(f"/series/{uuid.uuid4()}")).status_code == 404
    assert (await member.get("/series/not-a-uuid")).status_code in {404, 422}


@pytest.mark.ac("006/AC-06")
async def test_empty_series(member: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    series = await factory.series("Lonely Series", alice)
    page = await member.get(f"/series/{series}")
    assert page.status_code == 200
    assert "The family catalog has no books in this series yet." in text(page)
    assert f'href="/books/add?series={series}&amp;from_series={series}"' in page.text
    assert "Add a book to this series" in text(page)


# --------------------------------------------------------------------------- US2


def add_link(book: uuid.UUID, series: uuid.UUID) -> str:
    return f'href="/books/add?book={book}&amp;from_series={series}"'


@pytest.mark.ac("006/AC-07")
async def test_add_link_starts_from_the_book(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    page = await member.get(f"/series/{dresden['series']}")
    assert add_link(dresden["4"], dresden["series"]) in page.text
    assert add_link(dresden["1"], dresden["series"]) not in page.text  # already mine
    form = await member.get(f"/books/add?book={dresden['4']}&from_series={dresden['series']}")
    assert form.status_code == 200
    body = form.text
    assert f'name="book_id" value="{dresden["4"]}"' in body
    assert 'value="Summer Knight"' in body
    assert f'name="author_id_0" value="{dresden["author"]}"' in body
    assert 'value="Jim Butcher"' in body
    assert f'name="series_id" value="{dresden["series"]}"' in body
    assert 'name="series_number"' in body and 'value="4"' in body
    assert '<option value="want_to_read" selected>' in body
    assert f'name="from_series" value="{dresden["series"]}"' in body


def _save_book(ids: dict[str, uuid.UUID], book: str, then: str = "list") -> dict[str, str]:
    return {
        "book_id": str(ids[book]),
        "title": TITLES.get(book, ""),
        "status": "want_to_read",
        "from_series": str(ids["series"]),
        "then": then,
    }


@pytest.mark.ac("006/AC-08")
async def test_save_returns_to_series(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    saved = await member.post("/books/add", data=_save_book(dresden, "4"))
    assert saved.status_code == 303
    location = saved.headers["location"]
    match = re.fullmatch(rf"/series/{dresden['series']}\?added=([0-9a-f-]{{36}})", location)
    assert match, location
    assert await counts(factory) == (before[0], before[1] + 1)
    page = await member.get(location)
    assert "Added “Summer Knight” to your list." in text(page)
    assert re.search(r'role="status"[^>]*>\s*Added', page.text)
    knight = next(row for row in rows(page) if "Summer Knight" in row)
    assert knight.endswith("Want to read")
    assert f'href="/entries/{match.group(1)}"' in page.text


@pytest.mark.ac("006/AC-09")
async def test_gap_add(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    series, author = dresden["series"], dresden["author"]
    page = await member.get(f"/series/{series}")
    gap = f'href="/books/add?series={series}&amp;number=6&amp;from_series={series}"'
    assert gap in page.text
    form = await member.get(f"/books/add?series={series}&number=6&from_series={series}")
    body = form.text
    assert f'name="series_id" value="{series}"' in body
    assert 'value="The Dresden Files"' in body
    assert re.search(r'name="series_number"[^>]*value="6"', body)
    assert 'name="book_id" value=""' in body
    assert '<option value="want_to_read" selected>' in body
    saved = await member.post(
        "/books/add",
        data={
            "title": "Blood Rites", "author_id_0": str(author), "author_name_0": "Jim Butcher",
            "series_id": str(series), "series_name": "The Dresden Files",
            "series_number": "6", "status": "want_to_read", "from_series": str(series),
            "then": "list",
        },
    )  # fmt: skip
    assert saved.status_code == 303
    assert saved.headers["location"].startswith(f"/series/{series}?added=")
    page = await member.get(saved.headers["location"])
    six = next(row for row in rows(page) if "Blood Rites" in row)
    assert six.startswith("#6 Blood Rites") and six.endswith("Want to read")
    assert not any(row.startswith("#6 Not in the family catalog") for row in rows(page))


@pytest.mark.ac("006/AC-10")
async def test_return_survives_errors_and_prompts(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    series = str(dresden["series"])
    base = {
        "series_id": series, "series_name": "The Dresden Files", "series_number": "6",
        "status": "want_to_read", "from_series": series, "then": "list",
    }  # fmt: skip
    missing_title = await member.post(
        "/books/add", data={**base, "author_name_0": "Jim Butcher",
                            "author_id_0": str(dresden["author"])}
    )  # fmt: skip
    assert missing_title.status_code == 422
    assert f'name="from_series" value="{series}"' in missing_title.text
    typed = {**base, "title": "Blood Rites", "author_name_0": "Priscilla Butcher"}
    prompt = await member.post("/books/add", data=typed)
    assert prompt.status_code == 409
    assert "is not in the family catalog yet" in html.unescape(prompt.text)
    assert f'name="from_series" value="{series}"' in prompt.text
    confirmed = await member.post(
        "/books/add", data={**typed, "confirm_author_0": "Priscilla Butcher"}
    )
    assert confirmed.status_code == 303
    assert confirmed.headers["location"].startswith(f"/series/{series}?added=")


@pytest.mark.ac("006/AC-10")
async def test_isbn_conflict_form_keeps_the_return(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    await factory.book("Turn Coat", alice, author_ids=[dresden["author"]], isbn_13="9780451462565")
    series = str(dresden["series"])
    page = await member.post(
        "/books/add",
        data={
            "title": "Turn Coat again", "author_id_0": str(dresden["author"]),
            "author_name_0": "Jim Butcher", "isbn_13": "9780451462565",
            "status": "want_to_read", "from_series": series, "then": "list",
        },
    )  # fmt: skip
    assert page.status_code == 409
    conflict_form = page.text.split('id="conflict"', 1)[1].split("</form>", 1)[0]
    assert f'name="from_series" value="{series}"' in conflict_form


@pytest.mark.ac("006/AC-11")
async def test_add_another_keeps_spec_004(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    saved = await member.post("/books/add", data=_save_book(dresden, "4", then="another"))
    assert saved.status_code == 303
    assert saved.headers["location"].startswith("/books/add?after=")


@pytest.mark.ac("006/AC-12")
async def test_bad_parameters_ignored(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    for query in (
        "book=junk", f"book={uuid.uuid4()}", "series=junk&number=3",
        f"series={uuid.uuid4()}&number=3", "from_series=junk", f"from_series={uuid.uuid4()}",
        "from_series=https://example.com/",
    ):  # fmt: skip
        form = await member.get(f"/books/add?{query}")
        assert form.status_code == 200, query
        assert 'name="book_id" value=""' in form.text, query
        assert 'name="series_id" value=""' in form.text, query
        assert 'name="from_series"' not in form.text, query
    bad_number = await member.get(f"/books/add?series={dresden['series']}&number=abc")
    assert f'name="series_id" value="{dresden["series"]}"' in bad_number.text
    assert not re.search(r'name="series_number"[^>]*value="[^"]', bad_number.text)

    for bad in ("junk", str(uuid.uuid4()), "//example.com"):
        data = {**_save_book(dresden, "3"), "from_series": bad}
        saved = await member.post("/books/add", data=data)
        assert saved.status_code == 303 and saved.headers["location"] == "/?msg=added", bad
        # remove it again so the next loop can add the same book
        entry_id = await _entry_of(factory, dresden["3"])
        assert entry_id is not None
        await _delete_entry(factory, entry_id)

    # Ben's entry id in ?added= shows nothing on Alice's page.
    page = await member.get(f"/series/{dresden['series']}?added={dresden['ben4']}")
    assert page.status_code == 200 and "Added “" not in text(page)
    page = await member.get(f"/series/{dresden['series']}?added=junk")
    assert page.status_code == 200 and "Added “" not in text(page)


async def _entry_of(factory: Factory, book: uuid.UUID) -> uuid.UUID | None:
    async with factory._app.state.db.sessionmaker() as session:
        return await session.scalar(
            select(models.ReadingEntry.id).where(models.ReadingEntry.book_id == book)
        )


async def _delete_entry(factory: Factory, entry: uuid.UUID) -> None:
    async with factory._app.state.db.sessionmaker() as session:
        row = await session.get(models.ReadingEntry, entry)
        await session.delete(row)
        await session.commit()


@pytest.mark.ac("006/AC-13")
async def test_already_on_my_list(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    page = await member.post("/books/add", data=_save_book(dresden, "1"))
    assert page.status_code == 409
    assert "Already on your list" in text(page)
    assert await counts(factory) == before


# --------------------------------------------------------------------------- US3


@pytest.mark.ac("006/AC-14")
async def test_gap_rows_on_page(member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]) -> None:
    page = await member.get(f"/series/{dresden['series']}")
    shown = rows(page)
    six = shown.index("#6 Not in the family catalog yet Add #6")
    assert "Backup" in shown[six + 1]
    assert "Death Masks" in shown[six - 1]


@pytest.mark.ac("006/AC-16")
async def test_long_gap_is_one_row(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    await factory.book(
        "Far Future", alice, author_ids=[dresden["author"]], series_id=dresden["series"],
        series_number="500",
    )  # fmt: skip
    shown = rows(await member.get(f"/series/{dresden['series']}"))
    assert "#6–#499 Not in the family catalog yet Add #6" in shown
    assert len(shown) == 9  # 8 books and one gap row; Side Jobs last
    assert "Side Jobs" in shown[-1]
