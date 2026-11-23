"""Spec 013 AC-15: new author and series names on story rows (spec 005 prompts)."""

from __future__ import annotations

import re
import uuid

import httpx
import pytest

from tests.conftest import Factory, TestUser
from tests.integration.test_anthology_add import (  # noqa: F401 - fixtures
    alice_fixture,
    counts,
    dresden_fixture,
    field_value,
    member_fixture,
    side_jobs,
    stories_of,
)
from tests.integration.test_anthology_checks import field_error

PROMPT = "“{}” is not in the family catalog yet"


def confirm_buttons(page: str) -> list[tuple[str, str]]:
    return re.findall(
        r'<button type="submit" name="(confirm_[a-z_0-9]+)" value="([^"]*)">Add “', page
    )


@pytest.mark.ac("013/AC-15")
async def test_new_names_on_rows_are_prompted(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    before = await counts(factory)
    data = side_jobs(
        dresden, story_title_0="A", story_number_0="1", story_author_name_0="Zed Writer",
        story_series_name_0="Zed Tales",
    )  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 409 and await counts(factory) == before
    assert field_error(page.text, "story_author_name_0") == "Story 1: " + PROMPT.format(
        "Zed Writer"
    )
    assert field_error(page.text, "story_series_name_0") == "Story 1: " + PROMPT.format("Zed Tales")
    assert sorted(confirm_buttons(page.text)) == [
        ("confirm_story_author_0", "Zed Writer"), ("confirm_story_series_0", "Zed Tales"),
    ]  # fmt: skip
    data.update(confirm_story_author_0="Zed Writer", confirm_story_series_0="Zed Tales")
    response = await member.post("/books/add", data=data)
    assert response.status_code == 303, response.text
    assert await stories_of(factory, "Side Jobs") == [("A", "Zed Tales", 1, "Zed Writer")]


@pytest.mark.ac("013/AC-15")
async def test_one_prompt_per_name_across_book_and_rows(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    data = side_jobs(
        dresden, author_name_0="New Editor", author_id_0="",
        story_title_0="A", story_number_0="1.5", story_author_name_0="new editor",
        story_title_1="B", story_number_1="2.5", story_author_name_1="New Editor",
        story_title_2="C", story_number_2="3.5", story_series_name_2="Fresh Series",
        story_title_3="D", story_number_3="4.5", story_series_name_3="Fresh Series",
    )  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 409
    assert sorted(confirm_buttons(page.text)) == [
        ("confirm_author_0", "New Editor"), ("confirm_story_series_2", "Fresh Series"),
    ]  # fmt: skip
    assert not field_error(page.text, "story_author_name_0")
    assert not field_error(page.text, "story_series_name_3")
    data.update(confirm_author_0="New Editor", confirm_story_series_2="Fresh Series")
    response = await member.post("/books/add", data=data)
    assert response.status_code == 303, response.text
    assert await factory.scalar("SELECT count(*) FROM author WHERE lower(name) = 'new editor'") == 1
    assert await factory.scalar("SELECT count(*) FROM series WHERE name = 'Fresh Series'") == 1
    stories = await stories_of(factory, "Side Jobs")
    assert {s[3] for s in stories} == {"New Editor"}
    assert [s[1] for s in stories] == [
        "The Dresden Files", "The Dresden Files", "Fresh Series", "Fresh Series",
    ]  # fmt: skip


@pytest.mark.ac("013/AC-15")
async def test_use_a_similar_name_applies_everywhere(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser,
    dresden: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    robb = await factory.author("J.D. Robb", alice)
    data = side_jobs(
        dresden, author_name_0="J DM Robb", author_id_0="",
        story_title_0="A", story_number_0="1.5", story_author_name_0="J DM Robb",
    )  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 409
    assert re.search(rf'name="use_author_0" value="{robb}">Use “J.D. Robb”', page.text)
    redrawn = await member.post("/books/add", data={**data, "use_author_0": str(robb), "title": ""})
    assert field_value(redrawn.text, "story_author_name_0") == "J.D. Robb"
    assert field_value(redrawn.text, "story_author_id_0") == str(robb)
    response = await member.post("/books/add", data={**data, "use_author_0": str(robb)})
    assert response.status_code == 303, response.text
    assert await factory.scalar("SELECT count(*) FROM author") == 3  # nothing new
    assert (await stories_of(factory, "Side Jobs"))[0][3] == "J.D. Robb"


@pytest.mark.ac("013/AC-15")
async def test_use_a_similar_name_on_a_row(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser,
    dresden: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    robb = await factory.author("J.D. Robb", alice)
    data = side_jobs(
        dresden, story_title_0="A", story_number_0="1.5", story_author_name_0="J DM Robb",
        story_title_1="B", story_number_1="2.5", story_author_name_1="J DM Robb",
    )  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert re.search(rf'name="use_story_author_0" value="{robb}">Use “J.D. Robb”', page.text)
    assert not field_error(page.text, "story_author_name_1")
    response = await member.post("/books/add", data={**data, "use_story_author_0": str(robb)})
    assert response.status_code == 303, response.text
    assert {s[3] for s in await stories_of(factory, "Side Jobs")} == {"J.D. Robb"}


@pytest.mark.ac("013/AC-15")
async def test_picked_and_existing_names_need_no_prompt(
    member: httpx.AsyncClient,
    factory: Factory,
    dresden: dict[str, uuid.UUID],
) -> None:
    data = side_jobs(
        dresden, story_title_0="A", story_number_0="1", story_author_name_0="ann other",
        story_series_name_0="Other Series", story_series_id_0=str(dresden["other"]),
    )  # fmt: skip
    response = await member.post("/books/add", data=data)
    assert response.status_code == 303, response.text
    assert await stories_of(factory, "Side Jobs") == [("A", "Other Series", 1, "Ann Other")]


async def test_stale_ids_on_a_row_fall_back_to_the_typed_name(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    """A picked or "Use …" id that was deleted meanwhile: the typed name is checked again."""
    gone = str(uuid.uuid4())
    data = side_jobs(
        dresden, story_title_0="A", story_number_0="1", story_author_name_0="Zed Writer",
        story_author_id_0=gone, use_story_author_0=gone,
    )  # fmt: skip
    page = await member.post("/books/add", data=data)
    assert page.status_code == 409
    assert field_error(page.text, "story_author_name_0") == "Story 1: " + PROMPT.format(
        "Zed Writer"
    )
    assert field_value(page.text, "story_author_id_0") == ""
