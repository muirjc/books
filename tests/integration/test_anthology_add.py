"""Spec 013 User Stories 1 and 3: an anthology's stories on Add a book.

Contract: specs/013-anthology-on-add/contracts/ui-anthology.md.
"""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in
from tests.fakes import DRAFT_TEXT, FakeSummaryGenerator, good_draft

CHECKBOX = "This book is an anthology or collection"


@pytest.fixture(name="alice")
async def alice_fixture(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture(name="member")
async def member_fixture(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture(name="dresden")
async def dresden_fixture(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    return {
        "jim": await factory.author("Jim Butcher", alice),
        "series": await factory.series("The Dresden Files", alice),
        "ann": await factory.author("Ann Other", alice),
        "other": await factory.series("Other Series", alice),
    }


def side_jobs(d: dict[str, uuid.UUID], **fields: str) -> dict[str, str]:
    data = {
        "title": "Side Jobs", "author_name_0": "Jim Butcher", "author_id_0": str(d["jim"]),
        "series_name": "The Dresden Files", "series_id": str(d["series"]),
        "status": "finished", "anthology": "yes",
    }  # fmt: skip
    data.update(fields)
    return data


THREE = {
    "story_title_0": "Restoration of Faith", "story_number_0": "1.5",
    "story_title_1": "Publicity and Advertising", "story_number_1": "2.5",
    "story_title_2": "Something Borrowed", "story_number_2": "6.5",
}  # fmt: skip


async def counts(factory: Factory) -> tuple[int, ...]:
    found = []
    for table in ("author", "series", "book", "story", "book_story", "reading_entry"):
        found.append(int(await factory.scalar(f"SELECT count(*) FROM {table}")))
    return tuple(found)


async def stories_of(factory: Factory, title: str) -> list[tuple[str, str, Decimal, str]]:
    """(story title, series, number, authors) for the book's stories, by number."""
    rows = await factory.scalar(
        "SELECT string_agg(s.title || '|' || se.name || '|' || s.series_number || '|' || "
        "  (SELECT string_agg(a.name, ',' ORDER BY sa.position) FROM story_author sa "
        "   JOIN author a ON a.id = sa.author_id WHERE sa.story_id = s.id), "
        "  ';' ORDER BY s.series_number) "
        "FROM book b JOIN book_story bs ON bs.book_id = b.id JOIN story s ON s.id = bs.story_id "
        "JOIN series se ON se.id = s.series_id WHERE b.title = :t", t=title,
    )  # fmt: skip
    out = []
    for item in str(rows).split(";") if rows else []:
        t, series, number, authors = item.split("|")
        out.append((t, series, Decimal(number), authors))
    return out


def text_of(page: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def field_value(page: str, name: str) -> str | None:
    found = re.search(rf'<input[^>]*name="{name}"[^>]*value="([^"]*)"', page)
    return html.unescape(found.group(1)) if found else None


def story_rows(page: str) -> int:
    return len(re.findall(r'name="story_title_\d+"', page))


@pytest.mark.ac("013/AC-01")
@pytest.mark.ac("013/AC-02")
async def test_checkbox_and_section(member: httpx.AsyncClient) -> None:
    page = (await member.get("/books/add")).text
    box = re.search(r'<input[^>]*name="anthology"[^>]*>', page)
    assert box and 'type="checkbox"' in box.group(0) and "checked" not in box.group(0)
    assert CHECKBOX in text_of(page)
    assert "Stories in this book" in page and story_rows(page) == 1
    for name in ("story_title_0", "story_number_0", "story_series_name_0", "story_author_name_0"):
        assert f'name="{name}"' in page
    assert "<legend>Story 1</legend>" in page
    assert "Remove story 1" not in page  # the last row has no Remove
    assert "Leave Series blank to use the book's series" in text_of(page)


@pytest.mark.ac("013/AC-03")
async def test_save_with_three_stories(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    response = await member.post("/books/add", data=side_jobs(dresden, **THREE))
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/?msg=added&stories=3"
    assert await stories_of(factory, "Side Jobs") == [
        ("Restoration of Faith", "The Dresden Files", Decimal("1.5"), "Jim Butcher"),
        ("Publicity and Advertising", "The Dresden Files", Decimal("2.5"), "Jim Butcher"),
        ("Something Borrowed", "The Dresden Files", Decimal("6.5"), "Jim Butcher"),
    ]
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 1
    page = (await member.get(response.headers["location"])).text
    assert "Added to your list, with 3 stories." in text_of(page)


@pytest.mark.ac("013/AC-03")
async def test_row_series_and_author_win(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    data = side_jobs(dresden, story_title_0="Other Tale", story_number_0="3",
                     story_series_name_0="Other Series", story_series_id_0=str(dresden["other"]),
                     story_author_name_0="Ann Other")  # typed, an exact catalog name  # fmt: skip
    response = await member.post("/books/add", data=data)
    assert response.status_code == 303, response.text
    assert await stories_of(factory, "Side Jobs") == [
        ("Other Tale", "Other Series", Decimal("3"), "Ann Other")
    ]


@pytest.mark.ac("013/AC-03")
async def test_add_another_and_from_series_carry_the_count(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    one = {"story_title_0": "A", "story_number_0": "1.5"}
    response = await member.post("/books/add", data=side_jobs(dresden, then="another", **one))
    location = response.headers["location"]
    assert re.fullmatch(r"/books/add\?after=[0-9a-f-]+&stories=1", location)
    page = (await member.get(location)).text
    assert "with 1 story" in text_of(page)
    data = side_jobs(dresden, title="Brief Cases", from_series=str(dresden["series"]),
                     story_title_0="B", story_number_0="7.5")  # fmt: skip
    response = await member.post("/books/add", data=data)
    location = response.headers["location"]
    assert re.fullmatch(rf"/series/{dresden['series']}\?added=[0-9a-f-]+&stories=1", location)
    assert "with 1 story" in text_of((await member.get(location)).text)


@pytest.mark.ac("013/AC-04")
async def test_add_another_story_redraws_and_saves_nothing(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    data = side_jobs(dresden, story_title_0="A", story_number_0="1.5", notes="Kept note",
                     action="add_story")  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 200
    assert await counts(factory) == before
    assert story_rows(page.text) == 2
    assert field_value(page.text, "story_title_0") == "A" and "Kept note" in page.text
    assert re.search(r'<input[^>]*id="story_title_1"[^>]*autofocus', page.text)
    assert "Remove story 1" in page.text and "Remove story 2" in page.text
    assert 'class="error-summary"' not in page.text


@pytest.mark.ac("013/AC-05")
async def test_remove_a_story_row(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    page = await member.post(
        "/books/add", data=side_jobs(dresden, action="remove_story:1", **THREE)
    )
    assert page.status_code == 200 and await counts(factory) == before
    assert story_rows(page.text) == 2
    assert field_value(page.text, "story_title_0") == "Restoration of Faith"
    assert field_value(page.text, "story_title_1") == "Something Borrowed"
    assert field_value(page.text, "story_number_1") == "6.5"
    assert re.search(r'<h2[^>]*id="stories-heading"[^>]*tabindex="-1"[^>]*autofocus', page.text)
    # Out of range or the last row: nothing changes.
    one = await member.post("/books/add", data=side_jobs(dresden, action="remove_story:0",
                                                         story_title_0="Only"))  # fmt: skip
    assert story_rows(one.text) == 1 and field_value(one.text, "story_title_0") == "Only"
    odd = await member.post("/books/add", data=side_jobs(dresden, action="remove_story:x"))
    assert odd.status_code == 200 and story_rows(odd.text) == 1


@pytest.mark.ac("013/AC-06")
async def test_fifty_rows_is_the_most(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    rows = {f"story_title_{i}": f"S{i}" for i in range(49)}
    page = (
        await member.post("/books/add", data=side_jobs(dresden, action="add_story", **rows))
    ).text
    assert story_rows(page) == 50
    assert ">Add another story<" not in page
    assert "50 stories is the most for one save." in text_of(page)
    full = {f"story_title_{i}": f"S{i}" for i in range(50)}
    again = (
        await member.post("/books/add", data=side_jobs(dresden, action="add_story", **full))
    ).text
    assert story_rows(again) == 50


@pytest.mark.ac("013/AC-07")
async def test_blank_rows_are_ignored(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    data = side_jobs(dresden, story_title_0="", story_number_0="", story_title_1="A",
                     story_number_1="1.5", story_title_2="")  # fmt: skip
    response = await member.post("/books/add", data=data)
    assert response.headers["location"] == "/?msg=added&stories=1"
    assert [s[0] for s in await stories_of(factory, "Side Jobs")] == ["A"]
    response = await member.post("/books/add", data=side_jobs(dresden, title="Empty"))
    assert response.headers["location"] == "/?msg=added"  # every row empty: no stories


@pytest.mark.ac("013/AC-09")
async def test_from_a_series_gap(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    page = (await member.get(f"/books/add?series={dresden['series']}&number=3")).text
    assert field_value(page, "series_name") == "The Dresden Files"
    assert CHECKBOX in text_of(page)


# --------------------------------------------------------------------------- US3


@pytest.mark.ac("013/AC-18")
async def test_no_anthology_option_for_a_chosen_book(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Existing", alice)
    page = (await member.get(f"/books/add?book={book}")).text
    assert 'name="anthology"' not in page and "story_title_0" not in page
    assert "stories can be added from its Edit book page" in text_of(page)


@pytest.mark.ac("013/AC-19")
async def test_rows_survive_a_draft_and_errors(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID],
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    summary_generator.results.append(good_draft())
    page = (
        await member.post("/books/add", data=side_jobs(dresden, action="draft_summary", **THREE))
    ).text
    assert DRAFT_TEXT in page
    assert story_rows(page) == 3 and field_value(page, "story_number_2") == "6.5"
    assert re.search(r'<input[^>]*name="anthology"[^>]*checked', page)
    # A book field error keeps everything too.
    page = (await member.post("/books/add", data=side_jobs(dresden, title="", **THREE))).text
    assert (
        story_rows(page) == 3 and field_value(page, "story_title_1") == "Publicity and Advertising"
    )
    assert re.search(r'<input[^>]*name="anthology"[^>]*checked', page)


@pytest.mark.ac("013/AC-20")
async def test_choosing_the_existing_book_drops_the_stories(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    existing = await factory.book("Side Jobs", alice, isbn_13="9780451462879")
    page = await member.post(
        "/books/add", data=side_jobs(dresden, isbn_13="9780451462879", **THREE)
    )
    assert page.status_code == 409
    assert re.search(r'name="dropped_stories" value="yes"', page.text)
    response = await member.post("/books/add", data={
        "book_id": str(existing), "status": "finished", "dropped_stories": "yes",
    })  # fmt: skip
    assert response.status_code == 303
    location = response.headers["location"]
    assert re.fullmatch(r"/entries/[0-9a-f-]+\?msg=stories_not_added", location)
    assert await factory.scalar("SELECT count(*) FROM story") == 0
    entry = text_of((await member.get(location)).text)
    assert "The stories you typed were not added. Add them from Edit book." in entry


@pytest.mark.ac("013/AC-21")
async def test_add_and_add_another_starts_plain(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    response = await member.post(
        "/books/add",
        data=side_jobs(dresden, then="another", story_title_0="A", story_number_0="1.5"),
    )
    page = (await member.get(response.headers["location"])).text
    box = re.search(r'<input[^>]*name="anthology"[^>]*>', page)
    assert box and "checked" not in box.group(0)
    assert story_rows(page) == 1 and field_value(page, "story_title_0") == ""


async def test_other_members_list_is_untouched(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID], alice: TestUser
) -> None:
    """Principle I: the only personal record written is the member's own entry."""
    bob = await factory.user("bob")
    await factory.entry(bob, await factory.book("Bob's book", bob))
    response = await member.post("/books/add", data=side_jobs(dresden, **THREE))
    assert response.status_code == 303
    assert (
        await factory.scalar("SELECT count(*) FROM reading_entry WHERE user_id = :u", u=bob.id) == 1
    )
    assert (
        await factory.scalar("SELECT count(*) FROM reading_entry WHERE user_id = :u", u=alice.id)
        == 1
    )
