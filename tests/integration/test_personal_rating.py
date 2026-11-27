"""Spec 020: a personal rating from 1 to 5 on each of a member's entries.

Contracts: specs/020-personal-rating/contracts/ui-rating.md and api-rating.md."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in, ui_csrf
from tests.fakes import FakeBookSource
from tests.integration.import_helpers import confirm_via_page, stock

OPTIONS = [
    ("", "No rating"),
    ("1", "1 – Didn't like it"),
    ("2", "2 – It was OK"),
    ("3", "3 – Liked it"),
    ("4", "4 – Really liked it"),
    ("5", "5 – Loved it"),
]
RATING_ERROR = "Choose a rating from 1 to 5, or No rating"


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
async def shelf(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    jim = await factory.author("Jim Butcher", alice)
    hobbit = await factory.book("The Hobbit", alice)
    return {
        "jim": jim,
        "hobbit": hobbit,
        "e_hobbit": await factory.entry(alice, hobbit),
    }


def text(page: httpx.Response | str) -> str:
    body = page if isinstance(page, str) else page.text
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())


def rating_select(page: str) -> str:
    found = re.search(r'<select id="rating" name="rating"[^>]*>.*?</select>', page, flags=re.S)
    assert found, "no Rating select"
    return found.group(0)


def options(page: str) -> list[tuple[str, str]]:
    return [
        (value, html.unescape(label).strip())
        for value, label in re.findall(
            r'<option value="([^"]*)"[^>]*>([^<]*)</option>', rating_select(page)
        )
    ]


def selected(page: str) -> str | None:
    found = re.search(r'<option value="([^"]*)" selected>', rating_select(page))
    return found.group(1) if found else None


async def rating_of(factory: Factory, entry_id: uuid.UUID) -> Any:
    return await factory.scalar("SELECT rating FROM reading_entry WHERE id = :id", id=entry_id)


async def rating_by_title(factory: Factory, title: str) -> Any:
    return await factory.scalar(
        "SELECT e.rating FROM reading_entry e JOIN book b ON b.id = e.book_id WHERE b.title = :t",
        t=title,
    )


def entry_form(**fields: str) -> dict[str, str]:
    return {"status": "finished", "times_read": "1", "notes": "", "pre_ordered": "", **fields}


def new_book(author: uuid.UUID, title: str = "Storm Front", **fields: str) -> dict[str, str]:
    return {
        "title": title, "author_id_0": str(author), "author_name_0": "Jim Butcher",
        "status": "finished", "then": "list", **fields,
    }  # fmt: skip


# --------------------------------------------------------------------------- US1


@pytest.mark.ac("020/AC-01")
async def test_rate_on_the_entry_page(
    member: httpx.AsyncClient, factory: Factory, shelf: dict[str, uuid.UUID]
) -> None:
    url = f"/entries/{shelf['e_hobbit']}"
    page = await member.get(url)
    assert '<label for="rating">Rating (optional)</label>' in page.text
    assert options(page.text) == OPTIONS
    assert selected(page.text) == ""
    saved = await member.post(url, data=entry_form(rating="4"))
    assert saved.status_code == 303, saved.text
    assert await rating_of(factory, shelf["e_hobbit"]) == 4
    assert selected((await member.get(url)).text) == "4"
    assert (await member.post(url, data=entry_form(rating="5"))).status_code == 303
    assert await rating_of(factory, shelf["e_hobbit"]) == 5


@pytest.mark.ac("020/AC-02")
async def test_no_rating_clears_it(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    rated = await factory.entry(alice, await factory.book("Dune", alice), rating=3)
    url = f"/entries/{rated}"
    assert selected((await member.get(url)).text) == "3"
    saved = await member.post(url, data=entry_form(rating=""))
    assert saved.status_code == 303, saved.text
    assert await rating_of(factory, rated) is None
    assert selected((await member.get(url)).text) == ""


@pytest.mark.ac("020/AC-03")
async def test_add_a_book_with_a_rating(
    member: httpx.AsyncClient, factory: Factory, shelf: dict[str, uuid.UUID]
) -> None:
    form = await member.get("/books/add")
    assert options(form.text) == OPTIONS and selected(form.text) == ""
    saved = await member.post("/books/add", data=new_book(shelf["jim"], rating="5"))
    assert saved.status_code == 303, saved.text
    assert await rating_by_title(factory, "Storm Front") == 5
    # Save and add another (spec 004): the next form starts with no rating.
    another = await member.post(
        "/books/add", data=new_book(shelf["jim"], "Fool Moon", rating="2", then="another")
    )
    assert another.status_code == 303, another.text
    assert await rating_by_title(factory, "Fool Moon") == 2
    follow = await member.get(another.headers["location"])
    assert selected(follow.text) == ""
    # With the anthology section (spec 013).
    anthology = new_book(
        shelf["jim"], "Side Jobs", rating="4", anthology="yes",
        story_title_0="Restoration of Faith",
    )  # fmt: skip
    saved = await member.post("/books/add", data=anthology)
    assert saved.status_code == 303, saved.text
    assert await rating_by_title(factory, "Side Jobs") == 4
    # An existing catalog book.
    dune = await factory.book("Dune", await factory.user("carol"))
    chosen = await member.post(
        "/books/add", data={"book_id": str(dune), "status": "reading", "rating": "3"}
    )
    assert chosen.status_code == 303, chosen.text
    assert await rating_by_title(factory, "Dune") == 3
    # No choice: no rating.
    plain = await member.post("/books/add", data=new_book(shelf["jim"], "Grave Peril"))
    assert plain.status_code == 303
    assert await rating_by_title(factory, "Grave Peril") is None


@pytest.mark.ac("020/AC-04")
@pytest.mark.parametrize("bad", ["6", "0", "x", "4.5"])
async def test_a_tampered_rating_saves_nothing(
    member: httpx.AsyncClient, factory: Factory, shelf: dict[str, uuid.UUID], bad: str
) -> None:
    url = f"/entries/{shelf['e_hobbit']}"
    refused = await member.post(url, data=entry_form(rating=bad, notes="Second breakfast"))
    assert refused.status_code == 422
    assert f'<p class="field-error" id="rating-error">{RATING_ERROR}</p>' in refused.text
    assert 'aria-describedby="rating-error"' in rating_select(refused.text)
    assert "Second breakfast" in refused.text
    assert await rating_of(factory, shelf["e_hobbit"]) is None
    assert (
        await factory.scalar("SELECT notes FROM reading_entry WHERE id = :id", id=shelf["e_hobbit"])
        is None
    )
    added = await member.post("/books/add", data=new_book(shelf["jim"], rating=bad))
    assert added.status_code == 422
    assert RATING_ERROR in added.text and 'value="Storm Front"' in added.text
    assert await factory.scalar("SELECT count(*) FROM book WHERE title = 'Storm Front'") == 0


@pytest.mark.ac("020/AC-05")
@pytest.mark.parametrize("status", ["want_to_read", "reading", "finished"])
async def test_any_status_can_be_rated_and_a_status_change_keeps_it(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, status: str
) -> None:
    times = "1" if status == "finished" else "0"
    entry = await factory.entry(alice, await factory.book("Dune", alice), status=status)
    url = f"/entries/{entry}"
    saved = await member.post(url, data=entry_form(status=status, times_read=times, rating="4"))
    assert saved.status_code == 303, saved.text
    assert await rating_of(factory, entry) == 4
    for new in ("finished", "reading", "want_to_read"):
        # A form without the Rating field (an older page) keeps it too.
        changed = await member.post(url, data={"status": new})
        assert changed.status_code == 303, changed.text
        assert await rating_of(factory, entry) == 4
    finished = await member.post(url, data={"status": "finished"})
    assert finished.status_code == 303
    again = await member.post(f"/entries/{entry}/read-again", data={})
    assert again.status_code in (200, 303), again.text
    assert await rating_of(factory, entry) == 4


async def test_quick_add_and_import_add_no_rating(
    member: httpx.AsyncClient,
    factory: Factory,
    alice: TestUser,
    ben: TestUser,
    book_source: FakeBookSource,
) -> None:
    """Edge Cases: the quick-add rows (spec 015) and import (spec 002)."""
    series = await factory.series("Discworld", ben)
    mort = await factory.book("Mort", ben, series_id=series, series_number="4")
    added = await member.post(
        f"/books/{mort}/want-to-read",
        data={"back": f"/series/{series}", "csrf_token": await ui_csrf(member)},
    )
    assert added.status_code == 303, added.text
    assert await rating_by_title(factory, "Mort") is None
    stock(book_source)
    done = await confirm_via_page(member, ["OL1W"])
    assert done.status_code == 200, done.text
    assert await rating_by_title(factory, "Book 1") is None


# --------------------------------------------------------------------------- US2


def list_rows(page: httpx.Response) -> dict[str, str]:
    """My books rows by title, as HTML."""
    body = page.text.split('<ul class="book-list reading-list"', 1)[1].split("</ul>", 1)[0]
    rows = re.findall(r"<li[^>]*>(.*?)</li>", body, flags=re.S)
    return {text(re.search(r'class="book-title"[^>]*>([^<]*)<', r).group(1)): r for r in rows}  # type: ignore[union-attr]


@pytest.fixture
async def rated(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for title, rating in (("Dune", 5), ("Emma", 2), ("Ivanhoe", None)):
        ids[title] = await factory.book(title, alice)
        ids[f"e_{title}"] = await factory.entry(alice, ids[title], rating=rating)
    return ids


@pytest.mark.ac("020/AC-06")
async def test_my_books_rows_show_the_rating(
    member: httpx.AsyncClient, rated: dict[str, uuid.UUID]
) -> None:
    rows = list_rows(await member.get("/"))
    assert '<div class="book-rating">Rated 5 out of 5</div>' in rows["Dune"]
    assert '<div class="book-rating">Rated 2 out of 5</div>' in rows["Emma"]
    assert "book-rating" not in rows["Ivanhoe"] and "Rated" not in text(rows["Ivanhoe"])
    for row in rows.values():
        assert not re.search("[★☆⭐]", row)


@pytest.mark.ac("020/AC-07")
async def test_book_page_shows_my_rating(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, rated: dict[str, uuid.UUID]
) -> None:
    dune = await member.get(f"/books/{rated['Dune']}")
    status = re.search(r'<p class="row-status">(.*?)</p>', dune.text, flags=re.S)
    assert status and text(status.group(1)).endswith("· Rated 5 out of 5")
    unrated = await member.get(f"/books/{rated['Ivanhoe']}")
    assert "Rated" not in text(unrated)
    not_mine = await member.get(f"/books/{await factory.book('Persuasion', alice)}")
    assert "Not on my list" in text(not_mine) and "Rated" not in text(not_mine)


# --------------------------------------------------------------------------- US3


@pytest.fixture
async def spread(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    """Rated 5, 4 and 2, and two unrated (Ivanhoe, Beowulf)."""
    ids: dict[str, uuid.UUID] = {}
    for title, rating, status in (
        ("Middlemarch", 4, "finished"), ("Dune", 5, "finished"), ("Emma", 2, "reading"),
        ("Ivanhoe", None, "finished"), ("Beowulf", None, "want_to_read"),
    ):  # fmt: skip
        ids[title] = await factory.book(title, alice)
        ids[f"e_{title}"] = await factory.entry(alice, ids[title], rating=rating, status=status)
    return ids


async def titles(client: httpx.AsyncClient, **params: str) -> list[str]:
    page = await client.get("/", params=params)
    assert page.status_code == 200, page.text
    if '<ul class="book-list reading-list"' not in page.text:
        return []
    return list(list_rows(page))


@pytest.mark.ac("020/AC-08")
async def test_sort_by_rating(member: httpx.AsyncClient, spread: dict[str, uuid.UUID]) -> None:
    page = await member.get("/")
    sort = re.search(r'<select id="sort" name="sort">.*?</select>', page.text, flags=re.S)
    assert sort and '<option value="-rating">Highest rated</option>' in sort.group(0)
    assert '<option value="rating">Lowest rated</option>' in sort.group(0)
    assert await titles(member, sort="-rating") == [
        "Dune", "Middlemarch", "Emma", "Beowulf", "Ivanhoe"
    ]  # fmt: skip
    assert await titles(member, sort="rating") == [
        "Emma", "Middlemarch", "Dune", "Beowulf", "Ivanhoe"
    ]  # fmt: skip
    chosen = await member.get("/", params={"sort": "-rating"})
    assert '<option value="-rating" selected>Highest rated</option>' in chosen.text


RATING_FILTER = [
    ("", "Any rating"), ("5", "5"), ("4", "4 and up"), ("3", "3 and up"), ("2", "2 and up"),
    ("rated", "Rated"), ("unrated", "Not rated"),
]  # fmt: skip


@pytest.mark.ac("020/AC-09")
async def test_filter_by_rating(member: httpx.AsyncClient, spread: dict[str, uuid.UUID]) -> None:
    page = await member.get("/")
    select = re.search(r'<select id="rating" name="rating">(.*?)</select>', page.text, flags=re.S)
    assert select and '<label for="rating">Rating</label>' in page.text
    found = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', select.group(1))
    assert found == RATING_FILTER
    expected = {
        "5": ["Dune"],
        "4": ["Dune", "Middlemarch"],
        "3": ["Dune", "Middlemarch"],
        "2": ["Dune", "Emma", "Middlemarch"],
        "rated": ["Dune", "Emma", "Middlemarch"],
        "unrated": ["Beowulf", "Ivanhoe"],
        "": ["Beowulf", "Dune", "Emma", "Ivanhoe", "Middlemarch"],
        "1": ["Beowulf", "Dune", "Emma", "Ivanhoe", "Middlemarch"],  # not a choice: ignored
        "9": ["Beowulf", "Dune", "Emma", "Ivanhoe", "Middlemarch"],
        "x": ["Beowulf", "Dune", "Emma", "Ivanhoe", "Middlemarch"],
    }
    for value, books in expected.items():
        assert await titles(member, rating=value) == books, value
    chosen = await member.get("/", params={"rating": "4"})
    assert '<option value="4" selected>4 and up</option>' in chosen.text
    ignored = await member.get("/", params={"rating": "x"})
    assert '<option value="" selected>Any rating</option>' in ignored.text
    assert "No books on your list match" in (await member.get("/?rating=5&status=reading")).text


@pytest.mark.ac("020/AC-10")
async def test_rating_filter_combines_and_is_kept(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, spread: dict[str, uuid.UUID]
) -> None:
    assert await titles(member, rating="rated", status="finished") == ["Dune", "Middlemarch"]
    assert await titles(member, rating="unrated", q="Beo") == ["Beowulf"]
    assert await titles(member, rating="2", sort="-rating") == ["Dune", "Middlemarch", "Emma"]
    # Paging: 60 more rated 3 (pages hold 50); the links keep the filter.
    for n in range(60):
        await factory.entry(alice, await factory.book(f"Rated {n:02}", alice), rating=3)
    first = await member.get("/", params={"rating": "3"})
    assert "62 books" in text(first)  # the 60, Dune and Middlemarch
    nxt = re.search(r'href="(/\?[^"]*page=2)"', first.text)
    assert nxt and "rating=3" in html.unescape(nxt.group(1))
    second = await member.get(html.unescape(nxt.group(1)))
    assert len(list_rows(second)) == 12
    # Clear (spec 018) shows with only the rating filter, and drops it.
    clear = re.search(r'<span id="list-clear"([^>]*)><a href="([^"]*)">Clear filters', first.text)
    assert clear and "hidden" not in clear.group(1) and clear.group(2) == "/"
    plain = await member.get("/")
    assert re.search(r'<span id="list-clear"[^>]*hidden', plain.text)
    # HTMX gets just the list, with Clear swapped in.
    htmx = await member.get("/", params={"rating": "5"}, headers={"HX-Request": "true"})
    assert "<h1>" not in htmx.text and 'id="list-clear" hx-swap-oob="true">' in htmx.text
    # The sort alone isn't a filter.
    sorted_only = await member.get("/", params={"sort": "-rating"})
    assert re.search(r'<span id="list-clear"[^>]*hidden', sorted_only.text)


# --------------------------------------------------------------------------- US4: privacy


@pytest.mark.ac("020/AC-12")
async def test_another_members_rating_is_never_shown(
    member: httpx.AsyncClient,
    other: httpx.AsyncClient,
    factory: Factory,
    alice: TestUser,
    ben: TestUser,
) -> None:
    """Ben rates Mort and Small Gods 5; Alice has Mort unrated and Small Gods not at all."""
    terry = await factory.author("Terry Pratchett", ben)
    disc = await factory.series("Discworld", ben)
    mort = await factory.book("Mort", ben, author_ids=[terry], series_id=disc, series_number="4")
    gods = await factory.book("Small Gods", ben, author_ids=[terry], series_id=disc,
                              series_number="13")  # fmt: skip
    await factory.story("Troll Bridge", ben, series_id=None, series_number=None,
                        author_ids=[terry], book_ids=[mort])  # fmt: skip
    ben_mort = await factory.entry(ben, mort, rating=5)
    await factory.entry(ben, gods, rating=5)
    alice_mort = await factory.entry(alice, mort)
    others = [await factory.entry(alice, await factory.book(f"Mine {n}", alice)) for n in range(2)]

    # Ben's entry: 404 for Alice, by page and API, and unchanged.
    assert (await member.get(f"/entries/{ben_mort}")).status_code == 404
    assert (
        await member.post(f"/entries/{ben_mort}", data=entry_form(rating="1"))
    ).status_code == 404
    assert (await member.get(f"/api/v1/me/readings/{ben_mort}")).status_code == 404
    patched = await member.patch(f"/api/v1/me/readings/{ben_mort}", json={"rating": 1})
    assert patched.status_code == 404
    assert await rating_of(factory, ben_mort) == 5

    # Ben sees his own rating; Alice sees none of it anywhere.
    assert "Rated 5 out of 5" in text(await other.get(f"/books/{mort}"))
    pages = [
        f"/books/{mort}", f"/books/{gods}", f"/series/{disc}", f"/authors/{terry}",
        "/catalog", "/catalog?q=Mort", "/catalog/series", "/upcoming", "/",
        f"/entries/{alice_mort}",
        "/suggest/books?q=Mort", "/suggest/stories?q=Troll", "/suggest/series?q=Disc",
        "/suggest/authors?q=Terry",
    ]  # fmt: skip
    for path in pages:
        page = await member.get(path)
        assert page.status_code == 200, (path, page.text)
        assert not re.search(r"Rated \d out of 5", text(page)), path
    for path in (
        f"/api/v1/books/{mort}", "/api/v1/books?q=Mort", f"/api/v1/books/{mort}/stories",
        f"/api/v1/series/{disc}", f"/api/v1/authors/{terry}", "/api/v1/me/readings",
        f"/api/v1/me/readings/{alice_mort}", f"/api/v1/me/series/{disc}",
    ):  # fmt: skip
        response = await member.get(path)
        assert response.status_code == 200, (path, response.text)
        assert '"rating":5' not in response.text.replace(" ", ""), path
    # The list filters and sort hold only Alice's own entries.
    mine = {str(alice_mort), *map(str, others)}
    for params in ({"rated": "true"}, {"min_rating": "4"}, {"sort": "-rating"}):
        body = (await member.get("/api/v1/me/readings", params=params)).json()
        assert {item["id"] for item in body["items"]} <= mine, params
        assert all(item["rating"] is None for item in body["items"]), params
    for params in ({"rating": "rated"}, {"rating": "4"}, {"rating": "5"}):
        assert await titles(member, **params) == [], params
    assert await titles(member, sort="-rating") == ["Mine 0", "Mine 1", "Mort"]
