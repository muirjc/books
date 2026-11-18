"""T080: adding a book someone else already added, through the pages (AC-15, AC-16)."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in


@pytest.mark.ac("001/AC-15")
async def test_type_ahead_offers_existing_book(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    ben = await factory.user("ben")
    tolkien = await factory.author("J.R.R. Tolkien", alice)
    hobbit = await factory.book("The Hobbit", alice, author_ids=[tolkien])
    await factory.entry(alice, hobbit)
    member = await signed_in(client_factory(), ben)
    suggestions = await member.get("/suggest/books", params={"field": "title", "title": "Hob"})
    assert suggestions.status_code == 200
    assert 'role="listbox"' in suggestions.text
    options = re.findall(r'<li[^>]*role="option"[^>]*data-id="([^"]+)"', suggestions.text)
    assert options == [str(hobbit)]
    assert "J.R.R. Tolkien" in suggestions.text
    added = await member.post("/books/add", data={"book_id": str(hobbit), "title": "The Hobbit"})
    assert added.status_code == 303
    assert await factory.scalar("SELECT count(*) FROM book") == 1
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 2


@pytest.mark.ac("001/AC-16")
async def test_duplicate_author_in_form_offers_existing(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    existing = await factory.author("Terry Pratchett", alice)
    member = await signed_in(client_factory(), alice)
    response = await member.post(
        "/books/add", data={"title": "Mort", "author_name_0": "terry pratchett"}
    )
    assert response.status_code == 409
    assert "Already in the catalog" in response.text
    assert f'name="author_id_0" value="{existing}"' in response.text
    assert "Use existing author" in response.text
    chosen = await member.post(
        "/books/add",
        data={"title": "Mort", "author_name_0": "terry pratchett", "author_id_0": str(existing)},
    )
    assert chosen.status_code == 303
    assert await factory.scalar("SELECT count(*) FROM author") == 1


async def test_suggestion_endpoints(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    await factory.author("Robert Galbraith", alice, is_pen_name=True, real_name="J.K. Rowling")
    await factory.series("Cormoran Strike", alice)
    member = await signed_in(client_factory(), alice)
    authors = await member.get(
        "/suggest/authors", params={"field": "author_name_1", "author_name_1": "rowling"}
    )
    assert "Robert Galbraith" in authors.text
    assert 'id="author_name_1-listbox"' in authors.text
    series = await member.get("/suggest/series", params={"q": "strike"})
    assert "Cormoran Strike" in series.text
    empty = await member.get("/suggest/series", params={"q": ""})
    assert empty.status_code == 200
    assert 'role="option"' not in empty.text
    nothing = await member.get("/suggest/books", params={"q": "zzz"})
    assert "No matches" in nothing.text
