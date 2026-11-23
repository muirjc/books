"""Spec 012 User Story 4: a draft's series suggestion, applied only through Edit book."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.fakes import DRAFT_TEXT, FakeSummaryGenerator, good_draft
from tests.integration.test_draft_failures import post_draft
from tests.integration.test_summary_drafts import csrf, draft_id

NOTICE = "Series and number suggested by the AI. Check them, then save."


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
async def member(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), await factory.user("alice", display_name="Alice"))


@pytest.fixture
async def books(factory: Factory) -> dict[str, uuid.UUID]:
    owner = await factory.user("owner")
    butcher = await factory.author("Jim Butcher", owner)
    dresden = await factory.series("The Dresden Files", owner)
    return {
        "fool": await factory.book("Fool Moon", owner, author_ids=[butcher]),
        "storm": await factory.book("Storm Front", owner, author_ids=[butcher],
                                    series_id=dresden, series_number="1"),
    }  # fmt: skip


def suggestion(name: str | None, number: str | None) -> Any:
    return good_draft(series_name=name, series_number=number)


@pytest.mark.ac("012/AC-19")
@pytest.mark.parametrize(
    ("name", "number", "shown"),
    [
        ("The Dresden Files", "2", "Looks like The Dresden Files #2"),
        ("The Dresden Files", None, "Looks like The Dresden Files"),
        ("The Dresden Files", "two", "Looks like The Dresden Files"),  # unreadable number
        (None, None, None),
    ],
)
async def test_hint_for_a_book_without_a_series(
    member: httpx.AsyncClient, books: dict[str, uuid.UUID],
    summary_generator: FakeSummaryGenerator, name: str | None, number: str | None,
    shown: str | None,
) -> None:  # fmt: skip
    summary_generator.results.append(suggestion(name, number))
    page = await post_draft(member, books["fool"])
    if shown is None:
        assert "Looks like" not in page and "Use this series" not in page
    else:
        hint = re.search(r'<p class="series-hint">(.*?)</p>', page, re.S)
        assert hint and html.unescape(re.sub(r"<[^>]+>", "", hint.group(1))).strip() == shown
        assert ">Use this series</button>" in page


@pytest.mark.ac("012/AC-19")
async def test_no_hint_when_it_matches_the_book(
    member: httpx.AsyncClient, books: dict[str, uuid.UUID],
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    summary_generator.results.append(suggestion("the dresden files", "1"))
    assert "Looks like" not in await post_draft(member, books["storm"])
    summary_generator.results.append(suggestion("The Dresden Files", "1.5"))
    assert "Looks like The Dresden Files #1.5" in await post_draft(member, books["storm"])


async def use_series(member: httpx.AsyncClient, book: uuid.UUID, page: str, text: str) -> str:
    response = await member.post(
        f"/catalog/books/{book}/summary/use-series",
        data={"csrf_token": csrf(page), "text": text, "draft_id": draft_id(page)},
    )
    assert response.status_code == 200
    return response.text


@pytest.mark.ac("012/AC-21")
async def test_unsaved_draft_is_mentioned_first(
    member: httpx.AsyncClient, books: dict[str, uuid.UUID], factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    summary_generator.results.append(suggestion("The Dresden Files", "2"))
    page = await post_draft(member, books["fool"])
    edited = DRAFT_TEXT + " Edited."
    confirm = await use_series(member, books["fool"], page, edited)
    assert "Your AI draft isn't saved yet." in confirm
    assert ">Save summary first</button>" in confirm
    assert f'value="{draft_id(page)}"' in confirm and html.escape(edited) in confirm
    leave = re.search(r'<a href="([^"]+)">Leave the draft</a>', confirm)
    assert leave
    edit_url = f"/catalog/books/{books['fool']}/edit?suggest_draft={draft_id(page)}"
    assert html.unescape(leave.group(1)) == edit_url
    # Save summary first: the edited text is saved, then Edit book opens with the suggestion.
    saved = await member.post(
        f"/catalog/books/{books['fool']}/summary",
        data={"csrf_token": csrf(confirm), "text": edited, "draft_id": draft_id(page),
              "then": "series"},
    )  # fmt: skip
    assert saved.status_code == 303 and saved.headers["location"] == edit_url
    assert await factory.scalar("SELECT origin FROM book_summary WHERE is_current") == "ai_edited"
    assert len(summary_generator.calls) == 1
    again = await post_draft(member, books["fool"], regenerate=False)
    assert draft_id(again) == draft_id(page)  # still cached: no allowance spent
    assert len(summary_generator.calls) == 1


async def drafted(
    member: httpx.AsyncClient, book: uuid.UUID, summary_generator: FakeSummaryGenerator,
    name: str, number: str | None,
) -> str:  # fmt: skip
    summary_generator.results.append(suggestion(name, number))
    return draft_id(await post_draft(member, book))


@pytest.mark.ac("012/AC-20")
async def test_edit_book_is_filled_in_but_not_saved(
    member: httpx.AsyncClient, books: dict[str, uuid.UUID], factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    draft = await drafted(member, books["fool"], summary_generator, "The Dresden Files", "2")
    page = (await member.get(f"/catalog/books/{books['fool']}/edit?suggest_draft={draft}")).text
    assert NOTICE in page
    assert re.search(r'id="series_name"[^>]*value="The Dresden Files"', page)
    assert re.search(r'id="series_number"[^>]*value="2"', page)
    assert await factory.scalar("SELECT series_id FROM book WHERE id = :b", b=books["fool"]) is None
    plain = (await member.get(f"/catalog/books/{books['fool']}/edit")).text
    assert NOTICE not in plain


@pytest.mark.ac("012/AC-20")
async def test_only_a_stored_draft_for_this_book_is_a_suggestion(
    member: httpx.AsyncClient, books: dict[str, uuid.UUID], factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    """PR #32 review: a crafted link, another book's draft or an expired one suggests nothing."""
    fool = books["fool"]
    crafted = (await member.get(f"/catalog/books/{fool}/edit?suggest_series=Wrong+Series"
                                "&suggest_number=9")).text  # fmt: skip
    assert NOTICE not in crafted and "Wrong Series" not in crafted
    storms = await drafted(member, books["storm"], summary_generator, "Codex Alera", "1")
    other = (await member.get(f"/catalog/books/{fool}/edit?suggest_draft={storms}")).text
    assert NOTICE not in other and "Codex Alera" not in other
    page = await post_draft(member, fool, regenerate=False)  # no draft for Fool Moon yet
    mismatch = await member.post(
        f"/catalog/books/{fool}/summary/use-series",
        data={"csrf_token": csrf(page), "text": "x", "draft_id": storms},
    )
    assert mismatch.status_code == 303
    assert mismatch.headers["location"] == f"/catalog/books/{fool}/summary"
    fools = await drafted(member, fool, summary_generator, "The Dresden Files", "2")
    await factory.execute(
        "UPDATE summary_draft SET created_at = created_at - interval '31 days' WHERE id = :d",
        d=uuid.UUID(fools),
    )
    expired = (await member.get(f"/catalog/books/{fool}/edit?suggest_draft={fools}")).text
    assert NOTICE not in expired


@pytest.mark.ac("012/AC-20")
async def test_saving_the_suggestion_uses_the_existing_checks(
    member: httpx.AsyncClient, books: dict[str, uuid.UUID], factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    draft = await drafted(member, books["fool"], summary_generator, "The Dresden Files", "1")
    page = (await member.get(f"/catalog/books/{books['fool']}/edit?suggest_draft={draft}")).text
    form = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    form = {k: html.unescape(v) for k, v in form.items()}
    response = await member.post(f"/catalog/books/{books['fool']}/edit", data=form)
    # #1 is Storm Front's: the existing series-number conflict applies (spec 001).
    assert response.status_code == 409
    assert await factory.scalar("SELECT series_id FROM book WHERE id = :b", b=books["fool"]) is None
