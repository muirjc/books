"""T081: catalog search and edit endpoints match contracts/openapi.yaml."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.mark.ac("001/AC-15")
@pytest.mark.ac("001/AC-16")
@pytest.mark.ac("001/AC-19")
@pytest.mark.ac("001/AC-30")
@pytest.mark.ac("001/AC-32")
async def test_catalog_endpoints(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    api = await signed_in(client_factory(), alice)
    author = await factory.author("Terry Pratchett", alice, is_pen_name=True, real_name="TP")
    other_author = await factory.author("Neil Gaiman", alice)
    series = await factory.series("Discworld", alice)
    await factory.book(
        "Mort",
        alice,
        author_ids=[author],
        series_id=series,
        series_number="4",
        isbn_13="9780306406157",
    )
    book = await factory.book(
        "Good Omens", alice, author_ids=[author, other_author], series_id=series, series_number="5"
    )

    for path in ("/api/v1/books?q=mort", "/api/v1/authors?q=terry", "/api/v1/series?q=disc"):
        response = await api.get(path)
        assert response.status_code == 200, path
        assert_matches_contract(response)

    for path, body in (
        (f"/api/v1/books/{book}", {"title": "Good Omens (2006)"}),
        (f"/api/v1/authors/{other_author}", {"sort_name": "Gaiman, Neil"}),
        (f"/api/v1/series/{series}", {"name": "The Discworld"}),
    ):
        response = await api.patch(path, json=body)
        assert response.status_code == 200, path
        assert_matches_contract(response)

    conflicts = [
        await api.patch(f"/api/v1/books/{book}", json={"series_number": "4"}),
        await api.patch(f"/api/v1/books/{book}", json={"isbn_13": "9780306406157"}),
        await api.patch(f"/api/v1/authors/{other_author}", json={"name": "terry pratchett"}),
    ]
    for response in conflicts:
        assert response.status_code == 409
        assert_matches_contract(response)

    invalid = await api.patch(f"/api/v1/books/{book}", json={"isbn_13": "123"})
    assert invalid.status_code == 422
    assert_matches_contract(invalid)
