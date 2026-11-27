"""Spec 019 AC-13: stories without a series through the JSON API, against the committed
contract (specs/019-optional-story-series/contracts/api-stories.md)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.fixture
async def api(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), await factory.user("alice"))


async def _setup(api: httpx.AsyncClient) -> dict[str, Any]:
    jackson = (await api.post("/api/v1/authors", json={"name": "Shirley Jackson"})).json()["id"]
    tales = (await api.post("/api/v1/series", json={"name": "Tales"})).json()["id"]
    added = await api.post(
        "/api/v1/me/readings", json={"new_book": {"title": "Collection", "author_ids": [jackson]}}
    )
    return {"jackson": jackson, "tales": tales, "book": added.json()["book"]["id"]}


@pytest.mark.ac("019/AC-13")
async def test_story_without_a_series(api: httpx.AsyncClient) -> None:
    w = await _setup(api)
    url = f"/api/v1/books/{w['book']}/stories"
    numbered_story = {"title": "Numbered", "author_ids": [w["jackson"]],
                      "series_id": w["tales"], "series_number": "1"}  # fmt: skip
    numbered = await api.post(url, json=numbered_story)
    assert numbered.status_code == 201, numbered.text
    plain = await api.post(url, json={"title": "The Lottery", "author_ids": [w["jackson"]]})
    assert plain.status_code == 201, plain.text
    assert_matches_contract(plain)
    story = plain.json()
    assert story["series"] is None and story["series_number"] is None
    for half in ({"series_id": w["tales"]}, {"series_number": "2"}):
        refused = await api.post(url, json={"title": "Half", "author_ids": [w["jackson"]], **half})
        assert refused.status_code == 422, (half, refused.text)
        assert_matches_contract(refused)

    listed = await api.get(url)
    assert_matches_contract(listed)
    assert [s["title"] for s in listed.json()] == ["Numbered", "The Lottery"]
    in_series = await api.get("/api/v1/stories", params={"series_id": w["tales"]})
    assert [s["title"] for s in in_series.json()] == ["Numbered"]

    sid = numbered.json()["id"]
    cleared = await api.patch(f"/api/v1/stories/{sid}",
                              json={"series_id": None, "series_number": None})  # fmt: skip
    assert cleared.status_code == 200, cleared.text
    assert_matches_contract(cleared)
    assert cleared.json()["series"] is None
    for half in ({"series_id": w["tales"]}, {"series_number": "3"}):
        refused = await api.patch(f"/api/v1/stories/{sid}", json=half)
        assert refused.status_code == 422, (half, refused.text)
    given = await api.patch(f"/api/v1/stories/{sid}",
                            json={"series_id": w["tales"], "series_number": "5"})  # fmt: skip
    assert given.status_code == 200 and given.json()["series_number"] == "5"
    renumbered = await api.patch(f"/api/v1/stories/{sid}", json={"series_number": "6"})
    assert renumbered.status_code == 200 and renumbered.json()["series"]["id"] == w["tales"]


@pytest.mark.ac("019/AC-13")
async def test_entry_stories_without_a_series(api: httpx.AsyncClient) -> None:
    w = await _setup(api)

    async def create(stories: list[dict[str, Any]], **book: Any) -> httpx.Response:
        return await api.post("/api/v1/me/readings", json={
            "new_book": {"title": "Anthology", "author_ids": [w["jackson"]], **book},
            "stories": stories,
        })  # fmt: skip

    made = await create([{"title": "A"}, {"title": "B"}])
    assert made.status_code == 201, made.text
    assert_matches_contract(made)
    book = made.json()["book"]["id"]
    stories = (await api.get(f"/api/v1/books/{book}/stories")).json()
    assert [(s["title"], s["series"]) for s in stories] == [("A", None), ("B", None)]

    takes_book = await create([{"title": "C", "series_number": "1"}, {"title": "D"}],
                              series_id=w["tales"], series_number="9")  # fmt: skip
    assert takes_book.status_code == 201, takes_book.text
    in_book = (await api.get(f"/api/v1/books/{takes_book.json()['book']['id']}/stories")).json()
    assert [(s["title"], s["series"] and s["series"]["id"]) for s in in_book] == [
        ("C", w["tales"]), ("D", None),
    ]  # fmt: skip
    for bad in ([{"title": "E", "series_number": "1"}],           # no series anywhere
                [{"title": "F", "series_id": w["tales"]}]):  # a series, no number  # fmt: skip
        refused = await create(bad)
        assert refused.status_code == 422, (bad, refused.text)
        assert_matches_contract(refused)
