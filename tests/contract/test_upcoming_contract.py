"""Spec 007 T025 (FR-008): release dates, Pre-ordered and the upcoming filter in the JSON
API match the committed contract."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
async def api(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), await factory.user("alice"))


@pytest.fixture
async def other_api(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), await factory.user("ben"))


async def _add(api: httpx.AsyncClient, author: str, title: str, **extra: Any) -> httpx.Response:
    book: dict[str, Any] = {"title": title, "author_ids": [author]}
    if "release_date" in extra:
        book["release_date"] = extra.pop("release_date")
    added = await api.post(
        "/api/v1/me/readings", json={"new_book": book, "status": "want_to_read", **extra}
    )
    assert added.status_code == 201, added.text
    assert_matches_contract(added)
    return added


@pytest.mark.ac("007/AC-01")
@pytest.mark.ac("007/AC-07")
async def test_release_date_and_pre_ordered_round_trip(api: httpx.AsyncClient) -> None:
    author = (await api.post("/api/v1/authors", json={"name": "Jim Butcher"})).json()["id"]
    added = await _add(api, author, "Twelve Months", release_date="2027-03-03", pre_ordered=True)
    body = added.json()
    assert body["book"]["release_date"] == "2027-03-03"
    assert body["pre_ordered"] is True
    plain = (await _add(api, author, "Skin Game")).json()
    assert plain["book"]["release_date"] is None and plain["pre_ordered"] is False

    changed = await api.patch(f"/api/v1/me/readings/{body['id']}", json={"pre_ordered": False})
    assert changed.status_code == 200
    assert_matches_contract(changed)
    assert changed.json()["pre_ordered"] is False
    kept = await api.patch(f"/api/v1/me/readings/{body['id']}", json={"notes": "soon"})
    assert kept.json()["pre_ordered"] is False

    book_id = body["book"]["id"]
    moved = await api.patch(f"/api/v1/books/{book_id}", json={"release_date": "2027-04-01"})
    assert moved.status_code == 200
    assert_matches_contract(moved)
    assert moved.json()["release_date"] == "2027-04-01"
    cleared = await api.patch(f"/api/v1/books/{book_id}", json={"release_date": None})
    assert cleared.json()["release_date"] is None
    read = await api.get(f"/api/v1/books/{book_id}")
    assert_matches_contract(read)


@pytest.mark.ac("007/AC-03")
async def test_bad_release_date_is_refused(api: httpx.AsyncClient) -> None:
    author = (await api.post("/api/v1/authors", json={"name": "Jim Butcher"})).json()["id"]
    bad = await api.post(
        "/api/v1/me/readings",
        json={"new_book": {"title": "X", "author_ids": [author], "release_date": "2027-02-30"}},
    )
    assert bad.status_code == 422
    assert_matches_contract(bad)


@pytest.mark.ac("007/AC-10")
@pytest.mark.ac("007/AC-09")
async def test_upcoming_filter(api: httpx.AsyncClient, other_api: httpx.AsyncClient) -> None:
    author = (await api.post("/api/v1/authors", json={"name": "Jim Butcher"})).json()["id"]
    await _add(api, author, "Mirror Mirror", release_date="2027-06-01")
    await _add(api, author, "Twelve Months", release_date="2027-03-03", pre_ordered=True)
    await _add(api, author, "Storm Front", release_date="2000-04-01")
    await _add(api, author, "Out Today", release_date="2026-11-21")
    await _add(other_api, author, "Ben's Book", release_date="2027-01-01", pre_ordered=True)

    upcoming = await api.get("/api/v1/me/readings", params={"upcoming": "true", "sort": "-title"})
    assert upcoming.status_code == 200
    assert_matches_contract(upcoming)
    titles = [item["book"]["title"] for item in upcoming.json()["items"]]
    assert titles == ["Twelve Months", "Mirror Mirror"]
    assert upcoming.json()["total"] == 2
    everything = await api.get("/api/v1/me/readings")
    assert everything.json()["total"] == 4
    assert all(item["book"]["title"] != "Ben's Book" for item in everything.json()["items"])
