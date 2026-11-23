"""Spec 013 User Story 2: mistakes on story rows are caught before anything is saved."""

from __future__ import annotations

import html
import re
import uuid
from decimal import Decimal
from typing import Any

import httpx
import pytest

from book_tracker.persistence import catalog as catalog_persistence
from book_tracker.services import catalog as catalog_service
from tests.conftest import Factory, TestUser
from tests.integration.test_anthology_add import (  # noqa: F401 - fixtures
    THREE,
    alice_fixture,
    counts,
    dresden_fixture,
    field_value,
    member_fixture,
    side_jobs,
    stories_of,
    story_rows,
    text_of,
)


def field_error(page: str, field: str) -> str:
    found = re.search(rf'<p class="field-error" id="{field}-error">(.*?)</p>', page, re.S)
    return " ".join(html.unescape(found.group(1)).split()) if found else ""


def summary_has(page: str, field: str) -> bool:
    box = re.search(r'<div class="error-summary".*?</div>', page, re.S)
    return bool(box and f'href="#{field}"' in box.group(0))


@pytest.fixture
async def publicity(factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]) -> uuid.UUID:
    first = await factory.book("Side Jobs First Printing", alice, author_ids=[dresden["jim"]])
    return await factory.story(
        "Publicity and Advertising", alice, series_id=dresden["series"], series_number="2.5",
        author_ids=[dresden["jim"]], book_ids=[first],
    )  # fmt: skip


@pytest.mark.ac("013/AC-08")
async def test_unticked_box_with_rows(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    data = side_jobs(dresden, **THREE)
    del data["anthology"]
    before = await counts(factory)
    page = await member.post("/books/add", data=data)
    assert page.status_code == 422 and await counts(factory) == before
    assert field_error(page.text, "anthology").startswith("Tick “This book is an anthology")
    assert summary_has(page.text, "anthology")
    assert field_value(page.text, "story_title_2") == "Something Borrowed"


@pytest.mark.ac("013/AC-10")
async def test_row_errors_save_nothing(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    before = await counts(factory)
    data = side_jobs(dresden, story_title_0="Good", story_number_0="1.5",
                     story_title_1="", story_number_1="2.5",
                     story_title_2="No number", story_title_3="Too big", story_number_3="1000",
                     notes="Kept note")  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 422 and await counts(factory) == before
    assert field_error(page.text, "story_title_1") == "Story 2: Enter the story's title"
    assert field_error(page.text, "story_number_2") == (
        "Story 3: Enter the story's number in the series"
    )
    assert field_error(page.text, "story_number_3").startswith("Story 4: ")
    for name in ("story_title_1", "story_number_2", "story_number_3"):
        assert summary_has(page.text, name)
        assert re.search(rf'<input[^>]*id="{name}"[^>]*aria-invalid="true"', page.text)
    assert field_value(page.text, "story_title_0") == "Good" and "Kept note" in page.text


@pytest.mark.ac("013/AC-11")
async def test_no_series_anywhere(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    data = side_jobs(dresden, series_name="", series_id="", story_title_0="A",
                     story_number_0="1.5")  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 422
    assert field_error(page.text, "story_series_name_0") == (
        "Story 1: Choose a series for this story, or give the book a series"
    )
    assert await factory.scalar("SELECT count(*) FROM book") == 0


@pytest.mark.ac("013/AC-12")
async def test_two_rows_with_one_number(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    data = side_jobs(dresden, story_title_0="A", story_number_0="2.5", story_title_1="B",
                     story_number_1="3.5", story_title_2="C", story_number_2="2.5")  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 422
    message = "Story 1 and Story 3 have the same number in The Dresden Files"
    assert field_error(page.text, "story_number_0") == message
    assert field_error(page.text, "story_number_2") == message
    assert await factory.scalar("SELECT count(*) FROM book") == 0


@pytest.mark.ac("013/AC-13")
async def test_every_taken_row_is_shown_at_once(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser,
    dresden: dict[str, uuid.UUID], publicity: uuid.UUID,
) -> None:  # fmt: skip
    first = await factory.book("Another Printing", alice, author_ids=[dresden["jim"]])
    await factory.story(
        "Something Borrowed", alice, series_id=dresden["series"], series_number="6.5",
        author_ids=[dresden["jim"]], book_ids=[first],
    )  # fmt: skip
    page = await member.post("/books/add", data=side_jobs(dresden, **THREE))
    assert page.status_code == 409
    assert 'name="use_story_1"' in page.text and 'name="use_story_2"' in page.text
    assert not field_error(page.text, "story_number_0")


@pytest.mark.ac("013/AC-13")
async def test_a_taken_number_offers_the_story(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID],
    publicity: uuid.UUID,
) -> None:  # fmt: skip
    before = await counts(factory)
    page = await member.post("/books/add", data=side_jobs(dresden, **THREE))
    assert page.status_code == 409 and await counts(factory) == before
    assert field_error(page.text, "story_number_1") == (
        "Story 2: #2.5 “Publicity and Advertising” is already in the catalog"
    )
    assert "in Side Jobs First Printing" in text_of(page.text)
    button = re.search(
        r'<button type="submit" name="use_story_1" value="([^"]+)">Use that story', page.text
    )
    assert button and button.group(1) == str(publicity)
    # Choosing it redraws the row as that story, saving nothing.
    chosen = await member.post(
        "/books/add", data=side_jobs(dresden, use_story_1=str(publicity), **THREE)
    )
    assert chosen.status_code == 200 and await counts(factory) == before
    assert field_value(chosen.text, "story_id_1") == str(publicity)
    assert (
        "#2.5 “Publicity and Advertising” (The Dresden Files), already in the catalog"
        in text_of(chosen.text)
    )
    assert 'class="error-summary"' not in chosen.text
    # Saving links it: no second story at #2.5.
    assert field_value(chosen.text, "story_series_name_1") == "The Dresden Files"
    data = side_jobs(dresden, **{**THREE, "story_id_1": str(publicity)})
    response = await member.post("/books/add", data=data)
    assert response.status_code == 303, response.text
    assert await factory.scalar("SELECT count(*) FROM story") == 3
    assert (
        await factory.scalar("SELECT count(*) FROM book_story WHERE story_id = :s", s=publicity)
        == 2
    )


async def test_using_a_story_that_was_deleted(
    member: httpx.AsyncClient,
    dresden: dict[str, uuid.UUID],
) -> None:
    page = await member.post("/books/add", data=side_jobs(dresden, use_story_0=str(uuid.uuid4()),
                                                          story_title_0="A"))  # fmt: skip
    assert page.status_code == 409
    assert "That story was just deleted from the catalog" in field_error(page.text, "story_title_0")
    gone = await member.post("/books/add", data=side_jobs(
        dresden, story_id_0=str(uuid.uuid4()), story_title_0="A", story_number_0="9.5",
    ))  # fmt: skip
    assert gone.status_code == 422
    assert "That story was just deleted from the catalog" in field_error(gone.text, "story_title_0")


@pytest.mark.ac("013/AC-14")
async def test_a_number_shared_with_a_book_is_fine(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser,
    dresden: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    await factory.book("A novella", alice, series_id=dresden["series"], series_number="2.5")
    data = side_jobs(dresden, series_number="2.5", title="Side Jobs",
                     story_title_0="Publicity", story_number_0="2.5")  # fmt: skip
    data["series_number"] = ""  # the anthology itself has no number here
    response = await member.post("/books/add", data=data)
    assert response.status_code == 303, response.text
    assert [s[2] for s in await stories_of(factory, "Side Jobs")] == [Decimal("2.5")]


@pytest.mark.ac("013/AC-16")
async def test_a_number_taken_meanwhile(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser,
    dresden: dict[str, uuid.UUID], monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """Another member saves #2.5 after the pre-check: the database refuses ours."""
    first = await factory.book("Elsewhere", alice, author_ids=[dresden["jim"]])
    await factory.story(
        "Publicity", alice, series_id=dresden["series"], series_number="2.5",
        author_ids=[dresden["jim"]], book_ids=[first],
    )  # fmt: skip

    async def blind(db: Any, pairs: Any) -> dict[Any, Any]:
        return {}  # neither the page's check nor the service's sees it

    monkeypatch.setattr(catalog_service, "stories_at", blind)
    before = await counts(factory)
    page = await member.post("/books/add", data=side_jobs(dresden, **THREE))
    assert page.status_code == 409, page.text
    assert await counts(factory) == before
    assert field_error(page.text, "story_number_1") == (
        "Story 2: #2.5 “Publicity” is already in the catalog"
    )
    assert 'name="use_story_1"' in page.text


@pytest.mark.ac("013/AC-17")
async def test_a_late_failure_leaves_nothing_behind(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """The book, a new author and two stories are written before the third fails."""
    real = catalog_persistence.create_story
    made = {"n": 0}

    async def third_fails(db: Any, **values: Any) -> Any:
        made["n"] += 1
        if made["n"] == 3:
            raise catalog_service.ValidationFailed.single(
                "series_id", "That series is not in the catalog"
            )
        return await real(db, **values)

    monkeypatch.setattr(catalog_persistence, "create_story", third_fails)
    before = await counts(factory)
    data = side_jobs(dresden, story_author_name_0="Brand New Writer",
                     confirm_story_author_0="Brand New Writer", **THREE)  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 422, page.text
    assert made["n"] == 3
    assert await counts(factory) == before
    assert field_error(page.text, "story_series_name_2") == (
        "Story 3: That series is not in the catalog"
    )
    assert story_rows(page.text) == 3
