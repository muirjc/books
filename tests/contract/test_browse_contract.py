"""T092: browsing parameters and the series view match contracts/openapi.yaml."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.mark.ac("001/AC-21")
@pytest.mark.ac("001/AC-22")
@pytest.mark.ac("001/AC-23")
async def test_browse(factory: Factory, client_factory: Callable[[], httpx.AsyncClient]) -> None:
    alice = await factory.user("alice")
    api = await signed_in(client_factory(), alice)
    author = await factory.author("Terry Pratchett", alice)
    series = await factory.series("Discworld", alice)
    book = await factory.book(
        "Mort", alice, author_ids=[author], series_id=series, series_number="4"
    )
    await factory.entry(alice, book)
    params = {
        "q": "mort",
        "author_id": str(author),
        "series_id": str(series),
        "status": "finished",
        "sort": "-series",
        "page": "1",
        "page_size": "10",
    }
    listed = await api.get("/api/v1/me/readings", params=params)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert_matches_contract(listed)
    too_big = await api.get("/api/v1/me/readings", params={"page_size": "500"})
    assert too_big.status_code == 422
    assert_matches_contract(too_big)
    view = await api.get(f"/api/v1/me/series/{series}")
    assert view.status_code == 200
    assert_matches_contract(view)
    missing = await api.get("/api/v1/me/series/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404
    assert_matches_contract(missing)
