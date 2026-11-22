"""Spec 007: release dates and "Coming", Pre-ordered, the Upcoming filter and page, and the
"Now out" notice. Today is pinned to 21 Nov 2026."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in

TODAY = date(2026, 11, 21)


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


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


def text(page: httpx.Response) -> str:
    """The page's text; tags dropped without adding spaces, whitespace collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", page.text)).split())


def words(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def list_rows(page: httpx.Response) -> list[str]:
    """My books rows, as text."""
    if '<ul class="book-list reading-list"' not in page.text:
        return []
    body = page.text.split('<ul class="book-list reading-list"', 1)[1].split("</ul>", 1)[0]
    return [words(item) for item in re.findall(r"<li[^>]*>(.*?)</li>", body, flags=re.S)]


def section(page: httpx.Response, heading: str) -> str:
    """The HTML from an <h2> with this text up to the next <h2> (or the end of main)."""
    after = re.split(rf"<h2[^>]*>\s*{re.escape(heading)}\s*</h2>", page.text, maxsplit=1)
    assert len(after) == 2, heading
    return re.split(r"<h2|</main>", after[1], maxsplit=1)[0]


def titles_in(fragment: str, candidates: list[str]) -> list[str]:
    found = [(fragment.find(t), t) for t in candidates if t in fragment]
    return [t for _, t in sorted(found)]


@pytest.fixture
async def shelf(factory: Factory, alice: TestUser, ben: TestUser) -> dict[str, uuid.UUID]:
    """The spec's example. Alice: Twelve Months (3 Mar 2027, pre-ordered), Mirror Mirror
    (1 Jun 2027), The Olympian Affair (7 Nov 2026, pre-ordered), Storm Front (2000,
    Finished). Ben only: Wind and Truth (6 Dec 2026, pre-ordered). Nobody: Sunrise (2 Jan
    2027) and Old News (1 Jan 2020)."""
    author = await factory.author("Jim Butcher", alice)
    series = await factory.series("The Dresden Files", alice)
    ids: dict[str, uuid.UUID] = {"author": author, "series": series}
    ids["twelve"] = await factory.book(
        "Twelve Months", alice, author_ids=[author], series_id=series, series_number="18",
        release_date=date(2027, 3, 3),
    )  # fmt: skip
    ids["mirror"] = await factory.book(
        "Mirror Mirror", alice, author_ids=[author], release_date=date(2027, 6, 1)
    )
    ids["olympian"] = await factory.book(
        "The Olympian Affair", alice, author_ids=[author], release_date=date(2026, 11, 7)
    )
    ids["storm"] = await factory.book(
        "Storm Front", alice, author_ids=[author], series_id=series, series_number="1",
        release_date=date(2000, 4, 1),
    )  # fmt: skip
    ids["wind"] = await factory.book("Wind and Truth", ben, release_date=date(2026, 12, 6))
    ids["sunrise"] = await factory.book("Sunrise", ben, release_date=date(2027, 1, 2))
    ids["old"] = await factory.book("Old News", ben, release_date=date(2020, 1, 1))
    ids["e_twelve"] = await factory.entry(
        alice, ids["twelve"], status="want_to_read", pre_ordered=True
    )
    ids["e_mirror"] = await factory.entry(alice, ids["mirror"], status="want_to_read")
    ids["e_olympian"] = await factory.entry(
        alice, ids["olympian"], status="want_to_read", pre_ordered=True
    )
    ids["e_storm"] = await factory.entry(alice, ids["storm"], finished_on=date(2001, 5, 5))
    ids["ben_wind"] = await factory.entry(ben, ids["wind"], status="want_to_read", pre_ordered=True)
    return ids


def _new_book(author: uuid.UUID, **extra: str) -> dict[str, str]:
    return {
        "title": "Peace Talks", "author_id_0": str(author), "author_name_0": "Jim Butcher",
        "status": "want_to_read", "then": "list", **extra,
    }  # fmt: skip


async def _release_date(factory: Factory, title: str) -> Any:
    return await factory.scalar("SELECT release_date FROM book WHERE title = :t", t=title)


async def _pre_ordered(factory: Factory, entry_id: uuid.UUID) -> Any:
    return await factory.scalar("SELECT pre_ordered FROM reading_entry WHERE id = :id", id=entry_id)


def _book_fields(book_title: str, author: uuid.UUID, **extra: str) -> dict[str, str]:
    return {
        "title": book_title, "author_id_0": str(author), "author_name_0": "Jim Butcher",
        **extra,
    }  # fmt: skip


# --------------------------------------------------------------------------- US1


@pytest.mark.ac("007/AC-01")
async def test_add_book_with_release_date(
    member: httpx.AsyncClient, factory: Factory, shelf: dict[str, uuid.UUID]
) -> None:
    form = await member.get("/books/add")
    assert re.search(
        r'<input id="release_date" name="release_date" type="date"[^>]*value=""', form.text
    )
    assert "Release date (optional)" in text(form)
    saved = await member.post(
        "/books/add", data=_new_book(shelf["author"], release_date="2027-04-01")
    )
    assert saved.status_code == 303, saved.text
    assert await _release_date(factory, "Peace Talks") == date(2027, 4, 1)
    blank = await member.post(
        "/books/add", data={**_new_book(shelf["author"]), "title": "Skin Game"}
    )
    assert blank.status_code == 303
    assert await _release_date(factory, "Skin Game") is None


@pytest.mark.ac("007/AC-02")
async def test_edit_release_date(
    member: httpx.AsyncClient,
    other: httpx.AsyncClient,
    factory: Factory,
    shelf: dict[str, uuid.UUID],
) -> None:
    edit = f"/catalog/books/{shelf['mirror']}/edit"
    page = await member.get(edit)
    assert re.search(r'name="release_date"[^>]*value="2027-06-01"', page.text)
    saved = await member.post(
        edit, data=_book_fields("Mirror Mirror", shelf["author"], release_date="2027-07-15")
    )
    assert saved.status_code == 303, saved.text
    assert await _release_date(factory, "Mirror Mirror") == date(2027, 7, 15)
    cleared = await member.post(edit, data=_book_fields("Mirror Mirror", shelf["author"]))
    assert cleared.status_code == 303
    assert await _release_date(factory, "Mirror Mirror") is None
    # Through the entry page's book section, as other book details.
    entry = f"/entries/{shelf['e_mirror']}"
    saved = await member.post(
        entry,
        data={
            **_book_fields("Mirror Mirror", shelf["author"], release_date="2027-08-01"),
            "status": "want_to_read", "times_read": "0", "notes": "", "pre_ordered": "",
        },
    )  # fmt: skip
    assert saved.status_code == 303, saved.text
    assert await _release_date(factory, "Mirror Mirror") == date(2027, 8, 1)
    # A catalog change: Ben sees it.
    theirs = await other.get(f"/catalog/books/{shelf['mirror']}/edit")
    assert re.search(r'name="release_date"[^>]*value="2027-08-01"', theirs.text)


@pytest.mark.ac("007/AC-02")
async def test_stale_form_keeps_a_newer_release_date(
    member: httpx.AsyncClient,
    other: httpx.AsyncClient,
    factory: Factory,
    shelf: dict[str, uuid.UUID],
) -> None:
    """PR #23 review: Alice's entry page was opened before Ben set the date. Saving only her
    notes must not clear Ben's date; the same goes for a stale Edit book page."""
    await factory.execute("UPDATE book SET release_date = NULL WHERE id = :id", id=shelf["mirror"])
    entry = await member.get(f"/entries/{shelf['e_mirror']}")
    assert re.search(r'name="release_date_was"[^>]*value=""', entry.text)
    stale_edit = await member.get(f"/catalog/books/{shelf['mirror']}/edit")
    assert re.search(r'name="release_date_was"[^>]*value=""', stale_edit.text)
    saved = await other.post(
        f"/catalog/books/{shelf['mirror']}/edit",
        data=_book_fields(
            "Mirror Mirror", shelf["author"], release_date="2027-03-01", release_date_was=""
        ),
    )
    assert saved.status_code == 303
    fields = {
        **_book_fields("Mirror Mirror", shelf["author"], release_date="", release_date_was=""),
        "status": "want_to_read", "times_read": "0", "notes": "only my notes", "pre_ordered": "",
    }  # fmt: skip
    assert (await member.post(f"/entries/{shelf['e_mirror']}", data=fields)).status_code == 303
    assert await _release_date(factory, "Mirror Mirror") == date(2027, 3, 1)
    stale = _book_fields("Mirror Mirror", shelf["author"], release_date="", release_date_was="")
    edit = await member.post(f"/catalog/books/{shelf['mirror']}/edit", data=stale)
    assert edit.status_code == 303
    assert await _release_date(factory, "Mirror Mirror") == date(2027, 3, 1)
    # Changing the field still saves, including clearing it on purpose.
    cleared = _book_fields(
        "Mirror Mirror", shelf["author"], release_date="", release_date_was="2027-03-01"
    )
    await member.post(f"/catalog/books/{shelf['mirror']}/edit", data=cleared)
    assert await _release_date(factory, "Mirror Mirror") is None


@pytest.mark.ac("007/AC-03")
async def test_bad_release_date(
    member: httpx.AsyncClient, factory: Factory, shelf: dict[str, uuid.UUID]
) -> None:
    bad = await member.post(
        "/books/add", data=_new_book(shelf["author"], release_date="2027-02-30")
    )
    assert bad.status_code == 422
    assert 'id="release_date-error"' in bad.text
    assert "Enter a date like 2027-03-01" in text(bad)
    assert await factory.scalar("SELECT count(*) FROM book WHERE title = 'Peace Talks'") == 0
    edit = await member.post(
        f"/catalog/books/{shelf['mirror']}/edit",
        data=_book_fields("Mirror Mirror", shelf["author"], release_date="soon"),
    )
    assert edit.status_code == 422
    assert 'id="release_date-error"' in edit.text
    assert await _release_date(factory, "Mirror Mirror") == date(2027, 6, 1)


@pytest.mark.ac("007/AC-04")
async def test_coming_label_everywhere(
    member: httpx.AsyncClient, shelf: dict[str, uuid.UUID]
) -> None:
    mine = await member.get("/")
    twelve = next(row for row in list_rows(mine) if "Twelve Months" in row)
    assert "Coming 3 Mar 2027" in twelve
    series = await member.get(f"/series/{shelf['series']}")
    assert "Coming 3 Mar 2027" in text(series)
    entry = await member.get(f"/entries/{shelf['e_twelve']}")
    assert "Coming 3 Mar 2027" in text(entry)


@pytest.mark.ac("007/AC-05")
async def test_released_and_undated(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    today_book = await factory.book("Out Today", alice, release_date=TODAY)
    today_entry = await factory.entry(alice, today_book, status="reading")
    undated = await factory.book("No Date", alice)
    undated_entry = await factory.entry(alice, undated, status="reading")
    mine = await member.get("/")
    for title in ("Storm Front", "Out Today", "No Date", "The Olympian Affair"):
        row = next(r for r in list_rows(mine) if title in r)
        assert "Coming" not in row, row
    storm = await member.get(f"/entries/{shelf['e_storm']}")
    assert "Released 1 Apr 2000" in text(storm) and "Coming" not in text(storm)
    out_today = await member.get(f"/entries/{today_entry}")
    assert "Released 21 Nov 2026" in text(out_today)
    plain = await member.get(f"/entries/{undated_entry}")
    assert "Released" not in text(plain) and "Coming" not in text(plain)
    # Out, and pre-ordered within the Now out period: both show (PR #23 review).
    olympian = await member.get(f"/entries/{shelf['e_olympian']}")
    assert "Released 7 Nov 2026 · Pre-ordered" in text(olympian)


@pytest.mark.ac("007/AC-06")
async def test_chosen_book_shows_coming(
    member: httpx.AsyncClient, shelf: dict[str, uuid.UUID]
) -> None:
    page = await member.get(f"/books/add?book={shelf['wind']}")
    chosen = page.text.split('chosen-book">', 1)[1].split("</div>", 1)[0]
    assert "Coming 6 Dec 2026" in words(chosen)


# --------------------------------------------------------------------------- US2


@pytest.mark.ac("007/AC-07")
async def test_pre_ordered_saves(
    member: httpx.AsyncClient, factory: Factory, shelf: dict[str, uuid.UUID]
) -> None:
    form = await member.get("/books/add")
    assert re.search(r'<input[^>]*type="checkbox"[^>]*name="pre_ordered"', form.text)
    assert not re.search(r'name="pre_ordered"[^>]*checked', form.text)
    saved = await member.post(
        "/books/add",
        data=_new_book(shelf["author"], release_date="2027-04-01", pre_ordered="yes"),
    )
    assert saved.status_code == 303
    entry_id = await factory.scalar(
        "SELECT e.id FROM reading_entry e JOIN book b ON b.id = e.book_id "
        "WHERE b.title = 'Peace Talks'"
    )
    assert await _pre_ordered(factory, entry_id) is True
    url = f"/entries/{entry_id}"
    page = await member.get(url)
    assert re.search(r'name="pre_ordered"[^>]*value="yes"[^>]*checked', page.text)
    # Untick: the browser sends only the hidden field.
    await member.post(url, data={"status": "want_to_read", "pre_ordered": ""})
    assert await _pre_ordered(factory, entry_id) is False
    # Tick again: hidden field first, then the checkbox (the last value wins).
    await member.post(
        url,
        content=urlencode(
            [("status", "want_to_read"), ("pre_ordered", ""), ("pre_ordered", "yes")]
        ),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert await _pre_ordered(factory, entry_id) is True
    # A form without the field leaves it alone.
    await member.post(url, data={"status": "reading"})
    assert await _pre_ordered(factory, entry_id) is True


@pytest.mark.ac("007/AC-08")
async def test_pre_ordered_shown_when_relevant(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    long_ago = await factory.book("Long Out", alice, release_date=TODAY - timedelta(days=40))
    long_entry = await factory.entry(alice, long_ago, status="want_to_read", pre_ordered=True)
    mine = await member.get("/")
    twelve = next(row for row in list_rows(mine) if "Twelve Months" in row)
    assert "Coming 3 Mar 2027 · Pre-ordered" in twelve
    assert "Pre-ordered" not in next(r for r in list_rows(mine) if "Mirror Mirror" in r)
    assert "Pre-ordered" not in next(r for r in list_rows(mine) if "Long Out" in r)
    entry = await member.get(f"/entries/{shelf['e_twelve']}")
    assert "Coming 3 Mar 2027 · Pre-ordered" in text(entry)
    series = await member.get(f"/series/{shelf['series']}")
    assert "Coming 3 Mar 2027 · Pre-ordered" in text(series)
    old = await member.get(f"/entries/{long_entry}")
    assert re.search(r'name="pre_ordered"[^>]*checked', old.text)
    assert "· Pre-ordered" not in text(old)


@pytest.mark.ac("007/AC-09")
async def test_pre_ordered_is_private(
    member: httpx.AsyncClient, other: httpx.AsyncClient, shelf: dict[str, uuid.UUID]
) -> None:
    """SC-003: Alice's pre-orders and entries never show for Ben."""
    theirs = await other.get("/")
    rows = list_rows(theirs)
    assert len(rows) == 1 and "Wind and Truth" in rows[0]  # only Ben's own pre-order
    assert "Pre-ordered" in rows[0]
    assert "Twelve Months" not in text(theirs) and "Olympian" not in text(theirs)
    series = await other.get(f"/series/{shelf['series']}")
    assert "Pre-ordered" not in text(series)
    upcoming = await other.get("/upcoming")
    also = section(upcoming, "Also coming in the family catalog")
    assert "Twelve Months" in also and "Pre-ordered" not in words(also)
    assert "Alice" not in text(upcoming)
    api = await other.get("/api/v1/me/readings")
    assert all(item["book"]["title"] == "Wind and Truth" for item in api.json()["items"])


# --------------------------------------------------------------------------- US3


@pytest.mark.ac("007/AC-10")
async def test_upcoming_filter(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    also_march = await factory.book("A March Book", alice, release_date=date(2027, 3, 3))
    await factory.entry(alice, also_march, status="reading")
    page = await member.get("/?upcoming=1&sort=-title")
    candidates = ["A March Book", "Twelve Months", "Mirror Mirror", "The Olympian Affair",
                  "Storm Front", "Wind and Truth"]  # fmt: skip
    order = titles_in(" | ".join(list_rows(page)), candidates)
    assert order == ["A March Book", "Twelve Months", "Mirror Mirror"]
    assert "3 books" in text(page)
    assert re.search(r'name="upcoming" value="1"[^>]*checked', page.text)
    assert "Soonest first" in text(page)
    narrowed = await member.get("/?upcoming=1&status=want_to_read&q=mirror")
    two = ["Twelve Months", "Mirror Mirror"]
    assert titles_in(" | ".join(list_rows(narrowed)), two) == ["Mirror Mirror"]
    by_series = await member.get(f"/?upcoming=1&series_id={shelf['series']}")
    assert titles_in(" | ".join(list_rows(by_series)), two) == ["Twelve Months"]
    by_author = await member.get(f"/?upcoming=1&author_id={shelf['author']}")
    assert titles_in(" | ".join(list_rows(by_author)), two) == [
        "Twelve Months", "Mirror Mirror",
    ]  # fmt: skip
    # The sort is ignored under Upcoming only, so it isn't kept in links (PR #23 review).
    assert "sort=-title" not in page.text
    junk = await member.get("/?upcoming=yes")
    assert any("Storm Front" in row for row in list_rows(junk))  # anything but 1 is off


@pytest.mark.ac("007/AC-11")
async def test_upcoming_filter_kept(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    for n in range(60):
        book = await factory.book(f"Future {n:02}", alice, release_date=date(2028, 1, 1))
        await factory.entry(alice, book, status="want_to_read")
    page = await member.get("/?upcoming=1")
    assert (
        'href="/?upcoming=1&amp;page=2"' in page.text or 'href="/?upcoming=1&page=2"' in page.text
    )
    assert '<a href="/">Clear</a>' in page.text
    partial = await member.get("/?upcoming=1", headers={"HX-Request": "true"})
    assert "Storm Front" not in partial.text and "Twelve Months" in partial.text
    assert "<html" not in partial.text


@pytest.mark.ac("007/AC-12")
async def test_upcoming_page(member: httpx.AsyncClient, shelf: dict[str, uuid.UUID]) -> None:
    page = await member.get("/upcoming")
    assert page.status_code == 200
    assert re.search(r'<a href="/upcoming" aria-current="page">Upcoming</a>', page.text)
    mine = section(page, "On my list")
    candidates = ["Twelve Months", "Mirror Mirror", "The Olympian Affair", "Storm Front",
                  "Wind and Truth"]  # fmt: skip
    assert titles_in(mine, candidates) == ["Twelve Months", "Mirror Mirror"]
    assert "Coming 3 Mar 2027 · Pre-ordered" in words(mine)
    assert "Want to read" in words(mine) and "Jim Butcher" in words(mine)
    assert "The Dresden Files #18" in words(mine)
    assert f'href="/entries/{shelf["e_twelve"]}"' in mine
    also = section(page, "Also coming in the family catalog")
    assert titles_in(also, ["Wind and Truth", "Sunrise", "Old News", "Twelve Months"]) == [
        "Wind and Truth", "Sunrise",
    ]  # fmt: skip
    assert "Coming 6 Dec 2026" in words(also)
    assert f'href="/books/add?book={shelf["wind"]}"' in also
    assert str(shelf["ben_wind"]) not in page.text


@pytest.mark.ac("007/AC-13")
async def test_upcoming_page_empty(member: httpx.AsyncClient) -> None:
    page = await member.get("/upcoming")
    assert "Nothing on your list is coming up." in text(page)
    assert "Nothing else in the family catalog is coming up." in text(page)
    assert 'href="/books/add"' in page.text


# --------------------------------------------------------------------------- US4


def notice(page: httpx.Response) -> str | None:
    match = re.search(
        r'<div class="notice" role="status" id="now-out">(.*?)</div>', page.text, re.S
    )
    return match.group(1) if match else None


@pytest.mark.ac("007/AC-14")
async def test_now_out_notice(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    today_book = await factory.book("Out Today", alice, release_date=TODAY)
    today_entry = await factory.entry(alice, today_book, status="want_to_read")
    edge = await factory.book("Day Thirty", alice, release_date=TODAY - timedelta(days=29))
    await factory.entry(alice, edge, status="want_to_read")
    page = await member.get("/")
    found = notice(page)
    assert found is not None
    assert words(found).startswith("Now out:")
    assert titles_in(found, ["Out Today", "The Olympian Affair", "Day Thirty"]) == [
        "Out Today", "The Olympian Affair", "Day Thirty",
    ]  # fmt: skip
    assert "The Olympian Affair (pre-ordered)" in words(found)
    assert "Out Today (pre-ordered)" not in words(found)
    assert f'href="/entries/{today_entry}"' in found
    assert f'href="/entries/{shelf["e_olympian"]}"' in found
    # Before the filters, on the full page only.
    assert page.text.index('id="now-out"') < page.text.index('role="search"')


@pytest.mark.ac("007/AC-15")
async def test_now_out_window(member: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    gone = await factory.book("Day Thirty-One", alice, release_date=TODAY - timedelta(days=30))
    await factory.entry(alice, gone, status="want_to_read")
    soon = await factory.book("Tomorrow", alice, release_date=TODAY + timedelta(days=1))
    await factory.entry(alice, soon, status="want_to_read")
    assert notice(await member.get("/")) is None


@pytest.mark.ac("007/AC-16")
async def test_now_out_only_want_to_read(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    for title, status in (("Reading Now", "reading"), ("Done Already", "finished")):
        book = await factory.book(title, alice, release_date=TODAY - timedelta(days=3))
        await factory.entry(alice, book, status=status)
    assert notice(await member.get("/")) is None


@pytest.mark.ac("007/AC-17")
async def test_no_notice_when_none(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    await factory.execute("UPDATE book SET release_date = NULL WHERE title = 'The Olympian Affair'")
    page = await member.get("/")
    assert 'id="now-out"' not in page.text and "Now out" not in page.text
    await factory.execute(
        "UPDATE book SET release_date = :d WHERE title = 'The Olympian Affair'", d=TODAY
    )
    partial = await member.get("/", headers={"HX-Request": "true"})
    assert 'id="now-out"' not in partial.text


@pytest.mark.ac("007/AC-18")
async def test_now_out_is_private(
    member: httpx.AsyncClient, other: httpx.AsyncClient, factory: Factory, ben: TestUser
) -> None:
    yesterday = await factory.book("Ben's New Book", ben, release_date=TODAY - timedelta(days=1))
    await factory.entry(ben, yesterday, status="want_to_read", pre_ordered=True)
    assert notice(await member.get("/")) is None
    theirs = notice(await other.get("/"))
    assert theirs is not None and "Ben's New Book (pre-ordered)" in words(theirs)


# --------------------------------------------------------------------------- privacy


async def test_other_members_entry_still_404(
    member: httpx.AsyncClient, shelf: dict[str, uuid.UUID]
) -> None:
    """Principle I: Ben's entry is not found for Alice, on the page and through the API."""
    assert (await member.get(f"/entries/{shelf['ben_wind']}")).status_code == 404
    assert (await member.get(f"/api/v1/me/readings/{shelf['ben_wind']}")).status_code == 404
