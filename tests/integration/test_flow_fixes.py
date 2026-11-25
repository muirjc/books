"""Spec 014: flow fixes from the 2026-11-23 UI review (books-gjh).

Contract: specs/014-flow-fixes/contracts/ui-flow-fixes.md.
"""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import httpx
import pytest

from book_tracker.services import readings as readings_service
from tests.conftest import Factory, TestUser, signed_in
from tests.fakes import FakeBookSource
from tests.integration.import_helpers import confirm_via_page, stock
from tests.integration.import_helpers import member as import_member


@pytest.fixture(name="alice")
async def alice_fixture(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture(name="bob")
async def bob_fixture(factory: Factory) -> TestUser:
    return await factory.user("bob", display_name="Bob")


@pytest.fixture(name="member")
async def member_fixture(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture(name="other")
async def other_fixture(
    bob: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), bob)


@pytest.fixture(name="w")
async def world_fixture(factory: Factory, alice: TestUser, bob: TestUser) -> dict[str, Any]:
    jim = await factory.author("Jim Butcher", alice)
    dresden = await factory.series("The Dresden Files", alice)
    side = await factory.book("Side Jobs", alice, author_ids=[jim], series_id=dresden)
    fool = await factory.book("Fool Moon", alice, author_ids=[jim], series_id=dresden,
                              series_number="2")  # fmt: skip
    return {
        "jim": jim, "dresden": dresden, "side": side, "fool": fool,
        "entry": await factory.entry(alice, side),
        "fool_entry": await factory.entry(alice, fool),
        "bob_entry": await factory.entry(bob, fool),
    }  # fmt: skip


def text_of(page: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def link(page: str, label: str) -> str | None:
    """The href of the first link whose text is ``label``."""
    for href, inner in re.findall(r'<a [^>]*href="([^"]*)"[^>]*>(.*?)</a>', page, re.S):
        if text_of(inner) == label:
            return html.unescape(href)
    return None


def current_tab(page: str) -> str | None:
    nav = re.search(r'<nav aria-label="Main">.*?</nav>', page, re.S)
    assert nav
    found = re.search(r'<a [^>]*aria-current="page"[^>]*>(.*?)</a>', nav.group(0))
    return text_of(found.group(1)) if found else None


def story_form(w: dict[str, Any], title: str, number: str, **extra: str) -> dict[str, str]:
    return {
        "title": title, "series_number": number, "author_name_0": "Jim Butcher",
        "author_id_0": str(w["jim"]), "series_name": "The Dresden Files",
        "series_id": str(w["dresden"]), **extra,
    }  # fmt: skip


# --------------------------------------------------------------------------- foundational


async def test_entry_for_book_is_mine_only(
    app: Any, alice: TestUser, bob: TestUser, w: dict[str, Any]
) -> None:
    async with app.state.db.sessionmaker() as db:
        mine = await readings_service.entry_for_book(db, alice.id, w["side"])
        assert mine is not None and mine.id == w["entry"]
        assert await readings_service.entry_for_book(db, bob.id, w["side"]) is None
        bobs = await readings_service.entry_for_book(db, bob.id, w["fool"])
        assert bobs is not None and bobs.id == w["bob_entry"]


# --------------------------------------------------------------------------- US1


@pytest.mark.ac("014/AC-01")
async def test_entry_page_always_offers_add_a_story(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    page = (await member.get(f"/entries/{w['entry']}")).text
    assert "Stories in this book" in page
    assert (
        "No stories recorded. If this book is an anthology or collection, add its stories."
        in text_of(page)
    )
    add = f"/catalog/books/{w['side']}/stories/add?from=entry:{w['entry']}"
    assert link(page, "Add a story") == add
    await factory.story("Restoration of Faith", alice, series_id=w["dresden"], series_number="1.5",
                        author_ids=[w["jim"]], book_ids=[w["side"]])  # fmt: skip
    page = (await member.get(f"/entries/{w['entry']}")).text
    assert "Restoration of Faith" in page
    assert link(page, "Add a story") == add
    assert link(page, "Edit the stories") == f"/catalog/books/{w['side']}/edit#stories"


@pytest.mark.ac("014/AC-02")
async def test_stories_not_added_points_at_add_a_story(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    page = (await member.get(f"/entries/{w['entry']}?msg=stories_not_added")).text
    assert "The stories you typed were not added. Add them with Add a story below." in text_of(page)
    assert link(page, "Add a story")


@pytest.mark.ac("014/AC-03")
async def test_add_and_add_another_story(
    member: httpx.AsyncClient, factory: Factory, w: dict[str, Any]
) -> None:
    url = f"/catalog/books/{w['side']}/stories/add"
    response = await member.post(
        url, data=story_form(w, "Restoration of Faith", "1.5", then="another")
    )
    assert response.status_code == 303, response.text
    story = await factory.scalar("SELECT id FROM story WHERE title = 'Restoration of Faith'")
    assert response.headers["location"] == f"{url}?added={story}"
    page = (await member.get(response.headers["location"])).text
    assert "Added “#1.5 Restoration of Faith”." in text_of(page)
    assert re.search(r'<input[^>]*id="title"[^>]*autofocus', page)
    assert re.search(r'name="series_name"[^>]*value="The Dresden Files"', page)
    assert re.search(r'name="author_name_0"[^>]*value="Jim Butcher"', page)
    assert ">Add and add another<" in page
    # Errors behave as today: nothing saved, the form comes back.
    bad = await member.post(url, data=story_form(w, "", "2.5", then="another"))
    assert bad.status_code == 422
    # An id that isn't a story in this book says nothing.
    other = (await member.get(f"{url}?added={uuid.uuid4()}")).text
    assert "Added “" not in other


@pytest.mark.ac("014/AC-04")
async def test_add_a_story_returns_to_the_entry_page(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    url = f"/catalog/books/{w['side']}/stories/add"
    origin = f"entry:{w['entry']}"
    page = (await member.get(url, params={"from": origin})).text
    assert link(page, "Cancel") == f"/entries/{w['entry']}"
    assert re.search(rf'name="from" value="{origin}"', page)
    saved = await member.post(url, data=story_form(w, "A", "1.5", **{"from": origin}))
    assert saved.headers["location"] == f"/entries/{w['entry']}?msg=story_added"
    shown = (await member.get(saved.headers["location"])).text
    assert "Story added." in text_of(shown)
    another = await member.post(
        url, data=story_form(w, "B", "2.5", then="another", **{"from": origin})
    )
    assert another.headers["location"].endswith(f"&from={origin}")
    page = (await member.get(another.headers["location"])).text
    assert link(page, "Cancel") == f"/entries/{w['entry']}"


@pytest.mark.ac("014/AC-04")
@pytest.mark.parametrize("which", ["bob", "other_book", "malformed", "missing"])
async def test_a_foreign_from_is_ignored(
    member: httpx.AsyncClient, w: dict[str, Any], which: str
) -> None:
    origin = {
        "bob": f"entry:{w['bob_entry']}", "other_book": f"entry:{w['fool_entry']}",
        "malformed": "https://evil.example/", "missing": f"entry:{uuid.uuid4()}",
    }[which]  # fmt: skip
    url = f"/catalog/books/{w['side']}/stories/add"
    page = (await member.get(url, params={"from": origin})).text
    assert link(page, "Cancel") == f"/catalog/books/{w['side']}/edit#stories"
    assert 'name="from"' not in page
    saved = await member.post(url, data=story_form(w, "A", "1.5", **{"from": origin}))
    assert saved.headers["location"].startswith(f"/catalog/books/{w['side']}/edit?msg=story_added")


@pytest.mark.ac("014/AC-05")
async def test_edit_book_jump_link_and_hint(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    page = (await member.get(f"/catalog/books/{w['side']}/edit")).text
    assert link(page, "Stories in this book") == "#stories"
    assert "Jump to:" in text_of(page)
    assert "For an anthology or collection: each story gets its place in its series." in text_of(
        page
    )


# --------------------------------------------------------------------------- US2


@pytest.mark.ac("014/AC-06")
async def test_edit_book_back_link(
    member: httpx.AsyncClient, other: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    mine = (await member.get(f"/catalog/books/{w['side']}/edit")).text
    assert link(mine, "Back to “Side Jobs”") == f"/entries/{w['entry']}"
    bobs = (await other.get(f"/catalog/books/{w['side']}/edit")).text
    assert link(bobs, "Back to the catalog") == "/catalog"
    assert f"/entries/{w['entry']}" not in bobs  # never another member's entry


@pytest.mark.ac("014/AC-07")
async def test_summary_back_link(
    member: httpx.AsyncClient, other: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    mine = (await member.get(f"/catalog/books/{w['side']}/summary")).text
    assert link(mine, "Back to “Side Jobs”") == f"/entries/{w['entry']}"
    bobs = (await other.get(f"/catalog/books/{w['side']}/summary")).text
    # PR #37 review: not on my list, the summary page goes back to the book page (spec 016).
    assert link(bobs, "Back to “Side Jobs”") == f"/books/{w['side']}"


@pytest.mark.ac("014/AC-08")
async def test_edit_series_links_to_the_series(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    page = (await member.get(f"/catalog/series/{w['dresden']}/edit")).text
    assert link(page, "View the series") == f"/series/{w['dresden']}"


@pytest.mark.ac("014/AC-09")
async def test_edit_story_back_link(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    story = await factory.story("Tale", alice, series_id=w["dresden"], series_number="1.5",
                                author_ids=[w["jim"]], book_ids=[w["side"], w["fool"]])  # fmt: skip
    edit_book = (await member.get(f"/catalog/books/{w['fool']}/edit")).text
    from_link = f"/catalog/stories/{story}/edit?from=book:{w['fool']}"
    assert from_link in html.unescape(edit_book)
    page = (await member.get(from_link)).text
    assert link(page, "Back to “Fool Moon”") == f"/catalog/books/{w['fool']}/edit#stories"
    plain = (await member.get(f"/catalog/stories/{story}/edit")).text
    assert link(plain, "Back to “Fool Moon”") or link(plain, "Back to “Side Jobs”")
    odd = (await member.get(f"/catalog/stories/{story}/edit?from=book:{uuid.uuid4()}")).text
    assert link(odd, "Back to “Fool Moon”") or link(odd, "Back to “Side Jobs”")


@pytest.mark.ac("014/AC-10")
async def test_navigation_marks_the_related_tab(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    story = await factory.story("Tale", alice, series_id=w["dresden"], series_number="1.5",
                                author_ids=[w["jim"]], book_ids=[w["side"]])  # fmt: skip
    expected = {
        "/": "My books",
        f"/entries/{w['entry']}": "My books",
        "/authors/favorites": "My books",
        "/books/add": "Add a book",
        "/catalog": "Catalog",
        f"/catalog/books/{w['side']}/edit": "Catalog",
        f"/catalog/books/{w['side']}/summary": "Catalog",
        f"/catalog/books/{w['side']}/stories/add": "Catalog",
        f"/catalog/stories/{story}/edit": "Catalog",
        f"/catalog/series/{w['dresden']}/edit": "Catalog",
        f"/catalog/authors/{w['jim']}/edit": "Catalog",
        "/catalog/authors/unused": "Catalog",
        f"/series/{w['dresden']}": "Catalog",
        f"/authors/{w['jim']}": "Catalog",
        "/upcoming": "Upcoming",
        "/import": "Import",
    }
    for path, tab in expected.items():
        page = await member.get(path)
        assert page.status_code == 200, path
        assert current_tab(page.text) == tab, path
    nav = re.search(r'<nav aria-label="Main">.*?</nav>', page.text, re.S)
    assert nav and link(nav.group(0), "Import") == "/import"
    assert "Import from Open Library" not in nav.group(0)


@pytest.mark.ac("014/AC-11")
async def test_books_added_links_to_the_catalog(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await import_member(factory, client_factory, "kim")
    done = await confirm_via_page(client, ["OL1W"])
    assert link(done.text, "Go to the catalog") == "/catalog"


# --------------------------------------------------------------------------- US3


@pytest.mark.ac("014/AC-12")
async def test_add_next_row(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    await factory.story("Tale", alice, series_id=w["dresden"], series_number="3.5",
                        author_ids=[w["jim"]], book_ids=[w["side"]])  # fmt: skip
    page = (await member.get(f"/series/{w['dresden']}")).text
    s = w["dresden"]
    assert link(page, "Add #4") == f"/books/add?series={s}&number=4&from_series={s}"
    assert "#4 Not in the family catalog yet" in text_of(page)
    # Nothing numbered: no row.
    empty = await factory.series("Loose Ends", alice)
    await factory.book("Unnumbered", alice, series_id=empty)
    page = (await member.get(f"/series/{empty}")).text
    assert not re.search(r">Add #\d", page)
    # At 999: no row.
    top = await factory.series("Long Runner", alice)
    await factory.book("Last", alice, series_id=top, series_number="999")
    assert "Add #1000" not in (await member.get(f"/series/{top}")).text


@pytest.mark.ac("014/AC-13")
async def test_add_a_collection_from_a_series(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    s = w["dresden"]
    page = (await member.get(f"/series/{s}")).text
    href = link(page, "Add a collection with stories in this series")
    assert href == f"/books/add?series={s}&anthology=yes&from_series={s}"
    form = (await member.get(href)).text
    assert re.search(r'<input[^>]*name="anthology"[^>]*checked', form)
    assert re.search(r'name="series_name"[^>]*value="The Dresden Files"', form)
    assert re.search(r'name="series_number"[^>]*value=""', form)
    assert re.search(rf'name="from_series" value="{s}"', form)
    assert len(re.findall(r'name="story_title_\d+"', form)) == 1


@pytest.mark.ac("014/AC-14")
async def test_add_a_book_by_this_author(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    page = (await member.get(f"/authors/{w['jim']}")).text
    assert link(page, "Add a book by this author") == f"/books/add?author={w['jim']}"
    form = (await member.get(f"/books/add?author={w['jim']}")).text
    assert re.search(r'name="author_name_0"[^>]*value="Jim Butcher"', form)
    assert re.search(rf'name="author_id_0" value="{w["jim"]}"', form)
    for odd in (str(uuid.uuid4()), "nope"):
        plain = (await member.get(f"/books/add?author={odd}")).text
        assert re.search(r'name="author_name_0"[^>]*value=""', plain)


# --------------------------------------------------------------------------- US5


@pytest.mark.ac("014/AC-18")
async def test_favorites_link_beside_the_author_filter(member: httpx.AsyncClient) -> None:
    page = (await member.get("/")).text
    extra = re.search(r'<div id="filter-extra".*?</form>', page, re.S)
    assert extra
    block = extra.group(0)
    # books-349: after Apply, on its own line, so the Author dropdown lines up with the rest.
    series, apply, favorites = (
        block.find('id="series_id"'), block.find('<button type="submit">Apply</button>'),
        block.find('<p class="filter-link"><a href="/authors/favorites">'),
    )  # fmt: skip
    assert -1 < series < apply < favorites


@pytest.mark.ac("014/AC-19")
async def test_entry_page_jump_links(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    page = (await member.get(f"/entries/{w['entry']}")).text
    jump = re.search(r'<nav [^>]*aria-label="On this page".*?</nav>', page, re.S)
    assert jump
    links = re.findall(r'href="(#[^"]+)"', jump.group(0))
    assert links == ["#book-details-heading", "#my-reading-heading", "#stories-heading"]


# --------------------------------------------------------------------------- PR #34 review


@pytest.mark.ac("014/AC-03")
async def test_add_another_survives_a_number_conflict(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    taken = await factory.story("Taken", alice, series_id=w["dresden"], series_number="3",
                                author_ids=[w["jim"]], book_ids=[w["fool"]])  # fmt: skip
    url = f"/catalog/books/{w['side']}/stories/add"
    origin = f"entry:{w['entry']}"
    page = await member.post(
        url, data=story_form(w, "Taken", "3", then="another", **{"from": origin})
    )
    assert page.status_code == 409
    assert re.search(r'<input type="hidden" name="then" value="another">', page.text)
    used = await member.post(url, data=story_form(
        w, "Taken", "3", then="another", use_story=str(taken), **{"from": origin}
    ))  # fmt: skip
    assert used.headers["location"] == f"{url}?added={taken}&from={origin}"
    # "Add story" (then=list) after the hidden "another" still returns as a plain save.
    pairs = [*story_form(w, "New", "4", **{"from": origin}).items(), ("then", "another"),
             ("then", "list")]  # fmt: skip
    form_type = {"Content-Type": "application/x-www-form-urlencoded"}
    plain = await member.post(url, content=urlencode(pairs), headers=form_type)
    assert plain.headers["location"] == f"/entries/{w['entry']}?msg=story_added"


@pytest.mark.ac("014/AC-03")
async def test_add_another_with_a_story_already_in_the_book(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    story = await factory.story("Held", alice, series_id=w["dresden"], series_number="3",
                                author_ids=[w["jim"]], book_ids=[w["side"]])  # fmt: skip
    url = f"/catalog/books/{w['side']}/stories/add"
    again = await member.post(
        url, data=story_form(w, "Held", "3", then="another", story_id=str(story))
    )
    assert again.headers["location"] == f"{url}?added={story}&already=1"
    page = text_of((await member.get(again.headers["location"])).text)
    assert "That story is already in this book." in page and "Added “" not in page


@pytest.mark.ac("014/AC-09")
async def test_edit_story_keeps_where_it_came_from(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    story = await factory.story("Tale", alice, series_id=w["dresden"], series_number="1.5",
                                author_ids=[w["jim"]], book_ids=[w["side"], w["fool"]])  # fmt: skip
    url = f"/catalog/stories/{story}/edit"
    page = (await member.get(url, params={"from": f"book:{w['fool']}"})).text
    assert re.search(rf'<input type="hidden" name="from" value="book:{w["fool"]}">', page)
    form = story_form(w, "Tale", "1.5", **{"from": f"book:{w['fool']}"})
    saved = await member.post(url, data=form)
    assert saved.headers["location"] == f"{url}?msg=saved&from=book:{w['fool']}"
    after = (await member.get(saved.headers["location"])).text
    assert link(after, "Back to “Fool Moon”") == f"/catalog/books/{w['fool']}/edit#stories"
    bad = await member.post(url, data={**form, "title": ""})
    assert bad.status_code == 422
    assert link(bad.text, "Back to “Fool Moon”") == f"/catalog/books/{w['fool']}/edit#stories"


async def test_added_notice_is_read_with_the_title(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    url = f"/catalog/books/{w['side']}/stories/add"
    response = await member.post(url, data=story_form(w, "A", "1.5", then="another"))
    page = (await member.get(response.headers["location"])).text
    title = re.search(r'<input id="title"[^>]*>', page)
    assert title and re.search(r'aria-describedby="[^"]*added-notice', title.group(0))


@pytest.mark.ac("014/AC-10")
async def test_remove_confirmation_and_change_password_mark_their_tab(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    remove = await member.post(f"/entries/{w['entry']}/remove", data={})
    assert current_tab(remove.text) == "My books"
    password = (await member.get("/account/password")).text
    assert re.search(r'<a [^>]*href="/account/password"[^>]*aria-current="page"', password)


async def test_entry_errors_keep_the_source_reference(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    """PR #34 review (pre-existing): the "Imported from Open Library" note stays."""
    await factory.execute(
        "INSERT INTO book_source_ref (id, book_id, source, source_work_id, imported_by) "
        "VALUES (gen_random_uuid(), :b, 'open_library', 'OL9W', :u)",
        b=w["side"],
        u=alice.id,
    )
    page = (await member.get(f"/entries/{w['entry']}")).text
    assert "OL9W" in page
    bad = await member.post(
        f"/entries/{w['entry']}", data={"status": "finished", "times_read": "500"}
    )
    assert bad.status_code == 422 and "OL9W" in bad.text
