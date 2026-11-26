"""Spec 018: consistent navigation — the menu, the Authors page, Upcoming as the one place
for what's coming and what's new, and the Catalog's Series view (Principle I throughout)."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from book_tracker.persistence.favorites import FavoriteAuthorRepository
from book_tracker.persistence.models import Author
from book_tracker.persistence.readings import ReadingEntryRepository
from tests.conftest import Factory, TestUser, signed_in

TODAY = date(2026, 11, 21)
TEMPLATES = Path(__file__).resolve().parents[2] / "src/book_tracker/web/templates"


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def ben(factory: Factory) -> TestUser:
    return await factory.user("ben")


@pytest.fixture
async def member(
    client_factory: Callable[[], httpx.AsyncClient], alice: TestUser
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture
async def other(
    client_factory: Callable[[], httpx.AsyncClient], ben: TestUser
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), ben)


def words(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def section(page: str, pattern: str) -> str:
    match = re.search(pattern, page, re.S)
    assert match, pattern
    return match.group(1)


def menu(page: str) -> tuple[list[tuple[str, str, bool]], list[tuple[str, str, bool]]]:
    """(places, actions): each item's href, words and whether it's the current page."""
    nav = section(page, r'<nav aria-label="Main">(.*?)</nav>')
    lists = re.findall(r'<ul class="nav-list ([\w-]+)"([^>]*)>(.*?)</ul>', nav, re.S)
    found: dict[str, list[tuple[str, str, bool]]] = {}
    for kind, attrs, body in lists:
        found[kind] = [
            (href, words(label), "aria-current" in rest)
            for href, rest, label in re.findall(r'<a href="([^"]*)"([^>]*)>(.*?)</a>', body, re.S)
        ]
        if kind == "nav-actions":
            assert 'aria-label="Actions"' in attrs
    assert list(found) == ["nav-places", "nav-actions"], list(found)
    return found["nav-places"], found["nav-actions"]


def current(page: str) -> list[str]:
    places, actions = menu(page)
    return [label for _, label, here in places + actions if here]


def rows(page: str, cls: str = "author-row") -> list[str]:
    return [words(r) for r in re.findall(rf'<li class="{cls}"[^>]*>(.*?)</li>', page, re.S)]


def names(page: str, cls: str = "author-row") -> list[str]:
    return [
        words(name)
        for row in re.findall(rf'<li class="{cls}"[^>]*>(.*?)</li>', page, re.S)
        for name in re.findall(r'<a class="row-name" href="[^"]*">(.*?)</a>', row, re.S)
    ]


_STAR = re.compile(
    r'<form method="post" action="/authors/([0-9a-f-]{36})/favorite"[^>]*>(.*?)</form>', re.S
)


def stars(page: str) -> dict[str, dict[str, str]]:
    found = {}
    for author, body in _STAR.findall(page):
        fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', body))
        found[author] = {k: html.unescape(v) for k, v in fields.items()}
    return found


# --------------------------------------------------------------------------- repositories


async def test_author_condition_is_bound_to_the_user(
    app: Any, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    from sqlalchemy import select

    mine = await factory.author("Mine", alice)
    theirs = await factory.author("Theirs", alice)
    await factory.author("Nobody's", alice)
    await factory.favorite(alice, mine)
    await factory.favorite(ben, theirs)
    async with app.state.db.sessionmaker() as db:
        condition = FavoriteAuthorRepository(db, alice.id).author_condition()
        found = set(await db.scalars(select(Author.id).where(condition)))
    assert found == {mine}


async def test_finished_counts_by_series(
    app: Any, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    discworld = await factory.series("Discworld", alice)
    culture = await factory.series("Culture", alice)
    empty = await factory.series("Empty", alice)
    books = [await factory.book(f"D{i}", alice, series_id=discworld) for i in range(3)]
    novel = await factory.book("C1", alice, series_id=culture)
    await factory.entry(alice, books[0], status="finished")
    await factory.entry(alice, books[1], status="finished")
    await factory.entry(alice, books[2], status="reading")
    await factory.entry(alice, novel, status="want_to_read")
    await factory.entry(ben, novel, status="finished")
    await factory.entry(ben, books[2], status="finished")
    async with app.state.db.sessionmaker() as db:
        repo = ReadingEntryRepository(db, alice.id)
        assert await repo.finished_counts_by_series([discworld, culture, empty]) == {discworld: 2}
        assert await repo.finished_counts_by_series([]) == {}


def test_authors_query_falls_back_to_defaults() -> None:
    from book_tracker.schemas.catalog import AuthorsQuery, SeriesQuery

    query = AuthorsQuery.model_validate({"q": "  prat ", "favorites": "1", "page": "2"})
    assert (query.q, query.favorites, query.page) == ("prat", True, 2)
    bad = AuthorsQuery.model_validate({"q": ["x"], "favorites": "yes", "page": "0"})
    assert (bad.q, bad.favorites, bad.page) == ("", False, 1)
    assert AuthorsQuery.model_validate({}).page == 1
    series = SeriesQuery.model_validate({"q": "disc", "page": "-3"})
    assert (series.q, series.page) == ("disc", 1)


# --------------------------------------------------------------------------- AC-01 the menu


@pytest.mark.ac("018/AC-01")
async def test_menu_places_then_actions(
    member: httpx.AsyncClient, client_factory: Callable[[], httpx.AsyncClient], factory: Factory
) -> None:
    places, actions = menu((await member.get("/")).text)
    assert [(h, label) for h, label, _ in places] == [
        ("/", "My books"),
        ("/catalog", "Catalog"),
        ("/authors", "Authors"),
        ("/upcoming", "Upcoming"),
    ]
    assert [(h, label) for h, label, _ in actions] == [
        ("/books/add", "Add a book"),
        ("/import", "Import"),
    ]
    admin = await signed_in(client_factory(), await factory.user("root", role="admin"))
    _, admin_actions = menu((await admin.get("/")).text)
    assert [label for _, label, _ in admin_actions] == ["Add a book", "Import", "Accounts"]


@pytest.mark.ac("018/AC-01")
async def test_menu_marks_the_current_place(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Discworld", alice)
    author = await factory.author("Terry Pratchett", alice)
    book = await factory.book("Mort", alice, author_ids=[author], series_id=series)
    expected = {
        "/": "My books",
        "/catalog": "Catalog",
        "/catalog/series": "Catalog",
        f"/series/{series}": "Catalog",
        f"/books/{book}": "Catalog",
        "/authors": "Authors",
        f"/authors/{author}": "Authors",
        "/upcoming": "Upcoming",
        "/books/add": "Add a book",
        "/import": "Import",
    }
    for path, label in expected.items():
        page = await member.get(path)
        assert page.status_code == 200, path
        assert current(page.text) == [label], path


# --------------------------------------------------------------------------- AC-02 the rows


@pytest.mark.ac("018/AC-02")
async def test_authors_page_rows(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    pratchett = await factory.author("Terry Pratchett", alice, sort_name="Pratchett, Terry")
    banks = await factory.author("Iain M. Banks", alice, sort_name="Banks, Iain M.")
    galbraith = await factory.author(
        "Robert Galbraith", alice, sort_name="Galbraith, Robert", is_pen_name=True,
        real_name="J. K. Rowling",
    )  # fmt: skip
    austen = await factory.author("Jane Austen", alice, sort_name="Austen, Jane")
    lonely = await factory.author("Nobody Atall", alice, sort_name="Atall, Nobody")
    mort = await factory.book("Mort", alice, author_ids=[pratchett])
    await factory.book("Eric", alice, author_ids=[pratchett])
    guards = await factory.book("Guards! Guards!", alice, author_ids=[pratchett])
    await factory.book("Excession", alice, author_ids=[banks])
    await factory.book("The Cuckoo's Calling", alice, author_ids=[galbraith])
    await factory.book("Emma", alice, author_ids=[austen])
    await factory.entry(alice, mort, status="finished")
    await factory.entry(alice, guards, status="finished")
    await factory.favorite(alice, pratchett)
    await factory.favorite(alice, austen)

    page = await member.get("/authors")
    assert page.status_code == 200
    # Favorites first, then everyone else, each by sort name.
    assert names(page.text) == [
        "Jane Austen", "Terry Pratchett",
        "Nobody Atall", "Iain M. Banks", "Robert Galbraith",
    ]  # fmt: skip
    by_name = dict(zip(names(page.text), rows(page.text), strict=True))
    assert "3 books · 2 read" in by_name["Terry Pratchett"]
    assert "1 book · 0 read" in by_name["Iain M. Banks"]
    assert "0 books · 0 read" in by_name["Nobody Atall"]
    assert "pen name of J. K. Rowling" in by_name["Robert Galbraith"]
    assert "pen name" not in by_name["Terry Pratchett"]
    assert f'<a class="row-name" href="/authors/{pratchett}">' in page.text
    marks = stars(page.text)
    assert set(marks) == {str(a) for a in (pratchett, banks, galbraith, austen, lonely)}
    assert marks[str(pratchett)]["favorite"] == "no"
    assert marks[str(banks)]["favorite"] == "yes"
    assert marks[str(pratchett)]["back"] == "/authors"


# --------------------------------------------------------------------------- AC-03 search


@pytest.mark.ac("018/AC-03")
async def test_authors_search(member: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    await factory.author("Terry Pratchett", alice, sort_name="Pratchett, Terry")
    await factory.author("Iain M. Banks", alice, sort_name="Banks, Iain M.")
    await factory.author("Robert Galbraith", alice, is_pen_name=True, real_name="J. K. Rowling")
    await factory.author("100% Pure", alice)
    await factory.author("1000 Pure", alice)
    await factory.author("snake_case", alice)
    await factory.author("snakeXcase", alice)

    assert names((await member.get("/authors?q=PRAT")).text) == ["Terry Pratchett"]
    assert names((await member.get("/authors?q=banks,")).text) == ["Iain M. Banks"]
    assert names((await member.get("/authors?q=rowling")).text) == ["Robert Galbraith"]
    assert names((await member.get("/authors?q=100%25")).text) == ["100% Pure"]
    assert names((await member.get("/authors?q=snake_")).text) == ["snake_case"]

    partial = await member.get("/authors?q=prat", headers={"HX-Request": "true"})
    assert "<html" not in partial.text and "nav-places" not in partial.text
    assert names(partial.text) == ["Terry Pratchett"]

    none = await member.get("/authors?q=zzz")
    assert "No authors match “zzz”." in words(none.text)
    assert '<a href="/authors">Clear search</a>' in none.text
    form = section(none.text, r'(<form method="get" action="/authors".*?>)')
    assert 'hx-get="/authors"' in form and 'hx-target="#authors-list"' in form
    assert "input changed delay:300ms from:#q" in form


# --------------------------------------------------------------------------- AC-04 favorites


@pytest.mark.ac("018/AC-04")
async def test_favorites_only(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    pratchett = await factory.author("Terry Pratchett", alice)
    banks = await factory.author("Iain M. Banks", alice)
    page = await member.get("/authors")
    form = section(page.text, r'(<form method="get" action="/authors".*?</form>)')
    assert 'type="checkbox" id="favorites" name="favorites" value="1"' in form
    assert "change from:#favorites" in form
    assert re.search(r'<button type="submit">Apply</button>', form)

    # With none, the spec 017 empty text and Browse the Catalog.
    await factory.favorite(ben, banks)
    empty = await member.get("/authors?favorites=1")
    assert names(empty.text) == []
    assert "You haven't chosen any favorite authors yet." in words(empty.text)
    assert '<a href="/catalog">Browse the Catalog</a>' in empty.text
    assert 'id="favorites" name="favorites" value="1" checked' in empty.text

    await factory.favorite(alice, pratchett)
    mine = await member.get("/authors?favorites=1")
    assert names(mine.text) == ["Terry Pratchett"]
    assert '<a href="/?author_id=favorites">My books by these authors</a>' in mine.text
    assert "haven't chosen" not in mine.text
    none = await member.get("/authors?favorites=1&q=zzz")
    assert "No authors match “zzz”." in words(none.text)
    assert '<a href="/authors?favorites=1">Clear search</a>' in none.text


# --------------------------------------------------------------------------- AC-05 stars


@pytest.mark.ac("018/AC-05")
async def test_star_returns_to_the_authors_page(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    for i in range(55):
        await factory.author(f"Writer {i:02}", alice)
    target = await factory.author("Writer 99", alice)
    await factory.favorite(alice, target)
    page = await member.get("/authors?q=writer&favorites=1&page=1")
    back = stars(page.text)[str(target)]["back"]
    assert back == "/authors?q=writer&favorites=1&page=1"

    address = "/authors?q=writer&page=2"
    listed = await member.get(address)
    mark = stars(listed.text)
    some = next(iter(mark))
    assert mark[some]["back"] == address
    saved = await member.post(
        f"/authors/{some}/favorite",
        data={
            "favorite": "yes",
            "back": mark[some]["back"],
            "csrf_token": mark[some]["csrf_token"],
        },
    )
    assert saved.status_code == 303
    location = saved.headers["location"]
    parts = urlsplit(location)
    assert parts.path == "/authors" and parts.fragment == "favorite-notice"
    assert parse_qs(parts.query) == {"q": ["writer"], "page": ["2"], "favorited": [some]}
    landed = await member.get(location)
    assert 'id="favorite-notice"' in landed.text
    assert "Added Writer" in words(section(landed.text, r'id="favorite-notice">(.*?)</p>'))

    # Unfavoriting with Favorites only on: the author leaves the list; the notice names them.
    gone = await member.post(
        f"/authors/{target}/favorite",
        data={"favorite": "no", "back": back, "csrf_token": mark[some]["csrf_token"]},
    )
    after = await member.get(gone.headers["location"])
    assert "Writer 99" not in names(after.text)
    assert "Removed Writer 99 from your favorite authors." in words(after.text)


# --------------------------------------------------------------------------- AC-06 pages


@pytest.mark.ac("018/AC-06")
async def test_authors_pages(member: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    for i in range(51):
        author = await factory.author(f"Writer {i:02}", alice)
        await factory.favorite(alice, author)
    first = await member.get("/authors?q=writer&favorites=1")
    assert len(names(first.text)) == 50
    assert 'href="/authors?q=writer&amp;favorites=1&amp;page=2">Next</a>' in first.text
    assert "Page 1 of 2" in first.text
    second = await member.get("/authors?q=writer&favorites=1&page=2")
    assert names(second.text) == ["Writer 50"]
    assert 'href="/authors?q=writer&amp;favorites=1&amp;page=1">Previous</a>' in second.text
    beyond = await member.get("/authors?q=writer&favorites=1&page=9")
    assert names(beyond.text) == ["Writer 50"]  # clamped to the last page


# --------------------------------------------------------------------------- AC-07 old address


@pytest.mark.ac("018/AC-07")
async def test_old_favorites_address_redirects(member: httpx.AsyncClient) -> None:
    moved = await member.get("/authors/favorites")
    assert moved.status_code == 302
    assert moved.headers["location"] == "/authors?favorites=1"
    linking = [
        str(p.relative_to(TEMPLATES))
        for p in TEMPLATES.rglob("*.html")
        if "/authors/favorites" in p.read_text()
    ]
    assert linking == []
    assert not (TEMPLATES / "pages/favorite_authors.html").exists()


@pytest.mark.ac("018/AC-07")
async def test_author_page_links_to_favorites_only(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    author = await factory.author("Terry Pratchett", alice)
    page = await member.get(f"/authors/{author}")
    assert '<a href="/authors?favorites=1">My favorite authors</a>' in page.text


# --------------------------------------------------------------------------- AC-08 unused


@pytest.mark.ac("018/AC-08")
async def test_unused_authors_link_moves(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    await factory.author("Nobody Atall", alice)
    await factory.author("Also Nobody", alice)
    link = '<a href="/catalog/authors/unused">Authors with no books (2)</a>'
    assert link in (await member.get("/authors")).text
    assert "/catalog/authors/unused" not in (await member.get("/")).text
    assert link not in (await member.get("/authors", headers={"HX-Request": "true"})).text


# --------------------------------------------------------------------------- shared helpers


def days(n: int) -> date:
    return TODAY + timedelta(days=n)


# --------------------------------------------------------------------------- US2 Upcoming


@pytest.fixture
async def coming(factory: Factory, alice: TestUser, ben: TestUser) -> dict[str, uuid.UUID]:
    """One of mine out last week, one of mine coming, a catalog book coming, and Ben's
    own newly-out book."""
    out = await factory.book("Out Last Week", alice, release_date=days(-7))
    soon = await factory.book("Mine Next Month", alice, release_date=days(30))
    other = await factory.book("Catalog Coming", alice, release_date=days(60))
    bens = await factory.book("Ben's New One", ben, release_date=days(-2))
    return {
        "out": out,
        "e_out": await factory.entry(alice, out, status="want_to_read"),
        "e_soon": await factory.entry(alice, soon, status="want_to_read"),
        "other": other,
        "e_bens": await factory.entry(ben, bens, status="want_to_read"),
    }


@pytest.mark.ac("018/AC-09")
async def test_my_books_has_no_upcoming_checkbox(
    member: httpx.AsyncClient, coming: dict[str, uuid.UUID]
) -> None:
    page = (await member.get("/")).text
    assert 'name="upcoming"' not in page and "Upcoming only" not in page
    assert "Soonest first" not in page
    assert ">My favorite authors</a>" not in page
    assert '<option value="favorites">My favorite authors</option>' in page


@pytest.mark.ac("018/AC-10")
async def test_old_upcoming_address_redirects(member: httpx.AsyncClient) -> None:
    for address in ("/?upcoming=1", "/?upcoming=1&sort=-title&status=want_to_read&q=x"):
        moved = await member.get(address)
        assert moved.status_code == 302, address
        assert moved.headers["location"] == "/upcoming"
    assert (await member.get("/?upcoming=yes")).status_code == 200  # anything but 1 is off


@pytest.mark.ac("018/AC-11")
@pytest.mark.ac("018/AC-13")
async def test_upcoming_sections_in_order(
    member: httpx.AsyncClient, other: httpx.AsyncClient, coming: dict[str, uuid.UUID]
) -> None:
    page = html.unescape((await member.get("/upcoming")).text)
    now_out = section(
        page, r'<section id="now-out" aria-labelledby="now-out-heading">(.*?)</section>'
    )
    assert '<h2 id="now-out-heading">Now out</h2>' in now_out
    assert f'<a href="/entries/{coming["e_out"]}">Out Last Week</a>' in now_out
    assert "Ben's New One" not in page  # another member's Now out never shows
    starts = [page.index(h) for h in ("Now out</h2>", "On my list</h2>",
                                      "Also coming in the family catalog</h2>")]  # fmt: skip
    assert starts == sorted(starts)
    assert "Mine Next Month" in page[starts[1] : starts[2]]
    assert "Catalog Coming" in page[starts[2] :]
    theirs = html.unescape((await other.get("/upcoming")).text)
    assert "Ben's New One" in section(theirs, r'<section id="now-out"[^>]*>(.*?)</section>')
    assert "Out Last Week" not in theirs.split("On my list</h2>")[0]


@pytest.mark.ac("018/AC-11")
async def test_no_now_out_section_without_books(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Finished Already", alice, release_date=days(-3))
    await factory.entry(alice, book, status="finished")
    page = (await member.get("/upcoming")).text
    assert 'id="now-out"' not in page and "Now out" not in page


@pytest.mark.ac("018/AC-12")
async def test_my_books_points_to_now_out(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, coming: dict[str, uuid.UUID]
) -> None:
    pointer = re.compile(
        r'<p class="now-out-pointer" role="status"><a href="/upcoming#now-out">(.*?)</a></p>'
    )
    page = (await member.get("/")).text
    assert pointer.findall(page) == ["1 book you want to read is now out"]
    assert 'id="now-out"' not in page and "Now out:" not in page
    assert page.index("now-out-pointer") < page.index('role="search"')
    another = await factory.book("Also Out", alice, release_date=days(-1))
    await factory.entry(alice, another, status="want_to_read")
    page = (await member.get("/")).text
    assert pointer.findall(page) == ["2 books you want to read are now out"]
    partial = (await member.get("/", headers={"HX-Request": "true"})).text
    assert "now-out-pointer" not in partial
    await factory.execute(
        "UPDATE reading_entry SET status = 'finished' WHERE user_id = :u", u=alice.id
    )
    assert "now-out-pointer" not in (await member.get("/")).text


# --------------------------------------------------------------------------- US3 Series view


def switch(page: str) -> list[tuple[str, str, bool]]:
    nav = section(page, r'<nav class="catalog-switch" aria-label="Catalog view">(.*?)</nav>')
    return [
        (href, words(label), "aria-current" in rest)
        for href, rest, label in re.findall(r'<a href="([^"]*)"([^>]*)>(.*?)</a>', nav, re.S)
    ]


@pytest.mark.ac("018/AC-14")
async def test_books_series_switch(member: httpx.AsyncClient) -> None:
    books = (await member.get("/catalog")).text
    assert switch(books) == [("/catalog", "Books", True), ("/catalog/series", "Series", False)]
    assert books.index("<h1>Catalog</h1>") < books.index('class="catalog-switch"')
    series = (await member.get("/catalog/series")).text
    assert switch(series) == [("/catalog", "Books", False), ("/catalog/series", "Series", True)]
    assert "<h1>Catalog</h1>" in series


@pytest.mark.ac("018/AC-15")
async def test_series_rows(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    disc = await factory.series("Discworld", alice)
    culture = await factory.series("the Culture", alice)
    tales = await factory.series("Anthology Tales", alice)
    author = await factory.author("Terry Pratchett", alice)
    books = [await factory.book(f"D{i}", alice, series_id=disc) for i in range(12)]
    await factory.book("Excession", alice, series_id=culture)
    for book in books[:4]:
        await factory.entry(alice, book, status="finished")
    await factory.entry(ben, books[5], status="finished")
    host = await factory.book("Host Book", alice)
    await factory.story("A Tale", alice, series_id=tales, series_number="1",
                        author_ids=[author], book_ids=[host])  # fmt: skip

    page = (await member.get("/catalog/series")).text
    assert names(page, "series-row") == ["Anthology Tales", "Discworld", "the Culture"]
    by_name = dict(zip(names(page, "series-row"), rows(page, "series-row"), strict=True))
    assert "12 books · 4 read" in by_name["Discworld"]
    assert "1 book · 0 read" in by_name["the Culture"]
    assert "0 books · 0 read" in by_name["Anthology Tales"]  # stories only
    assert f'<a class="row-name" href="/series/{disc}">Discworld</a>' in page


@pytest.mark.ac("018/AC-16")
async def test_series_search_and_pages(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    await factory.series("Discworld", alice)
    await factory.series("100% Series", alice)
    await factory.series("1000 Series", alice)
    assert names((await member.get("/catalog/series?q=DISC")).text, "series-row") == ["Discworld"]
    assert names((await member.get("/catalog/series?q=100%25")).text, "series-row") == [
        "100% Series"
    ]
    none = (await member.get("/catalog/series?q=zzz")).text
    assert "No series match “zzz”." in words(none)
    assert '<a href="/catalog/series">Clear search</a>' in none
    form = section(none, r'(<form method="get" action="/catalog/series".*?>)')
    assert 'hx-target="#series-list"' in form and "input changed delay:300ms from:#q" in form
    partial = await member.get("/catalog/series?q=disc", headers={"HX-Request": "true"})
    assert "<html" not in partial.text and names(partial.text, "series-row") == ["Discworld"]

    for i in range(49):
        await factory.series(f"Saga {i:02}", alice)
    first = (await member.get("/catalog/series")).text
    assert len(names(first, "series-row")) == 50
    assert 'href="/catalog/series?page=2">Next</a>' in first
    second = (await member.get("/catalog/series?page=2")).text
    assert names(second, "series-row") == ["Saga 47", "Saga 48"]
    searched = (await member.get("/catalog/series?q=saga&page=1")).text
    assert "Next" not in searched and len(names(searched, "series-row")) == 49


# --------------------------------------------------------------------------- US4 privacy


@pytest.mark.ac("018/AC-17")
async def test_another_members_data_never_shows(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    disc = await factory.series("Discworld", alice)
    zed = await factory.author("Zed Zebra", alice)  # last by sort name
    amy = await factory.author("Amy Aardvark", alice)
    book = await factory.book("Zed's Book", alice, author_ids=[zed], series_id=disc)
    await factory.favorite(ben, zed)
    await factory.entry(ben, book, status="finished")
    out = await factory.book("Ben's Release", ben, author_ids=[amy], release_date=days(-1))
    await factory.entry(ben, out, status="want_to_read")

    page = (await member.get("/authors")).text
    assert names(page) == ["Amy Aardvark", "Zed Zebra"]  # Ben's favorite isn't first
    assert {k: v["favorite"] for k, v in stars(page).items()} == {str(amy): "yes", str(zed): "yes"}
    assert "1 book · 0 read" in dict(zip(names(page), rows(page), strict=True))["Zed Zebra"]
    only = (await member.get("/authors?favorites=1")).text
    assert names(only) == [] and "You haven't chosen any favorite authors yet." in words(only)
    series = (await member.get("/catalog/series")).text
    assert "1 book · 0 read" in rows(series, "series-row")[0]
    assert "now-out" not in (await member.get("/")).text
    assert 'id="now-out"' not in (await member.get("/upcoming")).text


# --------------------------------------------------------------------------- PR #43 review


@pytest.mark.ac("018/AC-05")
async def test_notice_links_to_the_author(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    """Starring moves the row (favorites first), so the notice links to the author."""
    for i in range(55):
        await factory.author(f"Writer {i:02}", alice)
    page = await member.get("/authors?q=writer&page=2")
    author, fields = next(iter(stars(page.text).items()))
    saved = await member.post(f"/authors/{author}/favorite", data=fields)
    landed = (await member.get(saved.headers["location"])).text
    notice = section(landed, r'<p class="notice" role="status" id="favorite-notice">(.*?)</p>')
    assert re.search(rf'Added <a href="/authors/{author}">Writer \d\d</a> to your favorite', notice)


async def test_authors_page_reads_favorites_once(
    app: Any, member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    """PR #43 review: the page query already knows each row's favorite; no ``among``."""
    from sqlalchemy import event

    for i in range(5):
        await factory.favorite(alice, await factory.author(f"Writer {i}", alice))
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(str(args[2]))

    engine = app.state.db.engine.sync_engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        page = await member.get("/authors", headers={"HX-Request": "true"})
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert {v["favorite"] for v in stars(page.text).values()} == {"no"}
    alone = [s for s in statements if re.match(r"SELECT favorite_author\.author_id\s+FROM", s)]
    assert alone == [], alone


@pytest.mark.ac("018/AC-08")
async def test_unused_authors_page_leads_back_to_authors(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    await factory.author("Nobody Atall", alice)
    page = (await member.get("/catalog/authors/unused")).text
    assert '<a href="/authors">Back to Authors</a>' in page
    assert "Back to my books" not in page
    assert current(page) == ["Authors"]
