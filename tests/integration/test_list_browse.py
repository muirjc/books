"""T091: sort, filter, search and the series view, only ever over the member's own list."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, signed_in


@pytest.fixture
async def world(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> dict[str, Any]:
    alice = await factory.user("alice")
    ben = await factory.user("ben")
    pratchett = await factory.author("Terry Pratchett", alice, sort_name="Pratchett, Terry")
    austen = await factory.author("Jane Austen", alice, sort_name="Austen, Jane")
    galbraith = await factory.author(
        "Robert Galbraith",
        alice,
        sort_name="Galbraith, Robert",
        is_pen_name=True,
        real_name="J.K. Rowling",
    )
    discworld = await factory.series("Discworld", alice)
    strike = await factory.series("Cormoran Strike", alice)
    books = {
        "mort": await factory.book(
            "Mort", alice, author_ids=[pratchett], series_id=discworld, series_number="4"
        ),
        "colour": await factory.book(
            "The Colour of Magic",
            alice,
            author_ids=[pratchett],
            series_id=discworld,
            series_number="1",
        ),
        "novella": await factory.book(
            "Troll Bridge", alice, author_ids=[pratchett], series_id=discworld, series_number="2.5"
        ),
        "extra": await factory.book(
            "A Discworld Extra", alice, author_ids=[pratchett], series_id=discworld
        ),
        "emma": await factory.book("Emma", alice, author_ids=[austen]),
        "cuckoo": await factory.book(
            "The Cuckoo's Calling",
            alice,
            author_ids=[galbraith],
            series_id=strike,
            series_number="1",
        ),
        "ben_only": await factory.book(
            "Equal Rites", ben, author_ids=[pratchett], series_id=discworld, series_number="3"
        ),
    }
    await factory.entry(alice, books["mort"], finished_on=date(2026, 3, 1))
    await factory.entry(alice, books["colour"], finished_on=date(2025, 1, 1))
    await factory.entry(alice, books["novella"], status="reading")
    await factory.entry(alice, books["extra"], status="want_to_read")
    await factory.entry(alice, books["emma"], finished_on=date(2026, 5, 1))
    await factory.entry(alice, books["cuckoo"], status="reading")
    await factory.entry(ben, books["ben_only"], notes="ben's notes")
    await factory.entry(ben, books["mort"], notes="ben on mort")
    return {
        "api": await signed_in(client_factory(), alice),
        "ben_api": await signed_in(client_factory(), ben),
        "pratchett": pratchett,
        "austen": austen,
        "discworld": discworld,
        "strike": strike,
    }


async def titles(api: httpx.AsyncClient, **params: Any) -> list[str]:
    response = await api.get("/api/v1/me/readings", params=params)
    assert response.status_code == 200, response.text
    assert "ben" not in response.text.lower()
    return [item["book"]["title"] for item in response.json()["items"]]


ALL = [
    "A Discworld Extra",
    "Emma",
    "Mort",
    "The Colour of Magic",
    "The Cuckoo's Calling",
    "Troll Bridge",
]


@pytest.mark.ac("001/AC-21")
async def test_sorts(world: dict[str, Any]) -> None:
    api = world["api"]
    assert await titles(api) == ALL
    assert await titles(api, sort="title") == ALL
    assert await titles(api, sort="-title") == list(reversed(ALL))
    # Author sort uses the first author's sort name: Austen, Galbraith, Pratchett.
    assert (await titles(api, sort="author"))[:2] == ["Emma", "The Cuckoo's Calling"]
    assert (await titles(api, sort="-author"))[-2:] == ["The Cuckoo's Calling", "Emma"]
    # Series sort: series name, then number (unnumbered last), books without a series last.
    assert await titles(api, sort="series") == [
        "The Cuckoo's Calling",
        "The Colour of Magic",
        "Troll Bridge",
        "Mort",
        "A Discworld Extra",
        "Emma",
    ]
    # Descending: series Z→A and highest number first; missing values stay last.
    assert await titles(api, sort="-series") == [
        "Mort",
        "Troll Bridge",
        "The Colour of Magic",
        "A Discworld Extra",
        "The Cuckoo's Calling",
        "Emma",
    ]
    assert (await titles(api, sort="finished_on"))[:3] == ["The Colour of Magic", "Mort", "Emma"]
    assert (await titles(api, sort="-finished_on"))[:3] == ["Emma", "Mort", "The Colour of Magic"]
    assert (await api.get("/api/v1/me/readings", params={"sort": "rating"})).status_code == 422


@pytest.mark.ac("001/AC-21")
async def test_filters(world: dict[str, Any]) -> None:
    api = world["api"]
    assert await titles(api, author_id=str(world["austen"])) == ["Emma"]
    pratchett = await titles(api, author_id=str(world["pratchett"]))
    assert pratchett == ["A Discworld Extra", "Mort", "The Colour of Magic", "Troll Bridge"]
    assert "Equal Rites" not in pratchett  # Ben's book in the same series and author
    assert await titles(api, series_id=str(world["strike"])) == ["The Cuckoo's Calling"]
    assert await titles(api, status="reading") == ["The Cuckoo's Calling", "Troll Bridge"]
    assert await titles(api, status="reading", series_id=str(world["discworld"])) == [
        "Troll Bridge"
    ]
    page = (await api.get("/api/v1/me/readings", params={"status": "finished"})).json()
    assert page["total"] == 3


@pytest.mark.ac("001/AC-23")
async def test_search(world: dict[str, Any]) -> None:
    api = world["api"]
    assert await titles(api, q="colour") == ["The Colour of Magic"]
    assert await titles(api, q="austen") == ["Emma"]
    assert await titles(api, q="rowling") == ["The Cuckoo's Calling"]  # real name
    assert await titles(api, q="strike") == ["The Cuckoo's Calling"]  # series name
    assert "Equal Rites" not in await titles(api, q="equal")
    assert await titles(api, q="100%") == []


@pytest.mark.ac("001/AC-22")
@pytest.mark.ac("001/AC-20")
async def test_series_view_order(world: dict[str, Any]) -> None:
    response = await world["api"].get(f"/api/v1/me/series/{world['discworld']}")
    assert response.status_code == 200
    body = response.json()
    assert body["series"]["name"] == "Discworld"
    assert [e["book"]["title"] for e in body["entries"]] == [
        "The Colour of Magic",
        "Troll Bridge",
        "Mort",
        "A Discworld Extra",
    ]
    assert [e["book"]["series_number"] for e in body["entries"]] == ["1", "2.5", "4", None]


@pytest.mark.ac("001/AC-22")
async def test_series_view_is_private(world: dict[str, Any]) -> None:
    """Cross-user (Principle I): Ben owns entries in the same series."""
    alice_view = (await world["api"].get(f"/api/v1/me/series/{world['discworld']}")).json()
    assert "Equal Rites" not in [e["book"]["title"] for e in alice_view["entries"]]
    assert "ben" not in str(alice_view).lower()
    ben_view = (await world["ben_api"].get(f"/api/v1/me/series/{world['discworld']}")).json()
    assert [e["book"]["title"] for e in ben_view["entries"]] == ["Equal Rites", "Mort"]
    assert all(e["notes"] and "ben" in e["notes"] for e in ben_view["entries"])


async def test_series_view_empty_and_unknown(world: dict[str, Any], factory: Factory) -> None:
    lonely = await factory.series("Nobody Reads This", await factory.user("carol"))
    empty = await world["api"].get(f"/api/v1/me/series/{lonely}")
    assert empty.status_code == 200
    assert empty.json()["entries"] == []
    assert (await world["api"].get(f"/api/v1/me/series/{uuid.uuid4()}")).status_code == 404
