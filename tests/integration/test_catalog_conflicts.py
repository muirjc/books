"""T077: uniqueness conflicts on catalog **edits** (creates are covered in T049)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def api(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.mark.ac("001/AC-16")
async def test_rename_author_or_series_to_existing(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    existing = await factory.author("Terry Pratchett", alice)
    other = await factory.author("Neil Gaiman", alice)
    response = await api.patch(f"/api/v1/authors/{other}", json={"name": "terry pratchett"})
    assert response.status_code == 409
    assert response.json()["code"] == "author_exists"
    assert response.json()["existing_id"] == str(existing)
    assert await factory.scalar("SELECT name FROM author WHERE id = :id", id=other) == "Neil Gaiman"
    discworld = await factory.series("Discworld", alice)
    sandman = await factory.series("Sandman", alice)
    renamed = await api.patch(f"/api/v1/series/{sandman}", json={"name": "DISCWORLD"})
    assert renamed.status_code == 409
    assert renamed.json()["code"] == "series_exists"
    assert renamed.json()["existing_id"] == str(discworld)


@pytest.mark.ac("001/AC-19")
async def test_patch_to_taken_series_number(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Discworld", alice)
    mort = await factory.book("Mort", alice, series_id=series, series_number="4")
    other = await factory.book("Sourcery", alice, series_id=series, series_number="5")
    response = await api.patch(f"/api/v1/books/{other}", json={"series_number": "4"})
    assert response.status_code == 409
    body = response.json()
    assert (body["code"], body["existing_id"], body["existing_label"]) == (
        "series_number_taken",
        str(mort),
        "Mort",
    )
    assert await factory.scalar("SELECT series_number FROM book WHERE id = :id", id=other) == 5


@pytest.mark.ac("001/AC-30")
async def test_patch_isbn(api: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    holder = await factory.book("Holder", alice, isbn_13="9780306406157")
    other = await factory.book("Other", alice)
    invalid = await api.patch(f"/api/v1/books/{other}", json={"isbn_13": "9780306406158"})
    assert invalid.status_code == 422
    taken = await api.patch(f"/api/v1/books/{other}", json={"isbn_13": "978-0-306-40615-7"})
    assert taken.status_code == 409
    assert taken.json()["code"] == "isbn_exists"
    assert taken.json()["existing_id"] == str(holder)
    assert await factory.scalar("SELECT isbn_13 FROM book WHERE id = :id", id=other) is None


@pytest.mark.ac("001/AC-06")
async def test_patch_number_without_series(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Loose", alice)
    response = await api.patch(f"/api/v1/books/{book}", json={"series_number": "2"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "series_number"


async def test_removing_series_clears_number(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Discworld", alice)
    book = await factory.book("Mort", alice, series_id=series, series_number="4")
    response = await api.patch(f"/api/v1/books/{book}", json={"series_id": None})
    assert response.status_code == 200
    assert response.json()["series"] is None
    assert response.json()["series_number"] is None


async def test_unknown_rows(api: httpx.AsyncClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    for path, body in (
        (f"/api/v1/books/{missing}", {"title": "x"}),
        (f"/api/v1/authors/{missing}", {"name": "x"}),
        (f"/api/v1/series/{missing}", {"name": "x"}),
    ):
        assert (await api.patch(path, json=body)).status_code == 404, path
