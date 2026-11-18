"""T099: writing a summary and seeing its history in the pages (AC-24, AC-25)."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in


@pytest.mark.ac("001/AC-24")
@pytest.mark.ac("001/AC-25")
async def test_summary_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    book = await factory.book("The Hobbit", alice)
    entry = await factory.entry(ben, book)
    alice_page = await signed_in(client_factory(), alice)
    form = await alice_page.get(f"/catalog/books/{book}/summary")
    assert form.status_code == 200
    assert re.search(r'<label for="text"', form.text)
    assert "No summary yet" in form.text
    saved = await alice_page.post(
        f"/catalog/books/{book}/summary", data={"text": "Bilbo leaves home."}
    )
    assert saved.status_code == 303
    ben_page = await signed_in(client_factory(), ben)
    shown = (await ben_page.get(f"/entries/{entry}")).text
    assert "Bilbo leaves home." in shown
    assert "Written by Alice on" in shown
    await ben_page.post(f"/catalog/books/{book}/summary", data={"text": "A dragon, some gold."})
    history = (await ben_page.get(f"/catalog/books/{book}/summary")).text
    assert history.index("A dragon, some gold.") < history.index("Bilbo leaves home.")
    assert "Written by Ben on" in history and "Written by Alice on" in history
    assert "Current" in history


async def test_summary_validation(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    book = await factory.book("The Hobbit", alice)
    page = await signed_in(client_factory(), alice)
    empty = await page.post(f"/catalog/books/{book}/summary", data={"text": "  "})
    assert empty.status_code == 422
    assert "Write a summary" in empty.text
    assert (
        await page.get("/catalog/books/00000000-0000-4000-8000-000000000000/summary")
    ).status_code == 404


@pytest.mark.ac("001/AC-24")
async def test_summary_when_adding_a_book(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice = await factory.user("alice")
    page = await signed_in(client_factory(), alice)
    form = await page.get("/books/add")
    assert re.search(r'<label for="summary"', form.text)
    added = await page.post(
        "/books/add",
        data={
            "title": "Earthsea",
            "author_name_0": "Ursula K. Le Guin",
            "summary": "A young wizard.",
        },
    )
    assert added.status_code == 303
    assert await factory.scalar("SELECT text FROM book_summary") == "A young wizard."
