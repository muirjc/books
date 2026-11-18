"""T093: list controls and the series page (FR-021 – FR-023)."""

from __future__ import annotations

import re
from collections.abc import Callable
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
    pratchett = await factory.author("Terry Pratchett", alice)
    discworld = await factory.series("Discworld", alice)
    mort = await factory.book(
        "Mort", alice, author_ids=[pratchett], series_id=discworld, series_number="4"
    )
    colour = await factory.book(
        "The Colour of Magic", alice, author_ids=[pratchett], series_id=discworld, series_number="1"
    )
    emma = await factory.book("Emma", alice)
    ben_book = await factory.book(
        "Equal Rites", ben, author_ids=[pratchett], series_id=discworld, series_number="3"
    )
    await factory.entry(alice, mort)
    await factory.entry(alice, colour, status="reading")
    await factory.entry(alice, emma)
    await factory.entry(ben, ben_book, notes="ben secret")
    return {
        "page": await signed_in(client_factory(), alice),
        "discworld": discworld,
        "pratchett": pratchett,
    }


@pytest.mark.ac("001/AC-21")
async def test_controls_are_labelled_and_work_without_js(world: dict[str, Any]) -> None:
    page = world["page"]
    html = (await page.get("/")).text
    for field in ("q", "sort", "status", "author_id", "series_id"):
        assert re.search(rf'<label for="{field}"', html), field
    form = re.search(r'<form[^>]*role="search"[^>]*>', html)
    assert form and 'method="get"' in form.group(0)
    assert 'hx-get="/"' in form.group(0) and 'hx-push-url="true"' in form.group(0)
    assert re.search(
        r'<option value="{}"[^>]*>Terry Pratchett</option>'.format(world["pratchett"]), html
    )
    filtered = await page.get("/", params={"status": "reading"})
    assert "The Colour of Magic" in filtered.text
    assert "Emma" not in filtered.text.split('id="reading-list"')[1]
    assert re.search(r'<option value="reading" selected', filtered.text)


@pytest.mark.ac("001/AC-23")
async def test_search_and_htmx_fragment(world: dict[str, Any]) -> None:
    page = world["page"]
    fragment = await page.get("/", params={"q": "colour"}, headers={"HX-Request": "true"})
    assert fragment.status_code == 200
    assert "<html" not in fragment.text
    assert "The Colour of Magic" in fragment.text and "Mort" not in fragment.text
    sorted_page = await page.get("/", params={"sort": "-title"})
    body = sorted_page.text.split('id="reading-list"')[1]
    assert body.index("The Colour of Magic") < body.index("Mort") < body.index("Emma")


@pytest.mark.ac("001/AC-22")
async def test_series_page(world: dict[str, Any]) -> None:
    page = world["page"]
    listing = (await page.get("/")).text
    assert f'href="/series/{world["discworld"]}"' in listing
    series = await page.get(f"/series/{world['discworld']}")
    assert series.status_code == 200
    assert "<h1>Discworld</h1>" in series.text
    text = series.text
    assert text.index("The Colour of Magic") < text.index("Mort")
    # Cross-user (Principle I): Ben's entry in the same series never appears.
    assert "Equal Rites" not in text and "ben secret" not in text
    filtered = await page.get("/", params={"series_id": str(world["discworld"])})
    assert "Equal Rites" not in filtered.text
    assert (await page.get("/series/00000000-0000-4000-8000-000000000000")).status_code == 404


async def test_invalid_filters_are_ignored(world: dict[str, Any]) -> None:
    response = await world["page"].get(
        "/", params={"sort": "bogus", "author_id": "nope", "status": "lost", "page": "x"}
    )
    assert response.status_code == 200
    assert "Mort" in response.text
