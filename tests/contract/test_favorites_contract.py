"""Spec 011 (AC-10, AC-13, AC-16): the favorite-author endpoints match the contract."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.mark.ac("011/AC-10")
@pytest.mark.ac("011/AC-13")
@pytest.mark.ac("011/AC-16")
async def test_favorite_endpoints(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    api = await signed_in(client_factory(), await factory.user("alice"))
    other = await signed_in(client_factory(), await factory.user("ben"))
    butcher = (await api.post("/api/v1/authors", json={"name": "Jim Butcher"})).json()["id"]
    austen = (await api.post("/api/v1/authors", json={"name": "Jane Austen"})).json()["id"]
    lonely = (await api.post("/api/v1/authors", json={"name": "Nobody Yet"})).json()["id"]
    for title, author in (("Storm Front", butcher), ("Emma", austen)):
        await api.post(
            "/api/v1/me/readings", json={"new_book": {"title": title, "author_ids": [author]}}
        )

    empty = await api.get("/api/v1/me/favorite-authors")
    assert empty.status_code == 200 and empty.json() == []
    assert_matches_contract(empty)
    for author in (butcher, lonely, butcher):  # the repeat is harmless
        added = await api.put(f"/api/v1/me/favorite-authors/{author}")
        assert added.status_code == 204, added.text
        assert_matches_contract(added)
    listed = await api.get("/api/v1/me/favorite-authors")
    assert [a["name"] for a in listed.json()] == ["Jim Butcher", "Nobody Yet"]  # sort names
    assert_matches_contract(listed)
    assert (await other.get("/api/v1/me/favorite-authors")).json() == []

    mine = await api.get("/api/v1/me/readings", params={"favorite_authors": "true"})
    assert mine.status_code == 200
    assert_matches_contract(mine)
    assert [e["book"]["title"] for e in mine.json()["items"]] == ["Storm Front"]
    bens = await other.get("/api/v1/me/readings", params={"favorite_authors": "true"})
    assert bens.json()["items"] == []

    blocked = await other.delete(f"/api/v1/authors/{lonely}")
    assert blocked.status_code == 409
    assert_matches_contract(blocked)
    assert blocked.json()["code"] == "author_is_favorite"
    assert "alice" not in blocked.text.lower()

    unknown = await api.put(f"/api/v1/me/favorite-authors/{uuid.uuid4()}")
    assert unknown.status_code == 404
    assert_matches_contract(unknown)
    removed = await api.delete(f"/api/v1/me/favorite-authors/{lonely}")
    assert removed.status_code == 204
    assert_matches_contract(removed)
    again = await api.delete(f"/api/v1/me/favorite-authors/{lonely}")
    assert again.status_code == 204
    gone = await api.delete(f"/api/v1/me/favorite-authors/{uuid.uuid4()}")
    assert gone.status_code == 404
    assert (await other.delete(f"/api/v1/authors/{lonely}")).status_code == 204
