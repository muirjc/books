"""Spec 019: stories without a series — saving them from every form, showing them in their
books in the agreed order, and keeping them off series pages."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from book_tracker.persistence import catalog
from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def member(
    client_factory: Callable[[], httpx.AsyncClient], alice: TestUser
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


def words(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


@pytest.fixture
async def shelf(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    """A collection holding Apple #3 and Zed #1, then two stories without a series added
    "Second" first; a second book holding "First" too."""
    jackson = await factory.author("Shirley Jackson", alice)
    zed, apple = (
        await factory.series("Zed Tales", alice),
        await factory.series("Apple Tales", alice),
    )
    book = await factory.book("Mixed Collection", alice, author_ids=[jackson])
    other = await factory.book("Another Anthology", alice, author_ids=[jackson])
    ids: dict[str, uuid.UUID] = {"book": book, "other": other, "zed": zed, "apple": apple,
                                 "jackson": jackson}  # fmt: skip
    for key, title, series, number, books in (
        ("z1", "Zed One", zed, "1", [book]),
        ("a3", "Apple Three", apple, "3", [book]),
        ("second", "Second", None, None, [book]),
        ("first", "First", None, None, [other, book]),
    ):
        ids[key] = await factory.story(title, alice, series_id=series, series_number=number,
                                       author_ids=[jackson], book_ids=books)  # fmt: skip
    return ids


# --------------------------------------------------------------------------- repositories


@pytest.mark.ac("019/AC-09")
async def test_book_stories_order(app: Any, shelf: dict[str, uuid.UUID]) -> None:
    async with app.state.db.sessionmaker() as db:
        mixed = [s.title for s in await catalog.book_stories(db, shelf["book"])]
        other = [s.title for s in await catalog.book_stories(db, shelf["other"])]
        no_series = await catalog.get_story(db, shelf["second"])
    assert mixed == ["Apple Three", "Zed One", "Second", "First"]
    assert other == ["First"]
    assert no_series is not None and no_series.series is None and no_series.series_number is None


@pytest.mark.ac("019/AC-09")
async def test_a_later_link_goes_last(
    app: Any, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    async with app.state.db.sessionmaker() as db:
        assert await catalog.link_story(db, shelf["other"], shelf["second"])
        await db.commit()
        other = [s.title for s in await catalog.book_stories(db, shelf["other"])]
    assert other == ["First", "Second"]


@pytest.mark.ac("019/AC-11")
async def test_series_stories_leave_out_stories_without_a_series(
    app: Any, shelf: dict[str, uuid.UUID]
) -> None:
    async with app.state.db.sessionmaker() as db:
        zed = [s.title for s in await catalog.series_stories(db, shelf["zed"])]
    assert zed == ["Zed One"]


@pytest.mark.ac("019/AC-01")
async def test_create_story_without_a_series(
    app: Any, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    async with app.state.db.sessionmaker() as db:
        story_id = await catalog.create_story(
            db, title="The Lottery", author_ids=[shelf["jackson"]], series_id=None,
            series_number=None, actor_id=alice.id,
        )  # fmt: skip
        await catalog.link_story(db, shelf["book"], story_id)
        await db.commit()
        titles = [s.title for s in await catalog.book_stories(db, shelf["book"])]
    assert titles[-1] == "The Lottery"


# --------------------------------------------------------------------------- US1 the forms


def add_book(**fields: str) -> dict[str, str]:
    data = {"title": "Best Short Stories", "author_name_0": "Various", "status": "want_to_read",
            "anthology": "yes"}  # fmt: skip
    data.update(fields)
    return data


async def stories_in(factory: Factory, title: str) -> list[tuple[str, str | None, str | None]]:
    """(title, series name, number) of a book's stories, in book order (AC-09)."""
    rows = await factory.scalar(
        "SELECT string_agg(s.title || '|' || coalesce(se.name, '-') || '|' || "
        "  coalesce(s.series_number::text, '-'), ';' ORDER BY s.series_id IS NULL, "
        "  lower(se.name), s.series_number, bs.position) "
        "FROM book b JOIN book_story bs ON bs.book_id = b.id JOIN story s ON s.id = bs.story_id "
        "LEFT JOIN series se ON se.id = s.series_id WHERE b.title = :t", t=title,
    )  # fmt: skip
    out: list[tuple[str, str | None, str | None]] = []
    for item in str(rows).split(";") if rows else []:
        t, series, number = item.split("|")
        out.append((t, None if series == "-" else series, None if number == "-" else number))
    return out


def error_for(page: str, field: str) -> str:
    match = re.search(rf'<p class="field-error" id="{field}-error"[^>]*>(.*?)</p>', page, re.S)
    return words(match.group(1)) if match else ""


@pytest.mark.ac("019/AC-01")
async def test_anthology_of_stories_without_a_series(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    ids = {
        name: await factory.author(name, alice)
        for name in ("Various", "Shirley Jackson", "Kurt Vonnegut", "Ursula K. Le Guin")
    }
    page = (await member.get("/books/add")).text
    assert "Leave the number and series blank for a story that isn't part of a series." in words(
        page
    )
    saved = await member.post("/books/add", data=add_book(
        author_id_0=str(ids["Various"]),
        story_title_0="The Lottery", story_author_name_0="Shirley Jackson",
        story_title_1="Harrison Bergeron", story_author_name_1="Kurt Vonnegut",
        story_title_2="The Ones Who Walk Away", story_author_name_2="Ursula K. Le Guin",
    ))  # fmt: skip
    assert saved.status_code == 303, error_for(saved.text, "story_title_0") or saved.text[-3000:]
    assert await stories_in(factory, "Best Short Stories") == [
        ("The Lottery", None, None),
        ("Harrison Bergeron", None, None),
        ("The Ones Who Walk Away", None, None),
    ]


@pytest.mark.ac("019/AC-01")
@pytest.mark.ac("019/AC-02")
async def test_book_with_a_series_mixes_both(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    jim = await factory.author("Jim Butcher", alice)
    dresden = await factory.series("The Dresden Files", alice)
    saved = await member.post("/books/add", data={
        "title": "Side Jobs", "author_name_0": "Jim Butcher", "author_id_0": str(jim),
        "series_name": "The Dresden Files", "series_id": str(dresden), "status": "finished",
        "anthology": "yes", "story_title_0": "Unrelated Tale",
        "story_title_1": "Restoration of Faith", "story_number_1": "1.5",
    })  # fmt: skip
    assert saved.status_code == 303, saved.text[-2000:]
    assert await stories_in(factory, "Side Jobs") == [
        ("Restoration of Faith", "The Dresden Files", "1.50"),
        ("Unrelated Tale", None, None),
    ]


@pytest.mark.ac("019/AC-03")
@pytest.mark.ac("019/AC-07")
async def test_row_needs_both_or_neither(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    other = await factory.series("Other Series", alice)
    refused = await member.post("/books/add", data=add_book(
        story_title_0="Half", story_series_name_0="Other Series", story_series_id_0=str(other),
        story_title_1="Numbered", story_number_1="4",
    ))  # fmt: skip
    assert refused.status_code == 422
    assert error_for(refused.text, "story_number_0") == (
        "Story 1: Enter a number, or clear the series for a story that isn't part of a series"
    )
    assert error_for(refused.text, "story_series_name_1") == (
        "Story 2: Choose a series for this story, or clear the number for a story that isn't "
        "part of a series"
    )
    assert 'value="Half"' in refused.text and 'value="Numbered"' in refused.text
    assert await factory.scalar("SELECT count(*) FROM book") == 0


@pytest.mark.ac("019/AC-04")
async def test_add_a_story_without_a_series(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    jim = await factory.author("Jim Butcher", alice)
    dresden = await factory.series("The Dresden Files", alice)
    book = await factory.book("Side Jobs", alice, author_ids=[jim], series_id=dresden)
    form = (await member.get(f"/catalog/books/{book}/stories/add")).text
    assert re.search(r'name="series_name"[^>]*value="The Dresden Files"', form)
    base = {"title": "A Loose Tale", "author_name_0": "Jim Butcher", "author_id_0": str(jim)}
    half = await member.post(f"/catalog/books/{book}/stories/add", data={
        **base, "series_name": "The Dresden Files", "series_id": str(dresden),
    })  # fmt: skip
    assert half.status_code == 422
    assert error_for(half.text, "series_number") == (
        "Enter a number, or clear the series for a story that isn't part of a series"
    )
    number_only = await member.post(
        f"/catalog/books/{book}/stories/add", data={**base, "series_number": "3"}
    )
    assert number_only.status_code == 422
    assert error_for(number_only.text, "series_name") == (
        "Choose a series, or clear the number for a story that isn't part of a series"
    )
    saved = await member.post(f"/catalog/books/{book}/stories/add", data=base)
    assert saved.status_code == 303, saved.text[-2000:]
    assert await stories_in(factory, "Side Jobs") == [("A Loose Tale", None, None)]


@pytest.mark.ac("019/AC-05")
async def test_edit_story_clears_and_sets_the_series(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    base = {"title": "Zed One", "author_name_0": "Shirley Jackson",
            "author_id_0": str(shelf["jackson"])}  # fmt: skip
    cleared = await member.post(f"/catalog/stories/{shelf['z1']}/edit", data=base)
    assert cleared.status_code == 303, cleared.text[-2000:]
    assert ("Zed One", None, None) in await stories_in(factory, "Mixed Collection")
    taken = await member.post(f"/catalog/stories/{shelf['second']}/edit", data={
        **base, "title": "Second", "series_name": "Apple Tales", "series_id": str(shelf["apple"]),
        "series_number": "3",
    })  # fmt: skip
    assert taken.status_code == 409 and "Apple Three" in words(taken.text)
    given = await member.post(f"/catalog/stories/{shelf['second']}/edit", data={
        **base, "title": "Second", "series_name": "Apple Tales", "series_id": str(shelf["apple"]),
        "series_number": "4",
    })  # fmt: skip
    assert given.status_code == 303, given.text[-2000:]
    assert ("Second", "Apple Tales", "4.00") in await stories_in(factory, "Mixed Collection")


@pytest.mark.ac("019/AC-06")
async def test_same_title_and_reuse_by_suggestion(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    twin = await factory.story(
        "Second", alice, series_id=None, series_number=None,
        author_ids=[shelf["jackson"]], book_ids=[shelf["other"]],
    )  # fmt: skip
    assert twin != shelf["second"]
    found = (await member.get("/suggest/stories", params={"q": "Second"})).text
    assert "in Mixed Collection" in words(found) and "#" not in words(found)
    base = {"title": "Second", "story_id": str(shelf["second"]), "author_name_0": "Shirley Jackson",
            "author_id_0": str(shelf["jackson"])}  # fmt: skip
    added = await member.post(f"/catalog/books/{shelf['other']}/stories/add", data=base)
    assert added.status_code == 303, added.text[-2000:]
    assert (
        await factory.scalar("SELECT count(*) FROM book_story WHERE book_id = :b", b=shelf["other"])
        == 3
    )  # First, the twin, and the reused Second: not a copy
    assert await factory.scalar("SELECT count(*) FROM story WHERE title = 'Second'") == 2


@pytest.mark.ac("019/AC-04")
async def test_story_hints_say_a_series_is_optional(
    member: httpx.AsyncClient, shelf: dict[str, uuid.UUID]
) -> None:
    hint = "Leave the series and number blank for a story that isn't part of a series"
    add = (await member.get(f"/catalog/books/{shelf['book']}/stories/add")).text
    edit = (await member.get(f"/catalog/books/{shelf['book']}/edit")).text
    assert hint in words(add)
    assert "leave the series and number blank for a story that isn't part of a series" in words(
        edit
    )


# --------------------------------------------------------------------------- US2 display


def story_items(page: str) -> list[str]:
    block = re.search(r'<ul class="story-list"[^>]*>(.*?)</ul>', page, re.S)
    assert block, "no story list"
    return [words(li) for li in re.findall(r"<li>(.*?)</li>", block.group(1), re.S)]


@pytest.mark.ac("019/AC-08")
@pytest.mark.ac("019/AC-09")
@pytest.mark.ac("019/AC-10")
async def test_book_entry_and_edit_book_lists(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    entry = await factory.entry(alice, shelf["book"], status="reading")
    for path in (f"/books/{shelf['book']}", f"/entries/{entry}",
                 f"/catalog/books/{shelf['book']}/edit"):  # fmt: skip
        page = (await member.get(path)).text
        items = story_items(page)
        assert [i.split(" · ")[0].split(" Edit")[0] for i in items] == [
            "#3 Apple Tales — Apple Three", "#1 Zed Tales — Zed One",
            "Second by Shirley Jackson", "First by Shirley Jackson",
        ], path  # fmt: skip  # PR #44 review: no series, so the authors show
        assert "/series/None" not in page and "#None" not in page and "— Second" not in page
    book = (await member.get(f"/books/{shelf['book']}")).text
    assert "First by Shirley Jackson · Also in “ Another Anthology ”" in story_items(book)[3]
    assert f'<a href="/books/{shelf["other"]}">Another Anthology</a>' in book


@pytest.mark.ac("019/AC-08")
async def test_author_pages_and_edit_story(
    member: httpx.AsyncClient, shelf: dict[str, uuid.UUID]
) -> None:
    author = (await member.get(f"/authors/{shelf['jackson']}")).text
    stories = re.search(r"<h2[^>]*>Stories</h2>\s*<ul[^>]*>(.*?)</ul>", author, re.S)
    assert stories, "no Stories list"
    listed = [words(li) for li in re.findall(r"<li>(.*?)</li>", stories.group(1), re.S)]
    assert "Second · in Mixed Collection" in listed
    assert "#1 Zed Tales — Zed One · in Mixed Collection" in listed
    assert "#None" not in author
    edit_author = (await member.get(f"/catalog/authors/{shelf['jackson']}/edit")).text
    assert f'<a href="/catalog/stories/{shelf["second"]}/edit">Second</a>' in edit_author
    story = (await member.get(f"/catalog/stories/{shelf['second']}/edit")).text
    assert "All of" not in story and "/series/None" not in story
    with_series = (await member.get(f"/catalog/stories/{shelf['z1']}/edit")).text
    assert f'<a href="/series/{shelf["zed"]}">All of Zed Tales</a>' in with_series


# --------------------------------------------------------------------------- US3 series pages


@pytest.mark.ac("019/AC-11")
@pytest.mark.ac("019/AC-12")
async def test_series_pages_only_hold_their_stories(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, shelf: dict[str, uuid.UUID]
) -> None:
    await factory.book("Zed Two", alice, author_ids=[shelf["jackson"]], series_id=shelf["zed"],
                       series_number="2")  # fmt: skip
    page = (await member.get(f"/series/{shelf['zed']}")).text
    text = words(page)
    assert "Zed One" in text and "Second" not in text and "First" not in text
    assert "of 1 story" in text  # the progress line counts only this series' stories
    assert re.search(r">Add #3<", page)  # next after the book at #2 and the story at #1
    base = {"title": "Zed One", "author_name_0": "Shirley Jackson",
            "author_id_0": str(shelf["jackson"])}  # fmt: skip
    await member.post(f"/catalog/stories/{shelf['z1']}/edit", data=base)
    after = words((await member.get(f"/series/{shelf['zed']}")).text)
    assert "Zed One" not in after and "of 1 story" not in after


@pytest.mark.ac("019/AC-03")
async def test_a_bad_number_still_reports_the_other_row_errors(member: httpx.AsyncClient) -> None:
    """PR #44 review: a number that doesn't parse doesn't hide a too-long series name."""
    refused = await member.post("/books/add", data=add_book(
        story_title_0="A", story_number_0="x", story_series_name_0="S" * 250,
    ))  # fmt: skip
    assert refused.status_code == 422
    assert error_for(refused.text, "story_number_0").startswith("Story 1: ")
    assert error_for(refused.text, "story_series_name_0").startswith("Story 1: Keep")
