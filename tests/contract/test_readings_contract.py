"""T050: reading-list and catalog-create endpoints match contracts/openapi.yaml."""

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


@pytest.mark.ac("001/AC-03")
@pytest.mark.ac("001/AC-05")
@pytest.mark.ac("001/AC-07")
async def test_reading_list_lifecycle(api: httpx.AsyncClient) -> None:
    author = await api.post("/api/v1/authors", json={"name": "Frank Herbert"})
    assert author.status_code == 201
    assert_matches_contract(author)
    series = await api.post("/api/v1/series", json={"name": "Dune Chronicles"})
    assert series.status_code == 201
    assert_matches_contract(series)

    added = await api.post(
        "/api/v1/me/readings",
        json={
            "new_book": {
                "title": "Dune",
                "author_ids": [author.json()["id"]],
                "series_id": series.json()["id"],
                "series_number": "1",
                "isbn_13": "9780306406157",
            },
            "notes": "First read",
        },
    )
    assert added.status_code == 201
    assert_matches_contract(added)
    entry_id = added.json()["id"]
    book_id = added.json()["book"]["id"]
    assert added.json()["book"]["series_number"] == "1"

    for path in (
        f"/api/v1/authors/{author.json()['id']}",
        f"/api/v1/series/{series.json()['id']}",
        f"/api/v1/books/{book_id}",
        "/api/v1/me/readings",
        f"/api/v1/me/readings/{entry_id}",
    ):
        response = await api.get(path)
        assert response.status_code == 200, path
        assert_matches_contract(response)

    duplicate = await api.post("/api/v1/me/readings", json={"book_id": book_id})
    assert duplicate.status_code == 409
    assert_matches_contract(duplicate)

    invalid = await api.post("/api/v1/me/readings", json={"book_id": "not-a-uuid"})
    assert invalid.status_code == 422
    assert_matches_contract(invalid)

    patched = await api.patch(f"/api/v1/me/readings/{entry_id}", json={"status": "reading"})
    assert patched.status_code == 200
    assert_matches_contract(patched)

    again = await api.post(f"/api/v1/me/readings/{entry_id}/read-again")
    assert again.status_code == 200
    assert_matches_contract(again)

    removed = await api.delete(f"/api/v1/me/readings/{entry_id}")
    assert removed.status_code == 204
    assert_matches_contract(removed)

    for path in (
        f"/api/v1/me/readings/{entry_id}",
        f"/api/v1/books/{uuid.uuid4()}",
        f"/api/v1/authors/{uuid.uuid4()}",
        f"/api/v1/series/{uuid.uuid4()}",
    ):
        missing = await api.get(path)
        assert missing.status_code == 404, path
        assert_matches_contract(missing)


async def test_catalog_conflict_shape(api: httpx.AsyncClient) -> None:
    await api.post("/api/v1/authors", json={"name": "Frank Herbert"})
    conflict = await api.post("/api/v1/authors", json={"name": "Frank Herbert"})
    assert conflict.status_code == 409
    assert_matches_contract(conflict)


async def test_unauthenticated(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/me/readings")
    assert response.status_code == 401
    assert_matches_contract(response)
