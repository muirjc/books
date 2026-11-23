"""Spec 012 User Story 3: drafts are reused for 30 days; Regenerate asks again."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.fakes import DRAFT_TEXT, FakeSummaryGenerator, good_draft
from tests.integration.test_draft_failures import left, post_draft
from tests.integration.test_summary_drafts import draft_id, save, textarea

NOON = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
OTHER_TEXT = DRAFT_TEXT.replace("tired detective", "weary investigator")


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: NOON


@pytest.fixture
async def clients(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> tuple[httpx.AsyncClient, httpx.AsyncClient]:
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    return await signed_in(client_factory(), alice), await signed_in(client_factory(), ben)


@pytest.fixture
async def books(factory: Factory) -> dict[str, uuid.UUID]:
    owner = await factory.user("owner")
    butcher = await factory.author("Jim Butcher", owner)
    return {
        "storm": await factory.book("Storm Front", owner, author_ids=[butcher]),
        "copy": await factory.book("Storm Front", owner, author_ids=[butcher]),
        "fool": await factory.book("Fool Moon", owner, author_ids=[butcher]),
    }


@pytest.mark.ac("012/AC-15")
async def test_cached_draft_is_reused_by_any_member(
    clients: tuple[httpx.AsyncClient, httpx.AsyncClient],
    books: dict[str, uuid.UUID],
    summary_generator: FakeSummaryGenerator,
) -> None:
    alice, ben = clients
    first = await post_draft(alice, books["storm"], regenerate=False)
    assert left(first) == 9 and "drafted earlier" not in first
    again = await post_draft(alice, books["storm"], regenerate=False)
    assert left(again) == 9  # no AI request, so nothing counted
    assert draft_id(again) == draft_id(first)
    assert "It was drafted earlier, on 23 Nov 2026." in again
    bens = await post_draft(ben, books["copy"], regenerate=False)  # same title and author
    assert draft_id(bens) == draft_id(first) and left(bens) == 10
    assert len(summary_generator.calls) == 1


@pytest.mark.ac("012/AC-15")
async def test_drafts_expire_after_30_days(
    factory: Factory,
    clients: tuple[httpx.AsyncClient, httpx.AsyncClient],
    books: dict[str, uuid.UUID],
    summary_generator: FakeSummaryGenerator,
) -> None:
    alice, _ = clients
    await post_draft(alice, books["storm"], regenerate=False)
    await factory.execute(  # moving the clock 30 days would end the sign-in session too
        "UPDATE summary_draft SET created_at = created_at - interval '30 days 1 second'"
    )
    await post_draft(alice, books["storm"], regenerate=False)
    assert len(summary_generator.calls) == 2


@pytest.mark.ac("012/AC-16")
async def test_regenerate_bypasses_the_cache_and_counts(
    app: Any,
    clients: tuple[httpx.AsyncClient, httpx.AsyncClient],
    books: dict[str, uuid.UUID],
    factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:
    alice, ben = clients
    first = await post_draft(alice, books["storm"], regenerate=False)
    app.state.clock = lambda: NOON + timedelta(minutes=5)
    summary_generator.results.append(good_draft(text=OTHER_TEXT))
    second = await post_draft(ben, books["storm"], regenerate=True)
    assert textarea(second) == OTHER_TEXT and left(second) == 9
    assert draft_id(second) != draft_id(first)
    latest = await post_draft(alice, books["storm"], regenerate=False)
    assert draft_id(latest) == draft_id(second)  # the new draft replaces the cached one
    # Alice was still reviewing the first draft: it saves as hers, unedited.
    await save(alice, books["storm"], DRAFT_TEXT, draft_id(first))
    assert await factory.scalar("SELECT origin FROM book_summary WHERE is_current") == "ai"


@pytest.mark.ac("012/AC-17")
async def test_changed_details_get_no_old_draft(
    clients: tuple[httpx.AsyncClient, httpx.AsyncClient],
    books: dict[str, uuid.UUID],
    factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:
    alice, _ = clients
    old = await post_draft(alice, books["storm"], regenerate=False)
    await factory.execute("UPDATE book SET title = 'Storm Front (Revised)' WHERE id = :b",
                          b=books["storm"])  # fmt: skip
    fresh = await post_draft(alice, books["storm"], regenerate=False)
    assert draft_id(fresh) != draft_id(old)
    assert len(summary_generator.calls) == 2
    await save(alice, books["storm"], DRAFT_TEXT, draft_id(old))  # the old details' draft
    assert await factory.scalar("SELECT origin FROM book_summary WHERE is_current") == "manual"
    await factory.execute("UPDATE book SET isbn_13 = '9780451457813' WHERE id = :b",
                          b=books["storm"])  # fmt: skip
    with_isbn = await post_draft(alice, books["storm"], regenerate=False)
    assert len(summary_generator.calls) == 3
    # With an ISBN, fixing the title still means a new draft (PR #32 review).
    await factory.execute("UPDATE book SET title = 'Storm Front' WHERE id = :b", b=books["storm"])
    fixed = await post_draft(alice, books["storm"], regenerate=False)
    assert draft_id(fixed) != draft_id(with_isbn)
    assert len(summary_generator.calls) == 4


@pytest.mark.ac("012/AC-18")
async def test_drafts_are_never_shown_as_summaries(
    clients: tuple[httpx.AsyncClient, httpx.AsyncClient],
    books: dict[str, uuid.UUID],
    factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:
    alice, ben = clients
    await post_draft(alice, books["storm"], regenerate=False)
    owner_entry = await factory.entry(await factory.user("carol"), books["storm"])
    assert owner_entry
    for client in (alice, ben):
        for path in (f"/catalog/books/{books['storm']}/summary", "/catalog", "/",
                     f"/catalog/books/{books['storm']}/edit"):  # fmt: skip
            assert DRAFT_TEXT not in (await client.get(path)).text, path
        api = (await client.get(f"/api/v1/books/{books['storm']}")).json()
        assert api["current_summary"] is None
