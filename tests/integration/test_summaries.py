"""T097: one shared current summary per book, with history (FR-024, FR-025)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, gather, signed_in


@pytest.fixture
async def world(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> dict[str, Any]:
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    book = await factory.book("The Hobbit", alice)
    return {
        "alice": await signed_in(client_factory(), alice),
        "ben": await signed_in(client_factory(), ben),
        "book": book,
    }


@pytest.mark.ac("001/AC-24")
async def test_summary_is_shared_and_attributed(world: dict[str, Any]) -> None:
    book = world["book"]
    saved = await world["alice"].post(
        f"/api/v1/books/{book}/summaries", json={"text": "  A hobbit goes on an adventure.  "}
    )
    assert saved.status_code == 201
    summary = saved.json()
    assert summary["text"] == "A hobbit goes on an adventure."
    assert summary["origin"] == "manual"
    assert summary["created_by"]["display_name"] == "Alice"
    assert summary["is_current"] is True
    assert summary["model"] is None and summary["source_urls"] is None
    seen = (await world["ben"].get(f"/api/v1/books/{book}")).json()["current_summary"]
    assert seen["text"] == "A hobbit goes on an adventure."
    assert seen["created_by"]["display_name"] == "Alice"


@pytest.mark.ac("001/AC-25")
async def test_new_summary_replaces_and_keeps_history(world: dict[str, Any]) -> None:
    book = world["book"]
    await world["alice"].post(f"/api/v1/books/{book}/summaries", json={"text": "First."})
    await world["ben"].post(f"/api/v1/books/{book}/summaries", json={"text": "Second."})
    current = (await world["alice"].get(f"/api/v1/books/{book}")).json()["current_summary"]
    assert (current["text"], current["created_by"]["display_name"]) == ("Second.", "Ben")
    history = (await world["alice"].get(f"/api/v1/books/{book}/summaries")).json()
    assert [(s["text"], s["is_current"]) for s in history] == [("Second.", True), ("First.", False)]


async def test_concurrent_saves_leave_one_current(world: dict[str, Any], factory: Factory) -> None:
    book = world["book"]
    results: list[Any] = await gather(
        world["alice"].post(f"/api/v1/books/{book}/summaries", json={"text": "From Alice."}),
        world["ben"].post(f"/api/v1/books/{book}/summaries", json={"text": "From Ben."}),
    )
    assert [r.status_code for r in results] == [201, 201]
    assert (
        await factory.scalar(
            "SELECT count(*) FROM book_summary WHERE book_id = :b AND is_current", b=book
        )
        == 1
    )
    assert await factory.scalar("SELECT count(*) FROM book_summary WHERE book_id = :b", b=book) == 2


@pytest.mark.ac("001/AC-24")
async def test_summary_with_new_book(world: dict[str, Any], factory: Factory) -> None:
    author = (
        await world["alice"].post("/api/v1/authors", json={"name": "Ursula K. Le Guin"})
    ).json()["id"]
    added = await world["alice"].post(
        "/api/v1/me/readings",
        json={
            "new_book": {
                "title": "A Wizard of Earthsea",
                "author_ids": [author],
                "summary": "A young wizard learns the cost of power.",
            }
        },
    )
    assert added.status_code == 201
    current = added.json()["book"]["current_summary"]
    assert current["text"] == "A young wizard learns the cost of power."
    assert current["origin"] == "manual"
    blank = await world["alice"].post(
        "/api/v1/me/readings",
        json={
            "new_book": {"title": "The Tombs of Atuan", "author_ids": [author], "summary": "   "}
        },
    )
    assert blank.json()["book"]["current_summary"] is None


async def test_validation_and_unknown_book(world: dict[str, Any]) -> None:
    book = world["book"]
    api = world["alice"]
    assert (
        await api.post(f"/api/v1/books/{book}/summaries", json={"text": "  "})
    ).status_code == 422
    assert (
        await api.post(f"/api/v1/books/{book}/summaries", json={"text": "x" * 5001})
    ).status_code == 422
    missing = "00000000-0000-4000-8000-000000000000"
    assert (
        await api.post(f"/api/v1/books/{missing}/summaries", json={"text": "x"})
    ).status_code == 404
    assert (await api.get(f"/api/v1/books/{missing}/summaries")).status_code == 404
