"""Spec 010: the Catalog page — every catalog book, searched, sorted, filtered and paged,
with On my list / Add to my list for the viewer only. Today is pinned to 22 Nov 2026."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in
from tests.integration.test_password_change import page_sign_in

TODAY = date(2026, 11, 22)
ROW = re.compile(  # spec 016 AC-07: a title opens the book page
    r'class="book-title" href="/books/([0-9a-f-]{36})">'
    r"([^<]+)</a>"
)


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def titles(body: str) -> list[str]:
    return [html.unescape(title) for _, title in ROW.findall(body)]


def count_text(body: str) -> str:
    found = re.search(r'<p class="muted" id="list-count" role="status">([^<]+)</p>', body)
    assert found, body
    return found.group(1)


@dataclass
class World:
    alice: TestUser
    ben: TestUser
    member: httpx.AsyncClient  # Alice
    other: httpx.AsyncClient  # Ben
    books: dict[str, uuid.UUID]
    series: dict[str, uuid.UUID]
    entries: dict[str, uuid.UUID]  # Alice's


@pytest.fixture
async def world(factory: Factory, client_factory: Callable[[], httpx.AsyncClient]) -> World:
    """T001: a small catalog. Alice has Storm Front and Emma; Ben has Fool Moon, finished,
    with a note."""
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    butcher = await factory.author("Jim Butcher", alice, sort_name="Butcher, Jim")
    austen = await factory.author("Jane Austen", alice, sort_name="Austen, Jane")
    galbraith = await factory.author(
        "Robert Galbraith",
        alice,
        sort_name="Galbraith, Robert",
        is_pen_name=True,
        real_name="J.K. Rowling",
    )
    dresden = await factory.series("The Dresden Files", alice)
    strike = await factory.series("Cormoran Strike", alice)
    books = {
        "storm": await factory.book(
            "Storm Front", alice, author_ids=[butcher], series_id=dresden, series_number="1"
        ),
        "fool": await factory.book(
            "Fool Moon", ben, author_ids=[butcher], series_id=dresden, series_number="2"
        ),
        "twenty": await factory.book(
            "Twenty Lives",
            alice,
            author_ids=[butcher],
            series_id=dresden,
            series_number="18",
            release_date=date(2027, 3, 3),
        ),
        "side": await factory.book("Side Jobs", alice, author_ids=[butcher]),
        "emma": await factory.book(
            "emma", alice, author_ids=[austen], isbn_13="9780141439587", release_date=TODAY
        ),
        "cuckoo": await factory.book(
            "The Cuckoo's Calling",
            alice,
            author_ids=[galbraith],
            series_id=strike,
            series_number="1",
        ),
        "percent": await factory.book("100% Proof", alice, author_ids=[austen]),
    }
    await factory.story(
        "Restoration of Faith",
        alice,
        series_id=dresden,
        series_number="1.5",
        author_ids=[butcher],
        book_ids=[books["side"]],
    )
    entries = {
        "storm": await factory.entry(alice, books["storm"], finished_on=date(2025, 3, 1)),
        "emma": await factory.entry(alice, books["emma"], status="want_to_read"),
    }
    await factory.entry(ben, books["fool"], finished_on=date(2025, 4, 2), notes="Ben's secret note")
    return World(
        alice=alice,
        ben=ben,
        member=await signed_in(client_factory(), alice),
        other=await signed_in(client_factory(), ben),
        books=books,
        series={"dresden": dresden, "strike": strike},
        entries=entries,
    )


ALL_BY_TITLE = [
    "100% Proof",
    "emma",
    "Fool Moon",
    "Side Jobs",
    "Storm Front",
    "The Cuckoo's Calling",
    "Twenty Lives",
]


# ------------------------------------------------------------------ US1: browse


@pytest.mark.ac("010/AC-01")
async def test_navigation_links_to_the_catalog(world: World) -> None:
    home = (await world.member.get("/")).text
    assert '<a href="/catalog">Catalog</a>' in home
    page = (await world.member.get("/catalog")).text
    assert '<a href="/catalog" aria-current="page">Catalog</a>' in page
    assert '<a href="/" aria-current="page">' not in page


@pytest.mark.ac("010/AC-02")
async def test_signed_out_and_password_change_are_sent_away(
    factory: Factory, client: httpx.AsyncClient, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    response = await client.get("/catalog")
    assert response.status_code == 303
    assert response.headers["location"] == "/sign-in"
    await factory.user("cara", must_change_password=True, password="temporary-1")
    browser = client_factory()
    await page_sign_in(browser, "cara", "temporary-1")
    blocked = await browser.get("/catalog")
    assert blocked.status_code == 303
    assert blocked.headers["location"] == "/account/password"


@pytest.mark.ac("010/AC-03")
async def test_lists_every_book_by_title_with_authors_and_series(world: World) -> None:
    page = await world.member.get("/catalog")
    assert page.status_code == 200
    assert "<h1>Catalog</h1>" in page.text
    assert count_text(page.text) == "7 books in the family catalog"
    assert titles(page.text) == ALL_BY_TITLE
    row = _row(page.text, world.books["cuckoo"])
    assert "Robert Galbraith" in row
    assert "Cormoran Strike #1" in row


@pytest.mark.ac("010/AC-04")
async def test_coming_date_only_while_not_out(world: World) -> None:
    page = (await world.member.get("/catalog")).text
    assert "Coming 3 Mar 2027" in _row(page, world.books["twenty"])
    assert "Coming" not in _row(page, world.books["emma"])  # out today
    assert "Coming" not in _row(page, world.books["storm"])  # no date


@pytest.mark.ac("010/AC-05")
async def test_title_and_series_links(world: World) -> None:
    page = (await world.member.get("/catalog")).text
    row = _row(page, world.books["fool"])
    assert f'href="/books/{world.books["fool"]}"' in row  # spec 016 AC-07
    assert f'href="/series/{world.series["dresden"]}"' in row
    assert "/series/" not in _row(page, world.books["side"])


@pytest.mark.ac("010/AC-06")
async def test_pages_of_fifty_keep_the_query(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    author = await factory.author("Prolific Writer", alice)
    for i in range(1, 121):
        await factory.book(f"Book {i:03d}", alice, author_ids=[author])
    member = await signed_in(client_factory(), alice)
    first = (await member.get("/catalog", params={"q": "book", "sort": "-title"})).text
    assert len(titles(first)) == 50
    assert titles(first)[0] == "Book 120"
    assert "Page 1 of 3" in first
    assert 'href="/catalog?q=book&amp;sort=-title&amp;page=2">Next</a>' in first
    assert "Previous</a>" not in first
    third = (await member.get("/catalog", params={"q": "book", "sort": "-title", "page": 3})).text
    assert titles(third) == [f"Book {i:03d}" for i in range(20, 0, -1)]
    assert 'href="/catalog?q=book&amp;sort=-title&amp;page=2">Previous</a>' in third
    assert "Next</a>" not in third
    past = (await member.get("/catalog", params={"page": 99})).text
    assert "Page 3 of 3" in past and titles(past)[0] == "Book 101"
    for bad in ("0", "-1", "two", "", "²", "9" * 5000):
        shown = (await member.get("/catalog", params={"page": bad})).text
        assert "Page 1 of 3" in shown, bad


@pytest.mark.ac("010/AC-07")
async def test_empty_catalog(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    member = await signed_in(client_factory(), await factory.user("alice"))
    page = (await member.get("/catalog")).text
    assert "The family catalog is empty." in page
    assert 'href="/books/add"' in page
    assert 'class="book-list catalog-list"' not in page


# ------------------------------------------------------------------ US2: add to my list


@pytest.mark.ac("010/AC-08")
async def test_on_my_list_links_to_my_entry(world: World) -> None:
    page = (await world.member.get("/catalog")).text
    row = _row(page, world.books["storm"])
    # Spec 015 AC-08: my status as a badge linking to my entry, not "On my list".
    mine = f'<a class="badge status-link" href="/entries/{world.entries["storm"]}">'
    assert mine in row and '<span class="visually-hidden">: “Storm Front”</span></a>' in row
    assert "/books/add?book=" not in row and "want-to-read" not in row


@pytest.mark.ac("010/AC-09")
async def test_add_to_my_list_starts_from_the_book(world: World) -> None:
    page = (await world.member.get("/catalog")).text
    row = _row(page, world.books["fool"])
    assert f'href="/books/add?book={world.books["fool"]}"' in row
    # Spec 015 AC-01: "Add with details…" beside the one-tap Want to read.
    assert '<span class="visually-hidden"> “Fool Moon”</span> with details…' in row
    assert "Not on my list" in row and f'action="/books/{world.books["fool"]}/want-to-read"' in row
    started = await world.member.get(f"/books/add?book={world.books['fool']}")
    assert started.status_code == 200 and "Fool Moon" in started.text


@pytest.mark.ac("010/AC-10")
async def test_other_members_entries_leave_no_trace(world: World, factory: Factory) -> None:
    page = (await world.member.get("/catalog")).text
    # My own statuses show since spec 015; Ben's never do (the row check below).
    for leak in ("Ben", "secret", "2 Apr 2025"):
        assert leak not in page, leak
    # Ben finished Fool Moon, with a note: its row is the same as when nobody has it.
    with_bens = _row(page, world.books["fool"])
    await factory.execute("DELETE FROM reading_entry WHERE user_id = :u", u=world.ben.id)
    without = _row((await world.member.get("/catalog")).text, world.books["fool"])
    assert with_bens == without
    # And Ben sees Alice's books as books he can add.
    seen_by_ben = (await world.other.get("/catalog")).text
    assert f'href="/books/add?book={world.books["storm"]}"' in seen_by_ben
    assert f"/entries/{world.entries['storm']}" not in seen_by_ben


# ------------------------------------------------------------------ US3: search, sort, filter


@pytest.mark.ac("010/AC-11")
@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("STORM", ["Storm Front"]),
        ("butcher", ["Fool Moon", "Side Jobs", "Storm Front", "Twenty Lives"]),
        ("rowling", ["The Cuckoo's Calling"]),
        ("cormoran", ["The Cuckoo's Calling"]),
        ("restoration", ["Side Jobs"]),
        ("100%", ["100% Proof"]),
        ("_", []),
    ],
)
async def test_search_fields(world: World, q: str, expected: list[str]) -> None:
    page = (await world.member.get("/catalog", params={"q": q})).text
    assert titles(page) == expected
    if expected:
        n = len(expected)
        assert count_text(page) == (f"{n} books match" if n > 1 else "1 book matches")


@pytest.mark.ac("010/AC-11")
async def test_search_is_cut_to_200_characters(world: World) -> None:
    page = (await world.member.get("/catalog", params={"q": "Storm Front" + "x" * 300})).text
    assert 'value="Storm Front' in page
    assert "x" * 201 not in page


@pytest.mark.ac("010/AC-11")
async def test_search_ignores_nul_characters(world: World) -> None:
    page = await world.member.get("/catalog", params={"q": "Sto\x00rm"})
    assert page.status_code == 200
    assert titles(page.text) == ["Storm Front"]


@pytest.mark.ac("010/AC-12")
async def test_isbn_match_is_first(world: World, factory: Factory) -> None:
    # A book titled with the ISBN digits would also match; the ISBN owner still comes first.
    await factory.book("A 978-0-14-143958-7 study", world.alice)
    page = (await world.member.get("/catalog", params={"q": "978-0-14-143958-7"})).text
    assert titles(page) == ["emma", "A 978-0-14-143958-7 study"]
    spaced = (await world.member.get("/catalog", params={"q": " 978 0141439587 "})).text
    assert titles(spaced)[0] == "emma"


@pytest.mark.ac("010/AC-13")
@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("title", ALL_BY_TITLE),
        ("-title", list(reversed(ALL_BY_TITLE))),
        (
            "author",
            [
                "100% Proof",
                "emma",
                "Fool Moon",
                "Side Jobs",
                "Storm Front",
                "Twenty Lives",
                "The Cuckoo's Calling",
            ],
        ),
        (
            "series",
            [
                "The Cuckoo's Calling",
                "Storm Front",
                "Fool Moon",
                "Twenty Lives",
                "100% Proof",
                "emma",
                "Side Jobs",
            ],
        ),
        ("nonsense", ALL_BY_TITLE),
    ],
)
async def test_sorts(world: World, sort: str, expected: list[str]) -> None:
    page = (await world.member.get("/catalog", params={"sort": sort})).text
    assert titles(page) == expected


@pytest.mark.ac("010/AC-13")
async def test_newest_in_the_catalog_first(world: World, factory: Factory) -> None:
    await factory.execute("UPDATE book SET created_at = now() - (interval '1 day' * length(title))")
    page = (await world.member.get("/catalog", params={"sort": "-added"})).text
    by_length = sorted(ALL_BY_TITLE, key=lambda t: (len(t), t.lower()))
    assert titles(page) == by_length
    assert '<option value="-added" selected>Newest in the catalog</option>' in page


@pytest.mark.ac("010/AC-14")
async def test_not_on_my_list_filter_is_mine_only(world: World) -> None:
    mine = (await world.member.get("/catalog", params={"not_mine": "1"})).text
    assert titles(mine) == [t for t in ALL_BY_TITLE if t not in ("Storm Front", "emma")]
    assert count_text(mine) == "5 books match"
    assert 'id="not_mine" name="not_mine" value="1" checked' in mine
    bens = (await world.other.get("/catalog", params={"not_mine": "1"})).text
    assert titles(bens) == [t for t in ALL_BY_TITLE if t != "Fool Moon"]
    ignored = (await world.member.get("/catalog", params={"not_mine": "yes"})).text
    assert titles(ignored) == ALL_BY_TITLE


@pytest.mark.ac("010/AC-15")
async def test_no_match(world: World) -> None:
    page = (await world.member.get("/catalog", params={"q": "zzz"})).text
    assert "No catalog books match." in page
    assert '<a href="/catalog">Show the whole catalog</a>' in page


@pytest.mark.ac("010/AC-16")
async def test_htmx_gets_just_the_list(world: World) -> None:
    full = (await world.member.get("/catalog", params={"q": "storm"})).text
    assert 'role="search"' in full and 'hx-get="/catalog"' in full
    assert 'hx-target="#catalog-list"' in full and 'hx-push-url="true"' in full
    assert '<div id="catalog-list">' in full and 'id="list-count" role="status"' in full
    assert 'hx-trigger="submit, change from:#sort, change from:#not_mine,' in full
    assert '<a id="catalog-clear" href="/catalog">Clear</a>' in full
    partial = await world.member.get(
        "/catalog", params={"q": "storm"}, headers={"HX-Request": "true"}
    )
    assert partial.status_code == 200
    assert "<h1>" not in partial.text and 'role="search"' not in partial.text
    assert titles(partial.text) == ["Storm Front"]
    assert partial.headers["vary"] == "HX-Request"
    # The count and Clear follow each update, out of band (PR #29 review).
    assert '<div hx-swap-oob="innerHTML:#list-count">1 book matches</div>' in partial.text
    assert '<a id="catalog-clear" href="/catalog" hx-swap-oob="true">Clear</a>' in partial.text
    cleared = await world.member.get("/catalog", headers={"HX-Request": "true"})
    assert (
        '<a id="catalog-clear" href="/catalog" hx-swap-oob="true" hidden>Clear</a>' in cleared.text
    )
    # An htmx history restore (Back, cache miss) gets the whole page.
    restored = await world.member.get(
        "/catalog",
        params={"q": "storm"},
        headers={"HX-Request": "true", "HX-History-Restore-Request": "true"},
    )
    assert "<h1>Catalog</h1>" in restored.text and 'role="search"' in restored.text


def _row(body: str, book_id: uuid.UUID) -> str:
    not_end = "(?:(?!</li>).)*"
    found = re.search(
        rf'<li class="catalog-row" id="book-{book_id}">{not_end}</li>',  # spec 015 rows
        body,
        re.S,
    )
    assert found, f"no row for {book_id}"
    return found.group(0)


@pytest.mark.ac("010/AC-06")
async def test_my_books_page_numbers_dont_crash(world: World) -> None:
    """The shared page parser (PR #29 review): "²" passes str.isdigit but not int()."""
    for bad in ("²", "9" * 5000):
        assert (await world.member.get("/", params={"page": bad})).status_code == 200
