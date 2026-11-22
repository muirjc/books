"""Spec 009 T017 (AC-26, FR-012): the story endpoints match the committed contract."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.fixture
async def api(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), await factory.user("alice"))


@pytest.mark.ac("009/AC-26")
async def test_story_endpoints(api: httpx.AsyncClient) -> None:
    butcher = (await api.post("/api/v1/authors", json={"name": "Jim Butcher"})).json()["id"]
    dresden = (await api.post("/api/v1/series", json={"name": "The Dresden Files"})).json()["id"]
    added = await api.post(
        "/api/v1/me/readings", json={"new_book": {"title": "Side Jobs", "author_ids": [butcher]}}
    )
    side_jobs = added.json()["book"]["id"]
    added = await api.post(
        "/api/v1/me/readings", json={"new_book": {"title": "Brief Cases", "author_ids": [butcher]}}
    )
    brief_cases = added.json()["book"]["id"]

    new = {
        "title": "Restoration of Faith",
        "author_ids": [butcher],
        "series_id": dresden,
        "series_number": "1.5",
    }
    created = await api.post(f"/api/v1/books/{side_jobs}/stories", json=new)
    assert created.status_code == 201, created.text
    assert_matches_contract(created)
    story = created.json()
    assert story["series_number"] == "1.5"
    assert [b["title"] for b in story["books"]] == ["Side Jobs"]

    taken = await api.post(f"/api/v1/books/{brief_cases}/stories", json={**new, "title": "x"})
    assert taken.status_code == 409
    assert_matches_contract(taken)
    assert taken.json()["code"] == "story_number_taken"
    assert taken.json()["existing_id"] == story["id"]
    assert taken.json()["existing_label"] == "#1.5 Restoration of Faith"

    linked = await api.post(f"/api/v1/books/{brief_cases}/stories", json={"story_id": story["id"]})
    assert linked.status_code == 201
    assert_matches_contract(linked)
    again = await api.post(f"/api/v1/books/{brief_cases}/stories", json={"story_id": story["id"]})
    assert again.status_code == 200
    assert_matches_contract(again)

    both = await api.post(
        f"/api/v1/books/{brief_cases}/stories", json={**new, "story_id": story["id"]}
    )
    assert both.status_code == 422
    assert_matches_contract(both)
    missing = await api.post(f"/api/v1/books/{uuid.uuid4()}/stories", json=new)
    assert missing.status_code == 404
    assert_matches_contract(missing)

    listed = await api.get(f"/api/v1/books/{side_jobs}/stories")
    assert listed.status_code == 200
    assert_matches_contract(listed)
    assert [s["id"] for s in listed.json()] == [story["id"]]
    assert (await api.get(f"/api/v1/books/{uuid.uuid4()}/stories")).status_code == 404

    one = await api.get(f"/api/v1/stories/{story['id']}")
    assert one.status_code == 200
    assert_matches_contract(one)
    gone = await api.get(f"/api/v1/stories/{uuid.uuid4()}")
    assert gone.status_code == 404
    assert_matches_contract(gone)

    in_series = await api.get("/api/v1/stories", params={"series_id": dresden})
    assert in_series.status_code == 200
    assert_matches_contract(in_series)
    assert [s["title"] for s in in_series.json()] == ["Restoration of Faith"]
    assert (
        await api.get("/api/v1/stories", params={"series_id": str(uuid.uuid4())})
    ).status_code == 404

    patched = await api.patch(f"/api/v1/stories/{story['id']}", json={"title": "Restoration"})
    assert patched.status_code == 200
    assert_matches_contract(patched)
    assert patched.json()["title"] == "Restoration"
    empty = await api.patch(f"/api/v1/stories/{story['id']}", json={"series_number": None})
    assert empty.status_code == 422
    assert_matches_contract(empty)
    other = await api.post(
        f"/api/v1/books/{side_jobs}/stories", json={**new, "series_number": "2.5"}
    )
    clash = await api.patch(f"/api/v1/stories/{other.json()['id']}", json={"series_number": "1.5"})
    assert clash.status_code == 409
    assert_matches_contract(clash)

    removed = await api.delete(f"/api/v1/books/{side_jobs}/stories/{story['id']}")
    assert removed.status_code == 204
    assert_matches_contract(removed)
    not_in = await api.delete(f"/api/v1/books/{side_jobs}/stories/{story['id']}")
    assert not_in.status_code == 404
    assert_matches_contract(not_in)
    last = await api.delete(f"/api/v1/books/{brief_cases}/stories/{story['id']}")
    assert last.status_code == 204
    assert (await api.get(f"/api/v1/stories/{story['id']}")).status_code == 404
