"""T076: type-ahead suggestions from the shared catalog (FR-010, AC-15)."""

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


@pytest.mark.ac("001/AC-15")
async def test_books_by_title_and_author(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    tolkien = await factory.author("J.R.R. Tolkien", alice)
    await factory.book("The Hobbit", alice, author_ids=[tolkien])
    await factory.book("Hobbits of the Shire", alice)
    await factory.book("A Short History of Hobbies", alice)
    titles = [b["title"] for b in (await api.get("/api/v1/books?q=hob")).json()]
    # Prefix matches first, then other matches, each alphabetically.
    assert titles == ["Hobbits of the Shire", "A Short History of Hobbies", "The Hobbit"]
    by_author = (await api.get("/api/v1/books?q=tolkien")).json()
    assert [b["title"] for b in by_author] == ["The Hobbit"]


async def test_limit_and_default(api: httpx.AsyncClient, factory: Factory, alice: TestUser) -> None:
    for i in range(12):
        await factory.book(f"Book {i:02d}", alice)
    assert len((await api.get("/api/v1/books?q=book")).json()) == 10
    assert len((await api.get("/api/v1/books?q=book&limit=3")).json()) == 3
    assert (await api.get("/api/v1/books?q=book&limit=26")).status_code == 422
    assert (await api.get("/api/v1/books?q=")).status_code == 422


async def test_wildcards_are_literal(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    await factory.book("100% Real", alice)
    await factory.book("Snake_case", alice)
    await factory.book("Plain", alice)
    assert [b["title"] for b in (await api.get("/api/v1/books?q=%25")).json()] == ["100% Real"]
    assert [b["title"] for b in (await api.get("/api/v1/books?q=_")).json()] == ["Snake_case"]


@pytest.mark.ac("001/AC-15")
async def test_isbn_matches_first(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    await factory.book("9780306406157 Stories", alice)
    await factory.book("By ISBN", alice, isbn_13="9780306406157")
    found = (await api.get("/api/v1/books?q=978-0-306-40615-7")).json()
    assert found[0]["title"] == "By ISBN"


async def test_authors_match_name_and_real_name(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    await factory.author("Robert Galbraith", alice, is_pen_name=True, real_name="J.K. Rowling")
    await factory.author("Robert Jordan", alice)
    names = [a["name"] for a in (await api.get("/api/v1/authors?q=robert")).json()]
    assert names == ["Robert Galbraith", "Robert Jordan"]
    real = (await api.get("/api/v1/authors?q=rowling")).json()
    assert [a["name"] for a in real] == ["Robert Galbraith"]


async def test_series_case_insensitive(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    await factory.series("Discworld", alice)
    await factory.series("The Wheel of Time", alice)
    assert [s["name"] for s in (await api.get("/api/v1/series?q=DISC")).json()] == ["Discworld"]
    assert [s["name"] for s in (await api.get("/api/v1/series?q=time")).json()] == [
        "The Wheel of Time"
    ]
