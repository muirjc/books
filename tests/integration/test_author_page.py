"""Spec 011: the Author page — books by series with my own statuses, stories, links to it,
and marking a favorite. Today is pinned to 22 Nov 2026."""

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

ROW = re.compile(  # spec 016 AC-07: a title opens the book page
    r'class="book-title" href="/books/([0-9a-f-]{36})">'
    r"([^<]+)</a>"
)


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def titles(body: str) -> list[str]:
    return [html.unescape(t) for _, t in ROW.findall(body)]


def csrf(body: str) -> str:
    found = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert found
    return found.group(1)


@dataclass
class World:
    alice: TestUser
    ben: TestUser
    member: httpx.AsyncClient
    other: httpx.AsyncClient
    butcher: uuid.UUID
    galbraith: uuid.UUID
    dresden: uuid.UUID
    books: dict[str, uuid.UUID]
    entries: dict[str, uuid.UUID]


@pytest.fixture
async def world(factory: Factory, client_factory: Callable[[], httpx.AsyncClient]) -> World:
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    butcher = await factory.author("Jim Butcher", alice, sort_name="Butcher, Jim")
    galbraith = await factory.author(
        "Robert Galbraith", alice, sort_name="Galbraith, Robert", is_pen_name=True,
        real_name="J.K. Rowling",
    )  # fmt: skip
    dresden = await factory.series("The Dresden Files", alice)
    cinder = await factory.series("cinder spires", alice)
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
        ),  # fmt: skip
        "extra": await factory.book(
            "A Dresden Extra", alice, author_ids=[butcher], series_id=dresden
        ),  # fmt: skip
        "aeronaut": await factory.book(
            "The Aeronaut's Windlass",
            alice,
            author_ids=[butcher],
            series_id=cinder,
            series_number="1",
        ),  # fmt: skip
        "side": await factory.book("Side Jobs", alice, author_ids=[butcher]),
        "brief": await factory.book("Brief Cases", alice, author_ids=[butcher]),
        "cuckoo": await factory.book("The Cuckoo's Calling", alice, author_ids=[galbraith]),
    }
    await factory.story(
        "Restoration of Faith", alice, series_id=dresden, series_number="1.5",
        author_ids=[butcher], book_ids=[books["side"], books["brief"]],
    )  # fmt: skip
    entries = {
        "storm": await factory.entry(alice, books["storm"], finished_on=date(2025, 3, 1)),
        "side": await factory.entry(alice, books["side"], status="want_to_read"),
    }
    await factory.entry(ben, books["fool"], finished_on=date(2025, 4, 2), notes="Ben's note")
    return World(
        alice, ben,
        await signed_in(client_factory(), alice), await signed_in(client_factory(), ben),
        butcher, galbraith, dresden, books, entries,
    )  # fmt: skip


def _row(body: str, book_id: uuid.UUID) -> str:
    not_end = "(?:(?!</li>).)*"
    found = re.search(
        rf'<li class="catalog-row" id="book-{book_id}">{not_end}</li>',  # spec 015 rows
        body,
        re.S,
    )
    assert found, f"no row for {book_id}"
    return found.group(0)


# ------------------------------------------------------------------ US1


@pytest.mark.ac("011/AC-01")
async def test_author_names_link_to_the_author_page(world: World) -> None:
    link = f'<a href="/authors/{world.butcher}">Jim Butcher</a>'
    for path in ("/", "/catalog", "/upcoming", f"/series/{world.dresden}"):
        page = await world.member.get(path)
        assert link in page.text, path
    for path in (
        f"/entries/{world.entries['storm']}",
        f"/catalog/books/{world.books['storm']}/edit",
    ):
        page = (await world.member.get(path)).text
        assert link in page, path
        assert f'href="/catalog/authors/{world.butcher}/edit"' in page, path  # still there


@pytest.mark.ac("011/AC-02")
async def test_author_details(world: World, client: httpx.AsyncClient) -> None:
    page = (await world.member.get(f"/authors/{world.butcher}")).text
    assert "<h1>Jim Butcher</h1>" in page
    assert "Pen name" not in page
    assert f'<a href="/catalog/authors/{world.butcher}/edit">Edit author</a>' in page
    pen = (await world.member.get(f"/authors/{world.galbraith}")).text
    assert "Pen name of J.K. Rowling" in pen
    assert (await world.member.get(f"/authors/{uuid.uuid4()}")).status_code == 404
    signed_out = await client.get(f"/authors/{world.butcher}")
    assert signed_out.status_code == 303 and signed_out.headers["location"] == "/sign-in"


@pytest.mark.ac("011/AC-02")
async def test_pen_name_without_real_name(world: World, factory: Factory) -> None:
    anon = await factory.author("Anonymous", world.alice, is_pen_name=True)
    page = (await world.member.get(f"/authors/{anon}")).text
    assert '<p class="muted">Pen name</p>' in page


@pytest.mark.ac("011/AC-03")
async def test_books_grouped_by_series(world: World) -> None:
    page = (await world.member.get(f"/authors/{world.butcher}")).text
    headings = re.findall(r"<h3[^>]*>(.*?)</h3>", page, re.S)
    assert [re.sub(r"<[^>]+>", "", h).strip() for h in headings] == [
        "cinder spires", "The Dresden Files", "Other books",
    ]  # fmt: skip
    assert f'<a href="/series/{world.dresden}">The Dresden Files</a>' in page
    assert titles(page) == [
        "The Aeronaut's Windlass",
        "Storm Front", "Fool Moon", "Twenty Lives", "A Dresden Extra",
        "Brief Cases", "Side Jobs",
    ]  # fmt: skip
    assert "#18" in _row(page, world.books["twenty"])
    assert "Coming 3 Mar 2027" in _row(page, world.books["twenty"])
    assert "#" not in _row(page, world.books["extra"])  # unnumbered


@pytest.mark.ac("011/AC-04")
async def test_my_status_or_add(world: World) -> None:
    page = (await world.member.get(f"/authors/{world.butcher}")).text
    storm = _row(page, world.books["storm"])
    # Spec 015 AC-08: the status badge is the link to my entry.
    storm_badge = f'<a class="badge status-link" href="/entries/{world.entries["storm"]}">Finished'
    assert storm_badge in storm
    assert 'class="badge status-link"' in _row(page, world.books["side"])
    assert ">Want to read<span" in _row(page, world.books["side"])
    fool = _row(page, world.books["fool"])
    assert f'href="/books/add?book={world.books["fool"]}"' in fool
    assert '<span class="visually-hidden"> “Fool Moon”</span> with details…' in fool
    assert "badge" not in fool and "Not on my list" in fool


@pytest.mark.ac("011/AC-05")
async def test_other_members_entries_leave_no_trace(world: World, factory: Factory) -> None:
    page = (await world.member.get(f"/authors/{world.butcher}")).text
    for leak in ("Ben", "Ben&#39;s note", "2 Apr 2025"):
        assert leak not in page, leak
    with_bens = _row(page, world.books["fool"])
    await factory.execute("DELETE FROM reading_entry WHERE user_id = :u", u=world.ben.id)
    after = (await world.member.get(f"/authors/{world.butcher}")).text
    assert _row(after, world.books["fool"]) == with_bens


@pytest.mark.ac("011/AC-06")
async def test_stories_section(world: World) -> None:
    page = (await world.member.get(f"/authors/{world.butcher}")).text
    assert "<h2>Stories</h2>" in page
    section = page.split("<h2>Stories</h2>", 1)[1]
    assert "#1.5 The Dresden Files — Restoration of Faith" in section
    assert f'<a href="/books/{world.books["brief"]}">Brief Cases</a>' in section
    assert f'<a href="/books/{world.books["side"]}">Side Jobs</a>' in section
    pen = (await world.member.get(f"/authors/{world.galbraith}")).text
    assert "<h2>Stories</h2>" not in pen


@pytest.mark.ac("011/AC-07")
async def test_author_with_no_books(world: World, factory: Factory) -> None:
    lonely = await factory.author("Nobody Yet", world.alice)
    page = (await world.member.get(f"/authors/{lonely}")).text
    assert "No book in the family catalog lists this author." in page
    assert "<h3>" not in page


# ------------------------------------------------------------------ US2


async def _favorite(client: httpx.AsyncClient, author: uuid.UUID, value: str) -> httpx.Response:
    page = await client.get(f"/authors/{author}")
    return await client.post(
        f"/authors/{author}/favorite", data={"csrf_token": csrf(page.text), "favorite": value}
    )


@pytest.mark.ac("011/AC-08")
async def test_add_and_remove_favorite(world: World) -> None:
    before = (await world.member.get(f"/authors/{world.butcher}")).text
    assert (
        '<button type="submit" name="favorite" value="yes">Add to my favorite authors</button>'
        in before
    )
    assert "One of your favorite authors" not in before
    added = await _favorite(world.member, world.butcher, "yes")
    assert added.status_code == 303
    assert added.headers["location"] == f"/authors/{world.butcher}?msg=favorited"
    page = (await world.member.get(added.headers["location"])).text
    assert "Added to your favorite authors." in page
    assert '<span aria-hidden="true">★</span> One of your favorite authors' in page
    assert 'value="no">Remove from my favorite authors</button>' in page
    removed = await _favorite(world.member, world.butcher, "no")
    assert removed.headers["location"] == f"/authors/{world.butcher}?msg=unfavorited"
    page = (await world.member.get(removed.headers["location"])).text
    assert "Removed from your favorite authors." in page
    assert "One of your favorite authors" not in page


@pytest.mark.ac("011/AC-09")
async def test_favorites_are_mine_only(world: World) -> None:
    await _favorite(world.member, world.butcher, "yes")
    assert (await _favorite(world.member, world.butcher, "yes")).status_code == 303  # again
    bens = (await world.other.get(f"/authors/{world.butcher}")).text
    assert "One of your favorite authors" not in bens and 'value="yes">Add to my' in bens
    assert (await _favorite(world.other, world.butcher, "no")).status_code == 303  # not his
    mine = (await world.member.get(f"/authors/{world.butcher}")).text
    assert "One of your favorite authors" in mine  # Ben's remove didn't touch Alice's
    token = csrf(mine)
    unknown = await world.member.post(
        f"/authors/{uuid.uuid4()}/favorite", data={"csrf_token": token, "favorite": "yes"}
    )
    assert unknown.status_code == 404
    bad = await world.member.post(
        f"/authors/{world.butcher}/favorite", data={"csrf_token": token, "favorite": "maybe"}
    )
    assert bad.status_code == 422
    no_csrf = await world.member.post(  # the client's header token replaced by a wrong one
        f"/authors/{world.butcher}/favorite",
        data={"favorite": "no"},
        headers={"X-CSRF-Token": "wrong"},
    )
    assert no_csrf.status_code == 403
    assert (
        "One of your favorite authors" in (await world.member.get(f"/authors/{world.butcher}")).text
    )
