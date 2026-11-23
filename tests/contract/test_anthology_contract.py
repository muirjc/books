"""Spec 013 User Story 4: a new book's stories in the create-entry request."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in
from tests.contract.conftest import assert_matches_contract

URL = "/api/v1/me/readings"


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def api(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture
async def ids(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    return {
        "jim": await factory.author("Jim Butcher", alice),
        "ann": await factory.author("Ann Other", alice),
        "dresden": await factory.series("The Dresden Files", alice),
        "other": await factory.series("Other Series", alice),
    }


def body(ids: dict[str, uuid.UUID], stories: Any, *, series: bool = True) -> dict[str, Any]:
    new_book: dict[str, Any] = {"title": "Side Jobs", "author_ids": [str(ids["jim"])]}
    if series:
        new_book["series_id"] = str(ids["dresden"])
    return {"new_book": new_book, "status": "finished", "stories": stories}


async def counts(factory: Factory) -> tuple[int, ...]:
    return tuple(
        [int(await factory.scalar(f"SELECT count(*) FROM {t}"))
         for t in ("book", "story", "book_story", "reading_entry")]
    )  # fmt: skip


@pytest.mark.ac("013/AC-22")
async def test_create_with_stories(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser, ids: dict[str, uuid.UUID]
) -> None:
    other_book = await factory.book("Elsewhere", alice, author_ids=[ids["jim"]])
    existing = await factory.story(
        "Old Tale", alice, series_id=ids["dresden"], series_number="9.5",
        author_ids=[ids["jim"]], book_ids=[other_book],
    )  # fmt: skip
    response = await api.post(URL, json=body(ids, [
        {"title": "Restoration of Faith", "series_number": "1.5"},
        {"title": "Other Tale", "series_number": "3", "series_id": str(ids["other"]),
         "author_ids": [str(ids["ann"])]},
        {"story_id": str(existing)},
    ]))  # fmt: skip
    assert response.status_code == 201, response.text
    assert_matches_contract(response)
    book_id = response.json()["book"]["id"]
    listed = await api.get(f"/api/v1/books/{book_id}/stories")
    assert listed.status_code == 200
    assert_matches_contract(listed)
    by_title = {s["title"]: s for s in listed.json()}
    assert set(by_title) == {"Restoration of Faith", "Other Tale", "Old Tale"}
    faith = by_title["Restoration of Faith"]
    assert faith["series"]["id"] == str(ids["dresden"]) and faith["series_number"] == "1.5"
    assert [a["id"] for a in faith["authors"]] == [str(ids["jim"])]
    assert [a["id"] for a in by_title["Other Tale"]["authors"]] == [str(ids["ann"])]
    assert by_title["Old Tale"]["id"] == str(existing)
    assert await factory.scalar("SELECT count(*) FROM story") == 3


@pytest.mark.ac("013/AC-23")
@pytest.mark.ac("013/AC-24")
@pytest.mark.ac("013/AC-26")
@pytest.mark.parametrize(
    ("case", "where"),
    [
        ("too_many", "stories"),
        ("no_title", "stories.0"),
        ("no_number", "stories.0"),
        ("both", "stories.0"),
        ("no_series", "stories"),
        ("same_pair", "stories"),
        ("same_story", "stories"),
        ("with_book_id", "stories"),
    ],
)
async def test_refused_items(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser, ids: dict[str, uuid.UUID],
    case: str, where: str,
) -> None:  # fmt: skip
    one = {"title": "A", "series_number": "1.5"}
    sid = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "too_many": body(ids, [{"title": f"S{i}", "series_number": str(i)} for i in range(51)]),
        "no_title": body(ids, [{"series_number": "1.5"}]),
        "no_number": body(ids, [{"title": "A"}]),
        "both": body(ids, [{**one, "story_id": sid}]),
        "no_series": body(ids, [one], series=False),
        "same_pair": body(ids, [one, {"title": "B", "series_number": "1.50",
                                      "series_id": str(ids["dresden"])}]),
        "same_story": body(ids, [{"story_id": sid}, {"story_id": sid}]),
        "with_book_id": {"book_id": str(await factory.book("X", alice)), "stories": [one]},
    }[case]  # fmt: skip
    before = await counts(factory)
    response = await api.post(URL, json=payload)
    assert response.status_code == 422, response.text
    assert_matches_contract(response)
    locations = [e["field"] for e in response.json()["errors"]]
    assert any(loc.startswith(where) for loc in locations), locations
    assert await counts(factory) == before


@pytest.mark.ac("013/AC-25")
async def test_a_taken_number_is_a_conflict(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser, ids: dict[str, uuid.UUID]
) -> None:
    other_book = await factory.book("Elsewhere", alice, author_ids=[ids["jim"]])
    existing = await factory.story(
        "Publicity", alice, series_id=ids["dresden"], series_number="2.5",
        author_ids=[ids["jim"]], book_ids=[other_book],
    )  # fmt: skip
    before = await counts(factory)
    response = await api.post(URL, json=body(ids, [
        {"title": "A", "series_number": "1.5"}, {"title": "B", "series_number": "2.5"},
    ]))  # fmt: skip
    assert response.status_code == 409, response.text
    assert_matches_contract(response)
    problem = response.json()
    assert problem["code"] == "story_number_taken" and problem["existing_id"] == str(existing)
    assert await counts(factory) == before


async def test_a_deleted_story_id_is_refused(
    api: httpx.AsyncClient, factory: Factory, ids: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    response = await api.post(URL, json=body(ids, [{"story_id": str(uuid.uuid4())}]))
    assert response.status_code == 422, response.text
    assert_matches_contract(response)
    assert await counts(factory) == before


@pytest.mark.ac("013/AC-27")
async def test_without_stories_as_before(
    api: httpx.AsyncClient, factory: Factory, ids: dict[str, uuid.UUID]
) -> None:
    payload = body(ids, None)
    del payload["stories"]
    response = await api.post(URL, json=payload)
    assert response.status_code == 201
    assert_matches_contract(response)
    assert await factory.scalar("SELECT count(*) FROM story") == 0
    empty = await api.post(URL, json={**body(ids, []), "new_book": {
        "title": "Empty", "author_ids": [str(ids["jim"])]}})  # fmt: skip
    assert empty.status_code == 201


async def test_an_invalid_new_book_gives_no_stories_error(
    api: httpx.AsyncClient, ids: dict[str, uuid.UUID]
) -> None:
    """PR #33 review: only the new book's own error is reported."""
    payload = body(ids, [{"title": "X", "series_number": "1"}])
    payload["new_book"]["title"] = ""
    response = await api.post(URL, json=payload)
    assert response.status_code == 422
    fields = [e["field"] for e in response.json()["errors"]]
    assert fields and all(not f.startswith("stories") for f in fields), fields
