"""Spec 009: stories in collections. Database rules and the catalog story use cases (T004,
T006); the pages are tested further down."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from book_tracker.services import catalog
from book_tracker.services.errors import ConflictError, NotFoundError, ValidationFailed
from tests.conftest import Factory, TestUser, signed_in, ui_csrf


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def ben(factory: Factory) -> TestUser:
    return await factory.user("ben", display_name="Ben")


@pytest.fixture
async def world(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    """The Dresden Files with Storm Front (#1) and Fool Moon (#2); Side Jobs (no series)
    holding Restoration of Faith (#1.5); Brief Cases (no series, no stories)."""
    butcher = await factory.author("Jim Butcher", alice)
    dresden = await factory.series("The Dresden Files", alice)
    storm = await factory.book(
        "Storm Front", alice, author_ids=[butcher], series_id=dresden, series_number="1"
    )
    fool = await factory.book(
        "Fool Moon", alice, author_ids=[butcher], series_id=dresden, series_number="2"
    )
    side_jobs = await factory.book("Side Jobs", alice, author_ids=[butcher])
    brief_cases = await factory.book("Brief Cases", alice, author_ids=[butcher])
    restoration = await factory.story(
        "Restoration of Faith", alice, series_id=dresden, series_number="1.5",
        author_ids=[butcher], book_ids=[side_jobs],
    )  # fmt: skip
    return {
        "butcher": butcher, "dresden": dresden, "storm": storm, "fool": fool,
        "side_jobs": side_jobs, "brief_cases": brief_cases, "restoration": restoration,
    }  # fmt: skip


async def _run(app: Any, action: Any) -> Any:
    async with app.state.db.sessionmaker() as db:
        result = await action(db)
        await db.commit()
    return result


# --------------------------------------------------------------------------- database rules


async def test_two_stories_never_share_a_number(
    factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    """SC-004, FR-003: the database refuses a second story at the same series and number."""
    with pytest.raises(IntegrityError, match="story_series_number_uq"):
        await factory.story(
            "Another 1.5", alice, series_id=world["dresden"], series_number="1.5",
            author_ids=[world["butcher"]], book_ids=[world["brief_cases"]],
        )  # fmt: skip


async def test_story_number_range_and_series_required(
    factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    with pytest.raises(IntegrityError, match="story_series_number_range"):
        await factory.story(
            "Too far", alice, series_id=world["dresden"], series_number="-1",
            author_ids=[world["butcher"]], book_ids=[world["side_jobs"]],
        )  # fmt: skip
    with pytest.raises(IntegrityError, match="series_id"):
        await factory.execute(
            "INSERT INTO story (id, title, series_id, series_number, created_by, updated_by) "
            "VALUES (gen_random_uuid(), 'x', NULL, 1, :u, :u)",
            u=alice.id,
        )


@pytest.mark.ac("009/AC-06")
async def test_a_story_may_share_a_number_with_a_book(
    factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    await factory.story(
        "Also number one", alice, series_id=world["dresden"], series_number="1",
        author_ids=[world["butcher"]], book_ids=[world["brief_cases"]],
    )  # fmt: skip


async def test_an_author_with_a_story_cannot_be_deleted_by_the_database(
    factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    only_stories = await factory.author("Story Only", alice)
    await factory.execute(
        "INSERT INTO story_author (story_id, author_id, position) VALUES (:s, :a, 2)",
        s=world["restoration"], a=only_stories,
    )  # fmt: skip
    with pytest.raises(IntegrityError, match="story_author_author_id_fkey"):
        await factory.execute("DELETE FROM author WHERE id = :id", id=only_stories)


# --------------------------------------------------------------------------- services


def _new(world: dict[str, uuid.UUID], title: str, number: str) -> catalog.NewStory:
    return catalog.NewStory(
        title=title,
        author_ids=[world["butcher"]],
        series_id=world["dresden"],
        series_number=Decimal(number),
    )


async def test_add_new_story(app: Any, alice: TestUser, world: dict[str, uuid.UUID]) -> None:
    story = await _run(
        app,
        lambda db: catalog.add_new_story(
            db, alice.id, world["side_jobs"], _new(world, "  Publicity  and Advertising ", "2.5")
        ),
    )
    assert story.title == "Publicity and Advertising"
    assert story.series_number == Decimal("2.5")
    assert [b.title for b in story.books] == ["Side Jobs"]
    stories = await _run(app, lambda db: catalog.book_stories(db, world["side_jobs"]))
    assert [s.title for s in stories] == ["Restoration of Faith", "Publicity and Advertising"]


async def test_add_new_story_number_taken(
    app: Any, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    with pytest.raises(ConflictError) as raised:
        await _run(
            app,
            lambda db: catalog.add_new_story(
                db, alice.id, world["brief_cases"], _new(world, "Clash", "1.5")
            ),
        )
    assert raised.value.code == "story_number_taken"
    assert raised.value.existing_id == world["restoration"]
    assert raised.value.existing_label == "#1.5 Restoration of Faith"


async def test_add_new_story_checks_references(
    app: Any, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    with pytest.raises(NotFoundError):
        await _run(
            app, lambda db: catalog.add_new_story(db, alice.id, uuid.uuid4(), _new(world, "x", "3"))
        )
    bad = catalog.NewStory(
        title="x", author_ids=[uuid.uuid4()], series_id=uuid.uuid4(), series_number=Decimal(3)
    )
    with pytest.raises(ValidationFailed) as raised:
        await _run(app, lambda db: catalog.add_new_story(db, alice.id, world["side_jobs"], bad))
    assert {e.field for e in raised.value.errors} == {"author_ids", "series_id"}


async def test_add_existing_story(app: Any, alice: TestUser, world: dict[str, uuid.UUID]) -> None:
    story, added = await _run(
        app,
        lambda db: catalog.add_existing_story(
            db, alice.id, world["brief_cases"], world["restoration"]
        ),
    )
    assert added
    assert [b.title for b in story.books] == ["Brief Cases", "Side Jobs"]
    story, added = await _run(
        app,
        lambda db: catalog.add_existing_story(
            db, alice.id, world["brief_cases"], world["restoration"]
        ),
    )
    assert not added
    with pytest.raises(NotFoundError):
        await _run(
            app,
            lambda db: catalog.add_existing_story(db, alice.id, world["brief_cases"], uuid.uuid4()),
        )
    with pytest.raises(NotFoundError):
        await _run(
            app,
            lambda db: catalog.add_existing_story(db, alice.id, uuid.uuid4(), world["restoration"]),
        )


async def test_update_story(
    app: Any, factory: Factory, alice: TestUser, ben: TestUser, world: dict[str, uuid.UUID]
) -> None:
    other = await factory.story(
        "Publicity and Advertising", alice, series_id=world["dresden"], series_number="2.5",
        author_ids=[world["butcher"]], book_ids=[world["side_jobs"]],
    )  # fmt: skip
    story = await _run(
        app,
        lambda db: catalog.update_story(
            db,
            ben.id,
            world["restoration"],
            {"title": "Restoration", "series_number": Decimal(1.25)},
        ),
    )
    assert (story.title, story.series_number, story.updated_by.display_name) == (
        "Restoration",
        Decimal("1.25"),
        "Ben",
    )
    with pytest.raises(ConflictError) as raised:
        await _run(
            app,
            lambda db: catalog.update_story(
                db, ben.id, world["restoration"], {"series_number": Decimal("2.5")}
            ),
        )
    assert raised.value.existing_id == other
    with pytest.raises(ValidationFailed):
        await _run(
            app,
            lambda db: catalog.update_story(db, ben.id, world["restoration"], {"author_ids": []}),
        )
    with pytest.raises(NotFoundError):
        await _run(app, lambda db: catalog.update_story(db, ben.id, uuid.uuid4(), {"title": "x"}))


async def test_remove_story(
    app: Any, factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    await factory.execute(
        "INSERT INTO book_story (book_id, story_id) VALUES (:b, :s)",
        b=world["brief_cases"], s=world["restoration"],
    )  # fmt: skip
    deleted = await _run(
        app, lambda db: catalog.remove_story(db, alice.id, world["side_jobs"], world["restoration"])
    )
    assert deleted is False
    story = await _run(app, lambda db: catalog.get_story(db, world["restoration"]))
    assert [b.title for b in story.books] == ["Brief Cases"]
    with pytest.raises(NotFoundError):  # no longer in Side Jobs
        await _run(
            app,
            lambda db: catalog.remove_story(db, alice.id, world["side_jobs"], world["restoration"]),
        )
    deleted = await _run(
        app,
        lambda db: catalog.remove_story(db, alice.id, world["brief_cases"], world["restoration"]),
    )
    assert deleted is True
    assert await factory.scalar("SELECT count(*) FROM story") == 0


async def test_link_to_a_story_deleted_meanwhile_is_not_found(
    app: Any, factory: Factory, alice: TestUser, world: dict[str, uuid.UUID], monkeypatch: Any
) -> None:
    """R2 race: the story's last link was removed after the look-up; the link insert then
    fails on its foreign key, which reads as not found."""
    from book_tracker.persistence import catalog as persistence

    real = persistence.get_story

    async def vanish(db: Any, story_id: uuid.UUID) -> Any:
        found = await real(db, story_id)
        await factory.execute("DELETE FROM story WHERE id = :id", id=story_id)
        return found

    monkeypatch.setattr(persistence, "get_story", vanish)
    with pytest.raises(NotFoundError):
        await _run(
            app,
            lambda db: catalog.add_existing_story(
                db, alice.id, world["brief_cases"], world["restoration"]
            ),
        )


# --------------------------------------------------------------------------- US1 pages


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


def text_of(page: httpx.Response) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page.text)).split())


def field_error(page: httpx.Response, field: str) -> str:
    found = re.search(rf'<p class="field-error" id="{field}-error">(.*?)</p>', page.text, re.S)
    return html.unescape(found.group(1)).strip() if found else ""


def section(page: httpx.Response, heading: str) -> str:
    """The text of the section after an <h2> with this heading, up to the next <h2>."""
    found = re.search(rf"<h2[^>]*>{re.escape(heading)}</h2>(.*?)(?=<h2|</main>)", page.text, re.S)
    assert found, f"no {heading} section"
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", found.group(1))).split())


async def story_form(
    member: httpx.AsyncClient, book_id: uuid.UUID, **values: str
) -> dict[str, str]:
    """The Add a story form as first shown, with ``values`` typed over it."""
    page = await member.get(f"/catalog/books/{book_id}/stories/add")
    assert page.status_code == 200, page.text
    data: dict[str, str] = {}
    form = re.search(
        r'<form method="post" action="/catalog/books/[^"]+"[^>]*>(.*?)</form>', page.text, re.S
    )
    assert form
    for tag in re.findall(r"<input\b[^>]*>", form.group(1)):
        name = re.search(r'name="([^"]+)"', tag)
        if name and 'type="submit"' not in tag:
            value = re.search(r'value="([^"]*)"', tag)
            data[name.group(1)] = html.unescape(value.group(1)) if value else ""
    data.update(values)
    return data


async def add_story(member: httpx.AsyncClient, book_id: uuid.UUID, **values: str) -> httpx.Response:
    data = await story_form(member, book_id, **values)
    return await member.post(f"/catalog/books/{book_id}/stories/add", data=data)


async def story_count(factory: Factory) -> int:
    return int(await factory.scalar("SELECT count(*) FROM story"))


@pytest.mark.ac("009/AC-01")
async def test_edit_book_lists_stories(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    witches = await factory.series("Aardvark Tales", alice)
    await factory.story(
        "Something Borrowed", alice, series_id=world["dresden"], series_number="6.5",
        author_ids=[world["butcher"]], book_ids=[world["side_jobs"]],
    )  # fmt: skip
    await factory.story(
        "An Aside", alice, series_id=witches, series_number="3",
        author_ids=[world["butcher"]], book_ids=[world["side_jobs"]],
    )  # fmt: skip
    page = await member.get(f"/catalog/books/{world['side_jobs']}/edit")
    stories = section(page, "Stories in this book")
    assert (
        stories.index("#3 Aardvark Tales — An Aside")
        < stories.index("#1.5 The Dresden Files — Restoration of Faith")
        < stories.index("#6.5 The Dresden Files — Something Borrowed")
    )
    assert f'href="/catalog/stories/{world["restoration"]}/edit"' in page.text
    assert (
        f'action="/catalog/books/{world["side_jobs"]}/stories/{world["restoration"]}/remove"'
        in page.text
    )
    assert f'href="/catalog/books/{world["side_jobs"]}/stories/add"' in page.text
    empty = await member.get(f"/catalog/books/{world['brief_cases']}/edit")
    assert "No stories recorded for this book." in section(empty, "Stories in this book")


@pytest.mark.ac("009/AC-02")
async def test_add_story_form_defaults(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    data = await story_form(member, world["storm"])
    assert data["author_name_0"] == "Jim Butcher"
    assert data["author_id_0"] == str(world["butcher"])
    assert data["series_name"] == "The Dresden Files"
    assert data["series_id"] == str(world["dresden"])
    assert data["series_number"] == "" and data["title"] == ""
    no_series = await story_form(member, world["side_jobs"])
    assert no_series["series_name"] == "" and no_series["author_name_0"] == "Jim Butcher"
    page = await member.get(f"/catalog/books/{world['storm']}/stories/add")
    assert "<h1>Add a story to “Storm Front”</h1>" in html.unescape(page.text)
    assert (await member.get(f"/catalog/books/{uuid.uuid4()}/stories/add")).status_code == 404


@pytest.mark.ac("009/AC-03")
async def test_add_story(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    saved = await add_story(
        member, world["side_jobs"], title="Publicity and Advertising",
        series_name="The Dresden Files", series_id=str(world["dresden"]), series_number="2.5",
    )  # fmt: skip
    assert saved.status_code == 303, saved.text
    location = saved.headers["location"]
    assert location.startswith(f"/catalog/books/{world['side_jobs']}/edit?msg=story_added&story=")
    page = await member.get(location)
    assert "Added the story “Publicity and Advertising”." in text_of(page)
    assert "#2.5 The Dresden Files — Publicity and Advertising" in section(
        page, "Stories in this book"
    )
    # A story id from another book, or a made-up one, names nothing.
    other = location.split("story=")[1].removesuffix("#stories")
    for crafted in (
        f"/catalog/books/{world['brief_cases']}/edit?msg=story_added&story={other}",
        f"/catalog/books/{world['side_jobs']}/edit?msg=story_added&story={uuid.uuid4()}",
        f"/catalog/books/{world['side_jobs']}/edit?msg=story_added&story=nonsense",
    ):
        assert "Added the story" not in (await member.get(crafted)).text


@pytest.mark.ac("009/AC-04")
async def test_add_story_errors(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    refused = await add_story(member, world["side_jobs"], title=" ", series_number="1000")
    assert refused.status_code == 422
    assert field_error(refused, "title") == "Enter a title"
    assert field_error(refused, "series_name") == "Choose a series"
    assert field_error(refused, "series_number") != ""
    missing = await add_story(member, world["storm"], title="Kept title", series_number="")
    assert missing.status_code == 422
    assert field_error(missing, "series_number") == "Enter the story's number in the series"
    assert 'value="Kept title"' in missing.text
    assert await story_count(factory) == 1


@pytest.mark.ac("009/AC-05")
async def test_number_held_by_story(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    clash = await add_story(member, world["storm"], title="Restoration", series_number="1.5")
    assert clash.status_code == 409
    words = text_of(clash)
    assert "#1.5 “Restoration of Faith” is already in the catalog, in Side Jobs." in words
    assert (
        f'<button type="submit" name="use_story" value="{world["restoration"]}">'
        "Add that story to this book</button>"
    ) in clash.text
    assert 'value="Restoration"' in clash.text  # the form is kept, to change the number
    assert await story_count(factory) == 1
    data = await story_form(member, world["storm"], title="Restoration", series_number="1.5")
    linked = await member.post(
        f"/catalog/books/{world['storm']}/stories/add",
        data={**data, "use_story": str(world["restoration"])},
    )
    assert linked.status_code == 303
    assert linked.headers["location"].endswith(f"story={world['restoration']}#stories")
    books = await factory.scalar(
        "SELECT string_agg(b.title, ', ' ORDER BY b.title) FROM book_story bs "
        "JOIN book b ON b.id = bs.book_id WHERE bs.story_id = :id",
        id=world["restoration"],
    )
    assert books == "Side Jobs, Storm Front"
    assert await story_count(factory) == 1


@pytest.mark.ac("009/AC-05")
async def test_number_taken_in_a_race(
    member: httpx.AsyncClient,
    factory: Factory,
    alice: TestUser,
    world: dict[str, uuid.UUID],
    monkeypatch: Any,
) -> None:
    """Another member adds a story at the number after the look-up: the unique index
    refuses the second, and the same choice is shown."""
    from book_tracker.services import catalog as service

    real, calls = service.story_at, []

    async def nothing_yet(db: Any, series_id: uuid.UUID, number: Decimal) -> Any:
        calls.append(number)
        if len(calls) > 1:  # the look-up after the refusal sees the other story
            return await real(db, series_id, number)
        await factory.story(
            "Got There First", alice, series_id=series_id, series_number=str(number),
            author_ids=[world["butcher"]], book_ids=[world["brief_cases"]],
        )  # fmt: skip
        return None

    monkeypatch.setattr(service, "story_at", nothing_yet)
    clash = await add_story(member, world["storm"], title="Late", series_number="3.5")
    assert clash.status_code == 409
    assert "#3.5 “Got There First” is already in the catalog, in Brief Cases." in text_of(clash)
    assert await story_count(factory) == 2


@pytest.mark.ac("009/AC-06")
async def test_number_shared_with_book(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    saved = await add_story(member, world["side_jobs"], title="A Fool Moon story",
                            series_name="The Dresden Files", series_id=str(world["dresden"]),
                            series_number="2")  # fmt: skip
    assert saved.status_code == 303, saved.text
    assert await story_count(factory) == 2


@pytest.mark.ac("009/AC-07")
async def test_story_new_names(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    data = await story_form(
        member, world["side_jobs"], title="Love Hurts", series_name="Dresden Files Shorts",
        series_number="11.5", author_name_1="Jim Butchr",
    )  # fmt: skip
    url = f"/catalog/books/{world['side_jobs']}/stories/add"
    asked = await member.post(url, data=data)
    assert asked.status_code == 409
    assert (
        field_error(asked, "series_name")
        == "“Dresden Files Shorts” is not in the family catalog yet"
    )
    assert field_error(asked, "author_name_1") == "“Jim Butchr” is not in the family catalog yet"
    assert await story_count(factory) == 1
    confirmed = await member.post(
        url,
        data={
            **data,
            "confirm_series": "Dresden Files Shorts",
            "confirm_author_1": "Jim Butchr",
        },
    )
    assert confirmed.status_code == 303, confirmed.text
    assert (
        await factory.scalar("SELECT count(*) FROM series WHERE name = 'Dresden Files Shorts'") == 1
    )
    authors = await factory.scalar(
        "SELECT string_agg(a.name, ', ' ORDER BY sa.position) FROM story s "
        "JOIN story_author sa ON sa.story_id = s.id JOIN author a ON a.id = sa.author_id "
        "WHERE s.title = 'Love Hurts'"
    )
    assert authors == "Jim Butcher, Jim Butchr"


@pytest.mark.ac("009/AC-08")
async def test_entry_page_lists_stories(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    entry = await factory.entry(alice, world["side_jobs"])
    page = await member.get(f"/entries/{entry}")
    stories = section(page, "Stories in this book")
    assert "#1.5 The Dresden Files — Restoration of Faith" in stories
    assert f'<a href="/series/{world["dresden"]}">The Dresden Files</a>' in page.text
    assert (
        f'<a href="/catalog/books/{world["side_jobs"]}/edit#stories">Edit the stories</a>'
        in page.text
    )
    plain = await factory.entry(alice, world["brief_cases"])
    assert "Stories in this book" not in (await member.get(f"/entries/{plain}")).text


# --------------------------------------------------------------------------- US3


async def edit_form(
    member: httpx.AsyncClient, story_id: uuid.UUID, **values: str
) -> dict[str, str]:
    page = await member.get(f"/catalog/stories/{story_id}/edit")
    assert page.status_code == 200, page.text
    form = re.search(
        r'<form method="post" action="/catalog/stories/[^"]+"[^>]*>(.*?)</form>', page.text, re.S
    )
    assert form
    data: dict[str, str] = {}
    for tag in re.findall(r"<input\b[^>]*>", form.group(1)):
        name = re.search(r'name="([^"]+)"', tag)
        if name and 'type="submit"' not in tag:
            value = re.search(r'value="([^"]*)"', tag)
            data[name.group(1)] = html.unescape(value.group(1)) if value else ""
    data.update(values)
    return data


@pytest.mark.ac("009/AC-16")
async def test_edit_story(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    await factory.execute(
        "INSERT INTO book_story (book_id, story_id) VALUES (:b, :s)",
        b=world["brief_cases"], s=world["restoration"],
    )  # fmt: skip
    url = f"/catalog/stories/{world['restoration']}/edit"
    page = await member.get(url)
    assert "<h1>Edit story “Restoration of Faith”</h1>" in html.unescape(page.text)
    assert section(page, "In these books").startswith("Brief Cases Side Jobs")
    saved = await member.post(
        url,
        data=await edit_form(
            member, world["restoration"], title="Restoration", series_number="1.25"
        ),
    )
    assert saved.status_code == 303 and saved.headers["location"] == f"{url}?msg=saved"
    assert "Saved." in text_of(await member.get(saved.headers["location"]))
    for book in ("side_jobs", "brief_cases"):
        listed = section(
            await member.get(f"/catalog/books/{world[book]}/edit"), "Stories in this book"
        )
        assert "#1.25 The Dresden Files — Restoration" in listed
    await factory.story(
        "Publicity and Advertising", alice, series_id=world["dresden"], series_number="2.5",
        author_ids=[world["butcher"]], book_ids=[world["side_jobs"]],
    )  # fmt: skip
    clash = await member.post(
        url, data=await edit_form(member, world["restoration"], series_number="2.5")
    )
    assert clash.status_code == 409
    assert "#2.5 “Publicity and Advertising” already has this number in the series." in text_of(
        clash
    )
    assert (
        await factory.scalar(
            "SELECT series_number::text FROM story WHERE id = :id", id=world["restoration"]
        )
        == "1.25"
    )
    refused = await member.post(url, data=await edit_form(member, world["restoration"], title=""))
    assert refused.status_code == 422 and field_error(refused, "title") == "Enter a title"


@pytest.mark.ac("009/AC-17")
async def test_add_existing_story_by_suggestion(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    found = await member.get("/suggest/stories", params={"field": "title", "title": "restor"})
    assert f'data-id="{world["restoration"]}"' in found.text
    assert "#1.5 The Dresden Files · in Side Jobs" in html.unescape(found.text)
    picked = await add_story(
        member, world["brief_cases"], title="Restoration of Faith",
        story_id=str(world["restoration"]), series_number="",
    )  # fmt: skip
    assert picked.status_code == 303
    assert picked.headers["location"].endswith(
        f"msg=story_added&story={world['restoration']}#stories"
    )
    assert await story_count(factory) == 1
    again = await add_story(
        member,
        world["brief_cases"],
        title="Restoration of Faith",
        story_id=str(world["restoration"]),
    )
    assert "msg=story_already" in again.headers["location"]
    assert "That story is already in this book." in text_of(
        await member.get(again.headers["location"])
    )
    # Without JavaScript, typing a different title leaves the old id behind: it's ignored.
    stale = await add_story(
        member, world["storm"], title="Something Else", story_id=str(world["restoration"]),
        series_number="3.5",
    )  # fmt: skip
    assert stale.status_code == 303
    assert await story_count(factory) == 2


@pytest.mark.ac("009/AC-18")
async def test_remove_story_kept_elsewhere(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    await factory.execute(
        "INSERT INTO book_story (book_id, story_id) VALUES (:b, :s)",
        b=world["brief_cases"], s=world["restoration"],
    )  # fmt: skip
    url = f"/catalog/books/{world['side_jobs']}/stories/{world['restoration']}/remove"
    csrf = await ui_csrf(member)
    asked = await member.post(url, data={"csrf_token": csrf})
    assert asked.status_code == 200
    words = text_of(asked)
    assert "Remove “Restoration of Faith” from “Side Jobs”?" in words
    assert "It stays in: Brief Cases." in words
    assert await factory.scalar("SELECT count(*) FROM book_story") == 2
    done = await member.post(url, data={"csrf_token": csrf, "confirm": "yes"})
    assert done.status_code == 303
    assert "Story removed from this book." in text_of(await member.get(done.headers["location"]))
    assert await story_count(factory) == 1
    assert await factory.scalar("SELECT count(*) FROM book_story") == 1


@pytest.mark.ac("009/AC-19")
async def test_remove_last_link_deletes(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    url = f"/catalog/books/{world['side_jobs']}/stories/{world['restoration']}/remove"
    csrf = await ui_csrf(member)
    asked = await member.post(url, data={"csrf_token": csrf})
    assert "It isn't in any other book, so it will be deleted from the family catalog." in text_of(
        asked
    )
    done = await member.post(url, data={"csrf_token": csrf, "confirm": "yes"})
    assert "Story deleted from the catalog." in text_of(await member.get(done.headers["location"]))
    assert await story_count(factory) == 0


@pytest.mark.ac("009/AC-20")
async def test_author_with_only_stories(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, world: dict[str, uuid.UUID]
) -> None:
    guest = await factory.author("Guest Writer", alice)
    await factory.execute(
        "INSERT INTO story_author (story_id, author_id, position) VALUES (:s, :a, 2)",
        s=world["restoration"], a=guest,
    )  # fmt: skip
    assert "Guest Writer" not in (await member.get("/catalog/authors/unused")).text
    page = await member.get(f"/catalog/authors/{guest}/edit")
    assert (
        f'<a href="/catalog/stories/{world["restoration"]}/edit">Restoration of Faith</a>'
        in page.text
    )
    assert "This author can't be deleted while books or stories list them." in text_of(page)
    assert "Delete author" not in page.text
    csrf = await ui_csrf(member)
    asked = await member.post(f"/catalog/authors/{guest}/delete", data={"csrf_token": csrf})
    assert asked.status_code == 409
    assert "“Guest Writer” now has a story, so it can't be deleted." in text_of(asked)
    refused = await member.post(
        f"/catalog/authors/{guest}/delete", data={"csrf_token": csrf, "confirm": "yes"}
    )
    assert refused.status_code == 409
    assert "“Guest Writer” now has a story, so it wasn't deleted." in text_of(refused)
    api = await member.delete(f"/api/v1/authors/{guest}", headers={"X-CSRF-Token": csrf})
    assert api.status_code == 409


@pytest.mark.ac("009/AC-21")
async def test_story_not_found(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    csrf = await ui_csrf(member)
    missing = uuid.uuid4()
    for response in (
        await member.get(f"/catalog/stories/{missing}/edit"),
        await member.post(f"/catalog/stories/{missing}/edit", data={"csrf_token": csrf}),
        await member.get(f"/catalog/books/{missing}/stories/add"),
        await member.post(f"/catalog/books/{missing}/stories/add", data={"csrf_token": csrf}),
        await member.post(
            f"/catalog/books/{world['brief_cases']}/stories/{world['restoration']}/remove",
            data={"csrf_token": csrf},
        ),
        await member.post(
            f"/catalog/books/{world['side_jobs']}/stories/{missing}/remove",
            data={"csrf_token": csrf},
        ),
    ):
        assert response.status_code == 404
    # "Add that story to this book" for a story deleted meanwhile says so.
    data = await story_form(member, world["brief_cases"], title="Gone", series_number="9")
    gone = await member.post(
        f"/catalog/books/{world['brief_cases']}/stories/add",
        data={**data, "use_story": str(missing)},
    )
    assert gone.status_code == 409
    assert field_error(gone, "title") == "That story was just deleted from the catalog."


# --------------------------------------------------------------------------- US4


@pytest.mark.ac("009/AC-22")
async def test_book_suggested_by_story_title(
    member: httpx.AsyncClient, factory: Factory, world: dict[str, uuid.UUID]
) -> None:
    found = await member.get("/suggest/books", params={"field": "title", "title": "Restoration"})
    assert f'data-id="{world["side_jobs"]}"' in found.text
    assert "Side Jobs — contains “Restoration of Faith”" in " ".join(
        html.unescape(re.sub(r"<[^>]+>", " ", found.text)).split()
    )
    api = await member.get("/api/v1/books", params={"q": "restoration"})
    assert [b["title"] for b in api.json()] == ["Side Jobs"]
    # A title match keeps its usual detail (the authors).
    plain = await member.get("/suggest/books", params={"field": "title", "title": "Side"})
    assert "contains" not in plain.text and "Jim Butcher" in plain.text
