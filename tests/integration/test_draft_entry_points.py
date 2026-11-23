"""Spec 012 User Story 5: start a draft from an entry page and from Add a book."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from book_tracker.services.errors import AiUnavailable
from tests.conftest import Factory, TestUser, signed_in
from tests.fakes import DRAFT_TEXT, WIKI, FakeSummaryGenerator
from tests.integration.test_draft_failures import alert, left
from tests.integration.test_summary_drafts import csrf

NOTICE = "AI draft, not saved yet. Check it, edit it if you like, then save it, or discard it."


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.mark.ac("012/AC-22")
async def test_entry_page_offers_a_draft(
    member: httpx.AsyncClient, alice: TestUser, factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    book = await factory.book("Storm Front", alice)
    entry = await factory.entry(alice, book, finished_on=date(2025, 1, 1))
    page = (await member.get(f"/entries/{entry}")).text
    form = re.search(
        rf'<form method="post" action="/catalog/books/{book}/summary/draft"[^>]*>(.*?)</form>',
        page, re.S,
    )  # fmt: skip
    assert form and ">Draft with AI</button>" in form.group(1)
    assert "Write a summary" in page
    drafted = await member.post(
        f"/catalog/books/{book}/summary/draft", data={"csrf_token": csrf(page)}
    )
    assert drafted.status_code == 200
    assert "<h1>Summary of “Storm Front”</h1>" in drafted.text and NOTICE in drafted.text


def add_form(page: str, **fields: str) -> dict[str, str]:
    data = {"csrf_token": csrf(page), "status": "finished", "finished_on": "2025-01-01"}
    data.update(fields)
    return data


@pytest.mark.ac("012/AC-23")
async def test_add_a_book_drafts_into_the_summary_field(
    member: httpx.AsyncClient, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    page = (await member.get("/books/add")).text
    assert 'name="action" value="draft_summary"' in page
    assert ">Draft summary with AI</button>" in page
    fields = {"title": "Storm Front", "author_name_0": "Jim Butcher", "notes": "Loved it",
              "isbn_13": "978-0-451-45781-3", "series_name": "The Dresden Files",
              "series_number": "1"}  # fmt: skip
    drafted = await member.post("/books/add", data={**add_form(page, **fields),
                                                    "action": "draft_summary"})  # fmt: skip
    assert drafted.status_code == 200
    body = drafted.text
    assert NOTICE in body
    found = re.search(r'<textarea id="summary"[^>]*>(.*?)</textarea>', body, re.S)
    assert found and html.unescape(found.group(1)) == DRAFT_TEXT
    for value in ("Storm Front", "Jim Butcher", "Loved it", "The Dresden Files"):
        assert value in body  # everything typed is kept
    assert f'href="{WIKI}"' in body and left(body) == 9
    draft = re.search(r'name="summary_draft_id" value="([^"]+)"', body)
    assert draft
    assert await factory.scalar("SELECT count(*) FROM book") == 0  # nothing saved yet
    facts, _ = summary_generator.calls[0]
    assert facts.title == "Storm Front" and facts.authors == ("Jim Butcher",)
    assert facts.isbn13 == "9780451457813" and facts.series_name == "The Dresden Files"
    # Saving the book saves the summary as an AI draft, edited or not.
    saved = await member.post("/books/add", data={
        **add_form(drafted.text, **fields), "summary": DRAFT_TEXT + " More.",
        "summary_draft_id": draft.group(1), "confirm_author_0": "Jim Butcher",
        "confirm_series": "The Dresden Files",
    })  # fmt: skip
    assert saved.status_code == 303, saved.text[:2000]
    row = await factory.row("SELECT origin, model, source_urls FROM book_summary")
    assert row["origin"] == "ai_edited" and row["model"] == "claude-opus-5-5"
    assert row["source_urls"] == [WIKI]


@pytest.mark.ac("012/AC-23")
async def test_add_a_book_needs_a_title_and_author_first(
    member: httpx.AsyncClient, summary_generator: FakeSummaryGenerator
) -> None:
    page = (await member.get("/books/add")).text
    response = await member.post("/books/add", data={**add_form(page, title="Storm Front"),
                                                     "action": "draft_summary"})  # fmt: skip
    assert response.status_code == 200
    assert alert(response.text) == (
        "Enter the title and at least one author first, then draft the summary."
    )
    assert summary_generator.calls == []
    assert 'value="Storm Front"' in response.text


@pytest.mark.ac("012/AC-23")
async def test_add_a_book_failures_and_allowance(
    member: httpx.AsyncClient, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    summary_generator.results.append(AiUnavailable())
    page = (await member.get("/books/add")).text
    response = await member.post("/books/add", data={
        **add_form(page, title="Mort", author_name_0="Terry Pratchett", summary="Mine."),
        "action": "draft_summary",
    })  # fmt: skip
    assert "The AI didn't answer in time." in alert(response.text)
    assert left(response.text) == 9
    assert ">Mine.</textarea>" in response.text
    assert 'name="summary_draft_id"' not in response.text
    saved = await member.post("/books/add", data={
        **add_form(response.text, title="Mort", author_name_0="Terry Pratchett", summary="Mine."),
        "confirm_author_0": "Terry Pratchett",
    })  # fmt: skip
    assert saved.status_code == 303
    assert await factory.scalar("SELECT origin FROM book_summary") == "manual"


async def test_a_forged_draft_id_on_add_saves_manual(
    member: httpx.AsyncClient, factory: Factory
) -> None:
    page = (await member.get("/books/add")).text
    saved = await member.post("/books/add", data={
        **add_form(page, title="Mort", author_name_0="Terry Pratchett", summary=DRAFT_TEXT),
        "summary_draft_id": str(uuid.uuid4()), "confirm_author_0": "Terry Pratchett",
    })  # fmt: skip
    assert saved.status_code == 303
    assert await factory.scalar("SELECT origin FROM book_summary") == "manual"
