"""Spec 012 User Story 2: every failure falls back to writing by hand; the daily allowance.

The AI is ``FakeSummaryGenerator`` and Open Library is ``FakeBookSource``.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from book_tracker.domain.drafts import BookDescription
from book_tracker.services.errors import AiDeclined, AiUnavailable
from tests.conftest import Factory, signed_in
from tests.fakes import DRAFT_TEXT, WIKI, FakeBookSource, FakeSummaryGenerator, good_draft
from tests.integration.test_summary_drafts import csrf, draft_id, save, textarea

NOON = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
TYPED = "My half-written summary."


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: NOON


@pytest.fixture
async def alice(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    user = await factory.user("alice", display_name="Alice")
    return await signed_in(client_factory(), user)


@pytest.fixture
async def ben(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    user = await factory.user("ben", display_name="Ben")
    return await signed_in(client_factory(), user)


@pytest.fixture
async def book(factory: Factory) -> uuid.UUID:
    owner = await factory.user("owner")
    author = await factory.author("Jim Butcher", owner)
    return await factory.book("Storm Front", owner, author_ids=[author])


async def post_draft(
    client: httpx.AsyncClient, book: uuid.UUID, text: str = TYPED, regenerate: bool = True
) -> str:
    page = await client.get(f"/catalog/books/{book}/summary")
    response = await client.post(
        f"/catalog/books/{book}/summary/draft",
        data={"csrf_token": csrf(page.text), "text": text, "regenerate": "1" if regenerate else ""},
    )
    assert response.status_code == 200
    return response.text


def alert(page: str) -> str:
    found = re.search(r'<div class="conflict" role="alert" id="draft-error"><p>([^<]+)</p>', page)
    assert found, "no failure message"
    return found.group(1).replace("&#39;", "'")


def left(page: str) -> int:
    found = re.search(r"(\d+) AI drafts? left today\.", page)
    assert found
    return int(found.group(1))


BLOCKED = "https://www.goodreads.com/book/show/47212"
SHORT = "Too short to be a summary."


@pytest.mark.ac("012/AC-09")
@pytest.mark.parametrize(
    ("result", "message"),
    [
        (AiUnavailable(), "The AI didn't answer in time. Try again, or write the summary yourself."),
        (good_draft(status="not_enough_information", text=""),
         "The AI couldn't find enough about this book to write a summary. You can write one yourself."),
        (AiDeclined(), "The AI couldn't write a summary of this book. You can write one yourself."),
        (good_draft(source_urls=(BLOCKED,), known_urls=frozenset({BLOCKED}), cited_urls=()),
         "The AI's draft didn't pass our checks. Try again, or write the summary yourself."),
        (good_draft(cited_urls=(BLOCKED,)),
         "The AI's draft didn't pass our checks. Try again, or write the summary yourself."),
        (good_draft(text=SHORT),
         "The AI's draft didn't pass our checks. Try again, or write the summary yourself."),
        (good_draft(text=" ".join(["word"] * 251)),
         "The AI's draft didn't pass our checks. Try again, or write the summary yourself."),
        (good_draft(source_urls=(), known_urls=frozenset(), cited_urls=()),
         "The AI couldn't find enough about this book to write a summary. You can write one yourself."),
    ],
)  # fmt: skip
async def test_each_failure_keeps_hand_writing(
    alice: httpx.AsyncClient,
    book: uuid.UUID,
    factory: Factory,
    summary_generator: FakeSummaryGenerator,
    result: Any,
    message: str,
) -> None:
    summary_generator.results.append(result)
    page = await post_draft(alice, book)
    assert alert(page) == message
    assert textarea(page) == TYPED
    assert 'name="draft_id"' not in page
    assert 'aria-describedby="text-hint draft-error"' in page
    assert ">Draft with AI</button>" in page  # can try again
    assert await factory.scalar("SELECT count(*) FROM summary_draft") == 0
    saved = await save(alice, book, TYPED, None)
    assert saved.status_code == 303
    assert await factory.scalar("SELECT origin FROM book_summary WHERE is_current") == "manual"


@pytest.mark.ac("012/AC-09")
async def test_not_set_up(
    alice: httpx.AsyncClient, book: uuid.UUID, factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    summary_generator.configured = False
    page = await post_draft(alice, book)
    assert alert(page) == "AI drafts aren't set up. You can write the summary yourself."
    assert textarea(page) == TYPED
    assert left(page) == 10  # nothing was asked, so nothing counts (AC-10)
    assert await factory.scalar("SELECT count(*) FROM ai_draft_usage") == 0


@pytest.mark.ac("012/AC-09")
async def test_server_without_a_key(alice: httpx.AsyncClient, book: uuid.UUID) -> None:
    """The app as built for tests has no key: the real 'not set up' path, no fake."""
    page = await post_draft(alice, book)
    assert alert(page) == "AI drafts aren't set up. You can write the summary yourself."


@pytest.mark.ac("012/AC-13")
async def test_copy_of_the_description_is_rejected(
    alice: httpx.AsyncClient, book: uuid.UUID, book_source: FakeBookSource,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    url = "https://openlibrary.org/works/OL5685119W"
    book_source.descriptions["storm front"] = BookDescription(url, "Blurb: " + DRAFT_TEXT)
    page = await post_draft(alice, book)
    assert "didn't pass our checks" in alert(page)
    _, description = summary_generator.calls[0]
    assert description is not None and description.work_url == url


@pytest.mark.ac("012/AC-10")
async def test_allowance_counts_requests_that_reach_the_ai(
    app: Any, alice: httpx.AsyncClient, ben: httpx.AsyncClient, book: uuid.UUID,
    summary_generator: FakeSummaryGenerator, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    monkeypatch.setattr(app.state.settings, "ai_daily_draft_limit", 3)
    summary_generator.results.append(AiUnavailable())
    first = await post_draft(alice, book)
    assert left(first) == 2  # a failed request still counts
    assert left(await post_draft(alice, book)) == 1
    assert left(await post_draft(alice, book)) == 0
    refused = await post_draft(alice, book)
    assert alert(refused) == (
        "You've used your 3 AI drafts for today. You can write the summary yourself, "
        "or draft again tomorrow."
    )
    assert len(summary_generator.calls) == 3  # the fourth never reached the AI
    assert left(await post_draft(ben, book)) == 2  # Ben's allowance is his own
    app.state.clock = lambda: NOON + timedelta(days=1)
    assert left(await post_draft(alice, book)) == 2  # a new day


@pytest.mark.ac("012/AC-11")
async def test_blocked_site_in_a_draft_is_never_shown(
    alice: httpx.AsyncClient, book: uuid.UUID, summary_generator: FakeSummaryGenerator
) -> None:
    amazon = "https://smile.amazon.co.uk/dp/1"
    summary_generator.results.append(
        good_draft(source_urls=(WIKI, amazon), known_urls=frozenset({WIKI, amazon}))
    )
    page = await post_draft(alice, book)
    assert "amazon" not in page.lower() and DRAFT_TEXT not in page


@pytest.mark.ac("012/AC-12")
async def test_length_band(
    alice: httpx.AsyncClient, book: uuid.UUID, summary_generator: FakeSummaryGenerator
) -> None:
    sixty = " ".join(["word"] * 60)
    summary_generator.results.append(good_draft(text=sixty))
    assert textarea(await post_draft(alice, book)) == sixty
    summary_generator.results.append(good_draft(text=" ".join(["word"] * 59)))
    assert "didn't pass our checks" in alert(await post_draft(alice, book))


@pytest.mark.ac("012/AC-14")
async def test_other_pages_never_wait_for_the_ai(
    alice: httpx.AsyncClient, book: uuid.UUID, summary_generator: FakeSummaryGenerator
) -> None:
    summary_generator.delay = 1.5
    page = await alice.get(f"/catalog/books/{book}/summary")
    token = csrf(page.text)
    drafting = asyncio.create_task(
        alice.post(f"/catalog/books/{book}/summary/draft", data={"csrf_token": token})
    )
    await asyncio.sleep(0.1)  # the draft is now waiting on the AI
    started = time.monotonic()
    for path in ("/", f"/catalog/books/{book}/summary", "/catalog"):
        assert (await alice.get(path)).status_code == 200
    assert time.monotonic() - started < 1.0
    assert not drafting.done()
    finished = await drafting
    assert draft_id(finished.text)
