"""Bead books-7bq: a NUL character in any search is dropped, not a server error.

PostgreSQL text cannot hold NUL, so every search parameter drops it before a query, and the
rest of the text still filters.
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
async def _books(factory: Factory, alice: TestUser) -> None:
    tolkien = await factory.author("J.R.R. Tolkien", alice)
    pratchett = await factory.author("Terry Pratchett", alice)
    middle = await factory.series("Middle-earth", alice)
    disc = await factory.series("Discworld", alice)
    hobbit = await factory.book("The Hobbit", alice, author_ids=[tolkien], series_id=middle)
    mort = await factory.book("Mort", alice, author_ids=[pratchett], series_id=disc)
    await factory.story(
        "Leaf by Niggle", alice, series_id=middle, series_number="9",
        author_ids=[tolkien], book_ids=[hobbit],
    )  # fmt: skip
    await factory.story(
        "Troll Bridge", alice, series_id=disc, series_number="9",
        author_ids=[pratchett], book_ids=[mort],
    )  # fmt: skip
    await factory.entry(alice, hobbit)
    await factory.entry(alice, mort)


@pytest.mark.parametrize(
    ("path", "found", "not_found"),
    [
        ("/?q=Hob%00bit", "The Hobbit", "Mort"),
        ("/catalog?q=Hob%00bit", "The Hobbit", "Mort"),
        ("/suggest/books?q=Hob%00bit", "The Hobbit", "Mort"),
        ("/suggest/authors?q=Tol%00kien", "Tolkien", "Pratchett"),
        ("/suggest/series?q=Middle%00-earth", "Middle-earth", "Discworld"),
        ("/suggest/stories?q=Leaf%00%20by", "Leaf by Niggle", "Troll Bridge"),
        ("/api/v1/me/readings?q=Hob%00bit", "The Hobbit", "Mort"),
        ("/api/v1/books?q=Hob%00bit", "The Hobbit", "Mort"),
        ("/api/v1/authors?q=Tol%00kien", "Tolkien", "Pratchett"),
        ("/api/v1/series?q=Middle%00-earth", "Middle-earth", "Discworld"),
    ],
)
async def test_nul_in_a_search_is_dropped(
    member: httpx.AsyncClient, path: str, found: str, not_found: str
) -> None:
    response = await member.get(path)
    assert response.status_code == 200, response.text
    assert found in response.text
    assert not_found not in response.text


@pytest.mark.parametrize("q", ["%00", "%00%00", "%00%20", "%20%20"])
@pytest.mark.parametrize("kind", ["books", "authors", "series"])
async def test_blank_type_ahead_query_is_refused(
    member: httpx.AsyncClient, kind: str, q: str
) -> None:
    assert (await member.get(f"/api/v1/{kind}?q={q}")).status_code == 422
