"""Spec 008 T006 (FR-004, FR-005): DELETE /authors/{id} matches the committed contract."""

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


@pytest.mark.ac("008/AC-04")
@pytest.mark.ac("008/AC-06")
@pytest.mark.ac("008/AC-08")
async def test_delete_author(api: httpx.AsyncClient) -> None:
    typo = (await api.post("/api/v1/authors", json={"name": "J DM Robb"})).json()["id"]
    robb = (await api.post("/api/v1/authors", json={"name": "J.D. Robb"})).json()["id"]
    added = await api.post(
        "/api/v1/me/readings", json={"new_book": {"title": "Naked in Death", "author_ids": [robb]}}
    )
    assert added.status_code == 201

    deleted = await api.delete(f"/api/v1/authors/{typo}")
    assert deleted.status_code == 204
    assert_matches_contract(deleted)
    again = await api.delete(f"/api/v1/authors/{typo}")
    assert again.status_code == 404
    assert_matches_contract(again)
    unknown = await api.delete(f"/api/v1/authors/{uuid.uuid4()}")
    assert unknown.status_code == 404

    kept = await api.delete(f"/api/v1/authors/{robb}")
    assert kept.status_code == 409
    assert_matches_contract(kept)
    assert kept.json()["title"] == "This author has books"
    assert (await api.get(f"/api/v1/authors/{robb}")).status_code == 200
