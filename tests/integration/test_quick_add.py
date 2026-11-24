"""Spec 015 User Story 1: a one-click "Want to read" on catalog rows (books-1q7).

Contract: specs/015-rows-quick-add/contracts/ui-rows.md.
"""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in, ui_csrf
from tests.integration.test_flow_fixes import link, text_of


@pytest.fixture(name="alice")
async def alice_fixture(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture(name="member")
async def member_fixture(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture(name="w")
async def world_fixture(factory: Factory, alice: TestUser) -> dict[str, Any]:
    terry = await factory.author("Terry Pratchett", alice)
    disc = await factory.series("Discworld", alice)
    gods = await factory.book("Small Gods", alice, author_ids=[terry], series_id=disc,
                              series_number="13")  # fmt: skip
    mort = await factory.book("Mort", alice, author_ids=[terry], series_id=disc, series_number="4")
    soon = await factory.book("Coming Soon", alice, author_ids=[terry],
                              release_date=date.today() + timedelta(days=60))  # fmt: skip
    tales = await factory.book("Disc Tales", alice, author_ids=[terry])
    story = await factory.story("Troll Bridge", alice, series_id=disc, series_number="4.5",
                                author_ids=[terry], book_ids=[tales])  # fmt: skip
    mort_entry = await factory.entry(alice, mort)
    return {"terry": terry, "disc": disc, "gods": gods, "mort": mort, "soon": soon,
            "tales": tales, "story": story, "mort_entry": mort_entry}  # fmt: skip


async def quick_add(client: httpx.AsyncClient, book: uuid.UUID, back: str) -> httpx.Response:
    return await client.post(
        f"/books/{book}/want-to-read", data={"back": back, "csrf_token": await ui_csrf(client)}
    )


def plain(page: str) -> str:
    """Page text with tags removed (not replaced by spaces), whitespace collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", page)).split())


def quick_button(page: str, book: uuid.UUID) -> re.Match[str] | None:
    return re.search(
        rf'<form method="post" action="/books/{book}/want-to-read"[^>]*>.*?</form>', page, re.S
    )


@pytest.mark.ac("015/AC-01")
@pytest.mark.ac("015/AC-04")
async def test_rows_offer_both_actions(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    pages = {
        "/catalog": [w["gods"], w["soon"], w["tales"]],
        f"/authors/{w['terry']}": [w["gods"], w["soon"], w["tales"]],
        "/upcoming": [w["soon"]],
        f"/series/{w['disc']}": [w["gods"], w["tales"]],  # tales via the Troll Bridge story row
    }
    for path, books in pages.items():
        page = (await member.get(path)).text
        for book in books:
            form = quick_button(page, book)
            assert form, (path, book)
            assert re.search(r'name="back" value="[^"]+"', form.group(0)), path
            assert re.search(r'<button type="submit"[^>]*>.*?Want to read', form.group(0), re.S)
        assert not quick_button(page, w["mort"]), path  # on my list: no add
        assert "Add with details…" in text_of(page) or "with details" in text_of(page), path
    series = (await member.get(f"/series/{w['disc']}")).text
    details = re.findall(r'href="(/books/add\?book=[^"]+)"', series)
    assert f"/books/add?book={w['gods']}&amp;from_series={w['disc']}".replace("&amp;", "&") in [
        d.replace("&amp;", "&") for d in details
    ]


@pytest.mark.ac("015/AC-02")
async def test_quick_add_keeps_the_page(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    back = "/catalog?q=terry&sort=-title&page=1"
    page = (await member.get(back)).text
    form = quick_button(page, w["gods"])
    assert form and 'value="/catalog?q=terry&amp;sort=-title&amp;page=1"' in form.group(0)
    response = await quick_add(member, w["gods"], back)
    assert response.status_code == 303
    assert response.headers["location"] == f"{back}&wanted={w['gods']}#book-{w['gods']}"
    row = await factory.row(
        "SELECT status, finished_on, notes, pre_ordered FROM reading_entry "
        "WHERE user_id = :u AND book_id = :b", u=alice.id, b=w["gods"],
    )  # fmt: skip
    assert row == {"status": "want_to_read", "finished_on": None, "notes": None,
                   "pre_ordered": False}  # fmt: skip
    shown = (await member.get(response.headers["location"].split("#")[0])).text
    entry = await factory.scalar("SELECT id FROM reading_entry WHERE book_id = :b", b=w["gods"])
    assert "Added “Small Gods” to your list as Want to read." in plain(shown)
    assert link(shown, "Small Gods") == f"/entries/{entry}"
    assert f'id="book-{w["gods"]}"' in shown


@pytest.mark.ac("015/AC-02")
@pytest.mark.parametrize("page", ["author", "upcoming", "series"])
async def test_quick_add_from_each_page(
    member: httpx.AsyncClient, w: dict[str, Any], page: str
) -> None:
    back, book = {
        "author": (f"/authors/{w['terry']}", w["gods"]),
        "upcoming": ("/upcoming", w["soon"]),
        "series": (f"/series/{w['disc']}", w["tales"]),
    }[page]
    response = await quick_add(member, book, back)
    assert response.headers["location"] == f"{back}?wanted={book}#book-{book}"
    shown = text_of((await member.get(response.headers["location"].split("#")[0])).text)
    assert "to your list as Want to read." in shown


@pytest.mark.ac("015/AC-03")
async def test_already_on_my_list(
    member: httpx.AsyncClient, factory: Factory, w: dict[str, Any]
) -> None:
    before = await factory.scalar("SELECT count(*) FROM reading_entry")
    response = await quick_add(member, w["mort"], "/catalog")
    assert response.headers["location"] == f"/catalog?already={w['mort']}#book-{w['mort']}"
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == before
    shown = plain((await member.get(response.headers["location"].split("#")[0])).text)
    assert "“Mort” is already on your list." in shown


@pytest.mark.ac("015/AC-05")
@pytest.mark.parametrize(
    "back",
    [
        "https://evil.example/", "//evil.example/catalog", "/\\evil", "javascript:alert(1)",
        "/entries/abc", "/catalog#x", "/catalog?q=a b", "/authors/not-a-uuid", "",
        "/catalog?q=%0d%0aSet-Cookie:x", "/series/{0}/../../admin",
    ],
)  # fmt: skip
async def test_unsafe_return_addresses_go_to_the_catalog(
    member: httpx.AsyncClient, w: dict[str, Any], back: str
) -> None:
    response = await quick_add(member, w["gods"], back.format(w["disc"]))
    assert response.status_code == 303
    assert response.headers["location"] == f"/catalog?wanted={w['gods']}#book-{w['gods']}"


@pytest.mark.ac("015/AC-05")
async def test_earlier_notices_are_replaced(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    back = f"/catalog?q=t&wanted={w['mort']}&already={w['mort']}&page=2"
    response = await quick_add(member, w["gods"], back)
    assert (
        response.headers["location"] == f"/catalog?q=t&page=2&wanted={w['gods']}#book-{w['gods']}"
    )


@pytest.mark.ac("015/AC-05")
async def test_unknown_book_and_csrf(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    assert (await quick_add(member, uuid.uuid4(), "/catalog")).status_code == 404
    forged = await member.post(
        f"/books/{w['gods']}/want-to-read", data={"back": "/catalog", "csrf_token": "wrong"},
        headers={"X-CSRF-Token": "wrong"},
    )  # fmt: skip
    assert forged.status_code == 403


async def test_another_members_entry_doesnt_block_mine(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    bob = await factory.user("bob")
    await factory.entry(bob, w["gods"])
    page = (await member.get("/catalog")).text
    assert quick_button(page, w["gods"])  # Bob's entry isn't mine
    response = await quick_add(member, w["gods"], "/catalog")
    assert "wanted=" in response.headers["location"]
    assert (
        await factory.scalar("SELECT count(*) FROM reading_entry WHERE book_id = :b", b=w["gods"])
        == 2
    )


async def test_notice_ignores_books_not_on_my_list(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    page = text_of((await member.get(f"/catalog?wanted={w['gods']}&already=nope")).text)
    assert "to your list as Want to read" not in page and "is already on your list" not in page


# --------------------------------------------------------------------------- PR #35 review


@pytest.mark.ac("015/AC-09")
async def test_story_badge_links_to_the_entry_it_shows(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    other = await factory.book("Zebra Anthology", alice, author_ids=[w["terry"]])
    await factory.execute(
        "INSERT INTO book_story (book_id, story_id) VALUES (:b, :s)", b=other, s=w["story"]
    )
    await factory.entry(alice, w["tales"], status="want_to_read")
    finished = await factory.entry(alice, other, status="finished")
    page = (await member.get(f"/series/{w['disc']}")).text
    story = re.search(r'<li class="series-story"[^>]*>.*?</li>', page, re.S)
    assert story
    badge = re.search(
        r'<a class="badge status-link" href="/entries/([^"]+)">Finished', story.group(0)
    )
    assert badge and badge.group(1) == str(finished)


@pytest.mark.ac("015/AC-02")
async def test_old_notices_are_not_carried_back(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    s = w["disc"]
    page = (await member.get(f"/series/{s}?added={w['mort_entry']}&stories=2&msg=x")).text
    assert f'name="back" value="/series/{s}"' in page
    response = await quick_add(member, w["gods"], f"/series/{s}?added=1&stories=2&msg=x")
    assert response.headers["location"] == f"/series/{s}?wanted={w['gods']}#book-{w['gods']}"


@pytest.mark.ac("015/AC-02")
@pytest.mark.ac("015/AC-04")
async def test_story_quick_add_returns_to_the_story_row(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    page = (await member.get(f"/series/{w['disc']}")).text
    assert f'<li class="series-story" id="story-{w["story"]}">' in page
    form = quick_button(page, w["tales"])
    assert form and f'name="anchor" value="story-{w["story"]}"' in form.group(0)
    response = await member.post(f"/books/{w['tales']}/want-to-read", data={
        "back": f"/series/{w['disc']}", "anchor": f"story-{w['story']}",
        "csrf_token": await ui_csrf(member),
    })  # fmt: skip
    assert response.headers["location"].endswith(f"#story-{w['story']}")
    bad = await member.post(f"/books/{w['gods']}/want-to-read", data={
        "back": "/catalog", "anchor": "x\"><script>", "csrf_token": await ui_csrf(member),
    })  # fmt: skip
    assert bad.headers["location"].endswith(f"#book-{w['gods']}")


async def test_uppercase_ids_in_the_return_address(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    back = f"/series/{str(w['disc']).upper()}"
    response = await quick_add(member, w["gods"], back)
    assert response.headers["location"].startswith(f"{back}?wanted=")


async def test_htmx_catalog_clears_the_notice(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    page = (await member.get(f"/catalog?wanted={w['mort']}")).text
    assert '<div id="quick-notice-area">' in page
    swapped = await member.get("/catalog", params={"q": "mort"}, headers={"HX-Request": "true"})
    assert '<div hx-swap-oob="innerHTML:#quick-notice-area"></div>' in swapped.text
