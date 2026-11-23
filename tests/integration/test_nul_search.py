"""Bead books-7bq: a NUL character in any search is ignored, not a server error.

PostgreSQL text cannot hold NUL, so every search parameter drops it before a query.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture(autouse=True)
async def _hobbit(factory: Factory, alice: TestUser) -> None:
    tolkien = await factory.author("J.R.R. Tolkien", alice)
    book = await factory.book("The Hobbit", alice, author_ids=[tolkien])
    await factory.entry(alice, book)


@pytest.mark.parametrize(
    "path",
    [
        "/?q=Hob%00bit",
        "/catalog?q=Hob%00bit",
        "/suggest/books?q=Hob%00bit",
        "/suggest/authors?q=Tol%00kien",
        "/suggest/series?q=a%00b",
        "/suggest/stories?q=a%00b",
        "/api/v1/me/readings?q=Hob%00bit",
        "/api/v1/books?q=Hob%00bit",
        "/api/v1/authors?q=Tol%00kien",
        "/api/v1/series?q=a%00b",
    ],
)
async def test_nul_in_a_search_is_ignored(member: httpx.AsyncClient, path: str) -> None:
    response = await member.get(path)
    assert response.status_code == 200, response.text
    if "series" not in path and "stories" not in path:
        assert ("Hobbit" in response.text) or ("Tolkien" in response.text), path


@pytest.mark.parametrize("path", ["/api/v1/books?q=%00", "/api/v1/authors?q=%00%00"])
async def test_nul_only_type_ahead_is_empty(member: httpx.AsyncClient, path: str) -> None:
    assert (await member.get(path)).status_code == 422
