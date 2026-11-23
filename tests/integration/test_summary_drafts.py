"""Spec 012 User Story 1: draft a summary with the AI, review it, and save or discard it.

The AI is ``FakeSummaryGenerator``; nothing here contacts Anthropic (Principle V).
"""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from book_tracker.services.errors import AiUnavailable
from tests.conftest import Factory, TestUser, signed_in
from tests.fakes import DRAFT_TEXT, WIKI, FakeSummaryGenerator, good_draft

NOTICE = "AI draft, not saved yet. Check it, edit it if you like, then save it, or discard it."


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@dataclass
class World:
    alice: TestUser
    member: httpx.AsyncClient
    other: httpx.AsyncClient
    book: uuid.UUID
    mort: uuid.UUID


@pytest.fixture
async def world(factory: Factory, client_factory: Callable[[], httpx.AsyncClient]) -> World:
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    butcher = await factory.author("Jim Butcher", alice)
    book = await factory.book("Storm Front", alice, author_ids=[butcher], isbn_13="9780451457813")
    mort = await factory.book("Mort", alice)
    return World(
        alice, await signed_in(client_factory(), alice), await signed_in(client_factory(), ben),
        book, mort,
    )  # fmt: skip


def csrf(body: str) -> str:
    found = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert found
    return found.group(1)


def draft_id(body: str) -> str:
    found = re.search(r'name="draft_id" value="([^"]+)"', body)
    assert found, "no draft id on the page"
    return found.group(1)


def textarea(body: str) -> str:
    found = re.search(r'<textarea id="text"[^>]*>(.*?)</textarea>', body, re.S)
    assert found
    return html.unescape(found.group(1))


async def draft(
    client: httpx.AsyncClient, book: uuid.UUID, *, text: str = "", regenerate: bool = False,
    htmx: bool = False, extra: dict[str, str] | None = None,
) -> httpx.Response:  # fmt: skip
    page = await client.get(f"/catalog/books/{book}/summary")
    data = {"csrf_token": csrf(page.text), "text": text, "regenerate": "1" if regenerate else "0"}
    return await client.post(
        f"/catalog/books/{book}/summary/draft",
        data={**data, **(extra or {})},
        headers={"HX-Request": "true"} if htmx else {},
    )


async def save(
    client: httpx.AsyncClient, book: uuid.UUID, text: str, draft: str | None
) -> httpx.Response:
    page = await client.get(f"/catalog/books/{book}/summary")
    data = {"csrf_token": csrf(page.text), "text": text}
    if draft is not None:
        data["draft_id"] = draft
    return await client.post(f"/catalog/books/{book}/summary", data=data)


@pytest.mark.ac("012/AC-01")
async def test_summary_page_offers_draft_with_ai(world: World) -> None:
    page = (await world.member.get(f"/catalog/books/{world.book}/summary")).text
    assert f'formaction="/catalog/books/{world.book}/summary/draft"' in page
    assert ">Draft with AI</button>" in page
    assert "The AI writes a draft for you to check. Nothing is saved until you save it." in page


@pytest.mark.ac("012/AC-02")
async def test_draft_is_shown_for_review(
    world: World, summary_generator: FakeSummaryGenerator
) -> None:
    both = (WIKI, "https://example.org/b")
    summary_generator.results.append(good_draft(source_urls=both, known_urls=frozenset(both)))
    response = await draft(world.member, world.book)
    assert response.status_code == 200
    page = response.text
    assert NOTICE in page
    assert textarea(page) == DRAFT_TEXT
    assert uuid.UUID(draft_id(page))
    assert "<h2" in page and "Based on" in page
    assert f'<a href="{WIKI}" target="_blank" rel="noopener noreferrer">' in page
    assert 'href="https://example.org/b"' in page
    assert "(opens in a new tab)" in page
    assert "Drafted by claude-opus-5-5" in page
    assert ">Save summary</button>" in page
    assert 'name="regenerate" value="1"' in page and ">Regenerate</button>" in page
    assert f'formaction="/catalog/books/{world.book}/summary/discard"' in page
    assert ">Discard draft</button>" in page
    assert "9 AI drafts left today." in page
    facts, _ = summary_generator.calls[0]
    assert facts.title == "Storm Front" and facts.authors == ("Jim Butcher",)
    assert facts.isbn13 == "9780451457813"


@pytest.mark.ac("012/AC-03")
async def test_nothing_is_stored_until_saved(
    world: World, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    await draft(world.member, world.book)
    assert await factory.scalar("SELECT count(*) FROM book_summary") == 0
    others = (await world.other.get(f"/catalog/books/{world.book}/summary")).text
    assert DRAFT_TEXT not in others and "No summary yet." in others
    api = (await world.other.get(f"/api/v1/books/{world.book}")).json()
    assert api["current_summary"] is None


@pytest.mark.ac("012/AC-04")
async def test_save_unchanged_is_ai_and_edited_is_ai_edited(
    world: World, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    first = await draft(world.member, world.book)
    saved = await save(world.member, world.book, "  " + DRAFT_TEXT + "\n", draft_id(first.text))
    assert saved.status_code == 303
    row = await factory.row(
        "SELECT origin, model, source_urls, created_by FROM book_summary WHERE is_current"
    )
    assert row["origin"] == "ai" and row["model"] == "claude-opus-5-5"
    assert row["source_urls"] == [WIKI] and row["created_by"] == world.alice.id
    second = await draft(world.member, world.book, regenerate=True)
    await save(world.member, world.book, DRAFT_TEXT + " One more line.", draft_id(second.text))
    row = await factory.row("SELECT origin, model, source_urls FROM book_summary WHERE is_current")
    assert row["origin"] == "ai_edited" and row["model"] == "claude-opus-5-5"
    assert await factory.scalar("SELECT count(*) FROM book_summary") == 2  # history kept


@pytest.mark.ac("012/AC-05")
async def test_history_says_how_each_summary_was_written(
    world: World, summary_generator: FakeSummaryGenerator
) -> None:
    await save(world.member, world.book, "My own words.", None)
    first = await draft(world.member, world.book)
    await save(world.member, world.book, DRAFT_TEXT, draft_id(first.text))
    second = await draft(world.member, world.book, regenerate=True)
    await save(world.member, world.book, "Edited: " + DRAFT_TEXT, draft_id(second.text))
    page = (await world.member.get(f"/catalog/books/{world.book}/summary")).text
    history = page.split("<h2>History</h2>", 1)[1]
    lines = re.findall(r'<p class="muted">(Written by [^<]*)</p>', history)
    assert lines == [
        "Written by Alice on 23 Nov 2026 (AI draft, edited)",
        "Written by Alice on 23 Nov 2026 (AI draft)",
        "Written by Alice on 23 Nov 2026",
    ]
    assert history.count(f'href="{WIKI}"') == 2  # each AI summary lists its sources


def hidden(body: str, name: str) -> str | None:
    found = re.search(rf'name="{name}" value="([^"]*)"', body)
    return html.unescape(found.group(1)) if found else None


@pytest.mark.ac("012/AC-06")
async def test_discard_restores_the_box_as_it_was(
    world: World, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    await save(world.member, world.book, "Already here.", None)
    typed = "My own three paragraphs, half written."
    page = (await draft(world.member, world.book, text=typed)).text
    assert hidden(page, "before_text") == typed
    discarded = await world.member.post(
        f"/catalog/books/{world.book}/summary/discard",
        data={"csrf_token": csrf(page), "text": DRAFT_TEXT, "draft_id": draft_id(page),
              "before_text": typed},
    )  # fmt: skip
    assert discarded.status_code == 200
    back = discarded.text
    assert textarea(back) == typed
    assert NOTICE not in back and 'name="draft_id"' not in back
    assert await factory.scalar("SELECT count(*) FROM book_summary") == 1
    # Regenerating keeps the text from before the first draft.
    again = await draft(world.member, world.book, text=DRAFT_TEXT, regenerate=True,
                        extra={"draft_id": draft_id(page), "before_text": typed})  # fmt: skip
    assert hidden(again.text, "before_text") == typed


@pytest.mark.ac("012/AC-08")
async def test_a_failed_regenerate_keeps_the_draft_shown(
    world: World, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    """PR #32 review: the AI text still in the box must still save as an AI draft."""
    first = (await draft(world.member, world.book)).text
    summary_generator.results.append(AiUnavailable())
    failed = await draft(world.member, world.book, text=DRAFT_TEXT, regenerate=True,
                         extra={"draft_id": draft_id(first)})  # fmt: skip
    assert "didn't answer in time" in html.unescape(failed.text)
    assert textarea(failed.text) == DRAFT_TEXT
    assert hidden(failed.text, "draft_id") == draft_id(first)
    await save(world.member, world.book, DRAFT_TEXT, hidden(failed.text, "draft_id"))
    assert await factory.scalar("SELECT origin FROM book_summary WHERE is_current") == "ai"


@pytest.mark.ac("012/AC-08")
async def test_a_rejected_save_keeps_the_draft_id(
    world: World, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    first = (await draft(world.member, world.book)).text
    rejected = await save(world.member, world.book, "   ", draft_id(first))
    assert rejected.status_code == 422
    assert hidden(rejected.text, "draft_id") == draft_id(first)


@pytest.mark.ac("012/AC-07")
async def test_full_page_without_javascript_and_partial_with_htmx(
    world: World, summary_generator: FakeSummaryGenerator
) -> None:
    full = (await draft(world.member, world.book)).text
    assert "<html" in full and 'id="summary-area"' in full
    partial = await draft(world.member, world.book, htmx=True)
    assert "<html" not in partial.text
    assert partial.text.lstrip().startswith('<div id="summary-area"')
    assert NOTICE in partial.text
    assert partial.headers.get("vary", "").lower().count("hx-request") == 1
    page = (await world.member.get(f"/catalog/books/{world.book}/summary")).text
    assert 'hx-post="/catalog/books/' in page and 'hx-target="#summary-area"' in page
    assert "Drafting… this can take up to 30 seconds" in page
    assert 'role="status"' in page


@pytest.mark.ac("012/AC-08")
async def test_only_the_apps_own_draft_for_this_book_counts(
    world: World, factory: Factory, summary_generator: FakeSummaryGenerator
) -> None:
    await save(world.member, world.book, DRAFT_TEXT, str(uuid.uuid4()))  # forged id
    assert await factory.scalar("SELECT origin FROM book_summary WHERE is_current") == "manual"
    for_mort = await draft(world.member, world.mort)
    await save(world.member, world.book, DRAFT_TEXT, draft_id(for_mort.text))  # other book
    row = await factory.row("SELECT origin, model, source_urls FROM book_summary WHERE is_current")
    assert row["origin"] == "manual" and row["model"] is None and row["source_urls"] is None
    await save(world.member, world.book, DRAFT_TEXT, "not-a-uuid")
    assert await factory.scalar("SELECT origin FROM book_summary WHERE is_current") == "manual"


async def test_draft_for_unknown_book_and_bad_csrf(
    world: World, summary_generator: FakeSummaryGenerator
) -> None:
    page = (await world.member.get(f"/catalog/books/{world.book}/summary")).text
    unknown = await world.member.post(
        f"/catalog/books/{uuid.uuid4()}/summary/draft", data={"csrf_token": csrf(page)}
    )
    assert unknown.status_code == 404
    bad = await world.member.post(
        f"/catalog/books/{world.book}/summary/draft",
        data={"text": ""},
        headers={"X-CSRF-Token": "wrong"},
    )
    assert bad.status_code == 403
    assert summary_generator.calls == []
