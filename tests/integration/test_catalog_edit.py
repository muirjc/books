"""T079: any member edits the shared catalog; edits are attributed (FR-009, AC-32)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import httpx
import pytest

from tests.conftest import Factory, signed_in


@pytest.mark.ac("001/AC-32")
async def test_edit_is_shared_and_attributed(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    book = await factory.book("The Hobit", alice)
    await factory.entry(alice, book)
    before = await factory.scalar("SELECT updated_at FROM book WHERE id = :id", id=book)
    ben_api = await signed_in(client_factory(), ben)
    response = await ben_api.patch(f"/api/v1/books/{book}", json={"title": "The Hobbit"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "The Hobbit"
    assert body["updated_by"]["display_name"] == "Ben"
    assert body["created_by"]["display_name"] == "Alice"
    assert datetime.fromisoformat(body["updated_at"]) > before
    alice_api = await signed_in(client_factory(), alice)
    listed = (await alice_api.get("/api/v1/me/readings")).json()
    assert listed["items"][0]["book"]["title"] == "The Hobbit"


@pytest.mark.ac("001/AC-20")
async def test_decimal_series_number(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    api = await signed_in(client_factory(), alice)
    series = await factory.series("Strike", alice)
    author = await factory.author("Robert Galbraith", alice)
    created = await api.post(
        "/api/v1/me/readings",
        json={
            "new_book": {
                "title": "Novella",
                "author_ids": [str(author)],
                "series_id": str(series),
                "series_number": "2.5",
            }
        },
    )
    assert created.status_code == 201
    assert created.json()["book"]["series_number"] == "2.5"
    book = created.json()["book"]["id"]
    patched = await api.patch(f"/api/v1/books/{book}", json={"series_number": "3.75"})
    assert patched.json()["series_number"] == "3.75"


async def test_author_order_and_same_titles(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    api = await signed_in(client_factory(), alice)
    first = await factory.author("First Author", alice)
    second = await factory.author("Second Author", alice)
    book = await factory.book("Collaboration", alice, author_ids=[first, second])
    swapped = await api.patch(
        f"/api/v1/books/{book}", json={"author_ids": [str(second), str(first)]}
    )
    assert [a["name"] for a in swapped.json()["authors"]] == ["Second Author", "First Author"]
    assert [a["position"] for a in swapped.json()["authors"]] == [1, 2]
    unknown = await api.patch(
        f"/api/v1/books/{book}", json={"author_ids": ["00000000-0000-4000-8000-000000000000"]}
    )
    assert unknown.status_code == 422
    # Two different books may share a title (edge case).
    await api.post(
        "/api/v1/me/readings",
        json={"new_book": {"title": "Collaboration", "author_ids": [str(second)]}},
    )
    assert await factory.scalar("SELECT count(*) FROM book WHERE title = 'Collaboration'") == 2


async def test_edit_series_and_author(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    api = await signed_in(client_factory(), alice)
    series = await factory.series("Discwrold", alice)
    author = await factory.author("Terry Pratchet", alice)
    renamed = await api.patch(f"/api/v1/series/{series}", json={"name": "Discworld"})
    assert renamed.json()["name"] == "Discworld"
    fixed = await api.patch(
        f"/api/v1/authors/{author}",
        json={"name": "Terry Pratchett", "sort_name": "Pratchett, Terry"},
    )
    assert (fixed.json()["name"], fixed.json()["sort_name"]) == (
        "Terry Pratchett",
        "Pratchett, Terry",
    )
    empty = await api.patch(f"/api/v1/authors/{author}", json={})
    assert empty.status_code == 422
