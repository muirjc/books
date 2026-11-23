"""Spec 012 User Story 6: summary drafts in the JSON API match the contract."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from book_tracker.services.errors import AiDeclined, AiUnavailable
from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract
from tests.fakes import DRAFT_TEXT, WIKI, FakeSummaryGenerator, good_draft


@pytest.fixture(autouse=True)
def _pinned_clock(app: Any) -> None:
    app.state.clock = lambda: datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
async def api(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), await factory.user("alice"))


@pytest.fixture
async def book(factory: Factory) -> uuid.UUID:
    owner = await factory.user("owner")
    return await factory.book(
        "Fool Moon", owner, author_ids=[await factory.author("Jim Butcher", owner)]
    )


def drafts_url(book: uuid.UUID) -> str:
    return f"/api/v1/books/{book}/summary-drafts"


@pytest.mark.ac("012/AC-24")
@pytest.mark.ac("012/AC-26")
async def test_draft_cache_and_regenerate(
    api: httpx.AsyncClient, book: uuid.UUID, factory: Factory,
    summary_generator: FakeSummaryGenerator,
) -> None:  # fmt: skip
    summary_generator.results.append(good_draft(series_name="The Dresden Files", series_number="2"))
    first = await api.post(drafts_url(book), json={})
    assert first.status_code == 200, first.text
    assert_matches_contract(first)
    body = first.json()
    assert body["text"] == DRAFT_TEXT and body["source_urls"] == [WIKI]
    assert body["model"] == "claude-opus-5-5" and body["cached"] is False
    assert body["series_suggestion"] == {"name": "The Dresden Files", "number": "2"}
    assert body["drafts_left_today"] == 9
    assert await factory.scalar("SELECT count(*) FROM book_summary") == 0  # nothing saved
    again = (await api.post(drafts_url(book), json={})).json()
    assert again["id"] == body["id"] and again["cached"] is True
    assert again["drafts_left_today"] == 9
    fresh = await api.post(drafts_url(book), json={"regenerate": True})
    assert_matches_contract(fresh)
    assert fresh.json()["id"] != body["id"] and fresh.json()["drafts_left_today"] == 8
    assert fresh.json()["series_suggestion"] is None


@pytest.mark.ac("012/AC-24")
@pytest.mark.parametrize(
    ("result", "status", "code"),
    [
        (AiUnavailable(), 503, "ai_unavailable"),
        (AiDeclined(), 422, "ai_declined"),
        (good_draft(status="not_enough_information", text=""), 422, "not_enough_information"),
        (good_draft(text="Far too short."), 422, "draft_rejected"),
    ],
)
async def test_failures(
    api: httpx.AsyncClient, book: uuid.UUID, summary_generator: FakeSummaryGenerator,
    result: Any, status: int, code: str,
) -> None:  # fmt: skip
    summary_generator.results.append(result)
    response = await api.post(drafts_url(book), json={})
    assert response.status_code == status
    assert response.json()["code"] == code
    assert_matches_contract(response)
    # The failed request still counted (AC-10), although the API request was rolled back.
    after = (await api.post(drafts_url(book), json={"regenerate": True})).json()
    assert after["drafts_left_today"] == 8


@pytest.mark.ac("012/AC-24")
async def test_not_configured_limit_and_unknown_book(
    app: Any, api: httpx.AsyncClient, book: uuid.UUID,
    summary_generator: FakeSummaryGenerator, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    summary_generator.configured = False
    off = await api.post(drafts_url(book), json={})
    assert off.status_code == 503 and off.json()["code"] == "ai_not_configured"
    assert_matches_contract(off)
    summary_generator.configured = True
    monkeypatch.setattr(app.state.settings, "ai_daily_draft_limit", 1)
    assert (await api.post(drafts_url(book), json={})).status_code == 200
    limited = await api.post(drafts_url(book), json={"regenerate": True})
    assert limited.status_code == 429 and limited.json()["code"] == "draft_limit_reached"
    assert_matches_contract(limited)
    cached = await api.post(drafts_url(book), json={})  # the cache still answers
    assert cached.status_code == 200 and cached.json()["drafts_left_today"] == 0
    missing = await api.post(drafts_url(uuid.uuid4()), json={})
    assert missing.status_code == 404
    assert_matches_contract(missing)
    extra = await api.post(drafts_url(book), json={"regenerate": False, "x": 1})
    assert extra.status_code == 422
    wrong = await api.post(drafts_url(book), json={}, headers={"X-CSRF-Token": "wrong"})
    assert wrong.status_code == 403


@pytest.mark.ac("012/AC-25")
@pytest.mark.ac("012/AC-26")
async def test_save_with_a_draft_id(
    api: httpx.AsyncClient, book: uuid.UUID, summary_generator: FakeSummaryGenerator
) -> None:
    draft = (await api.post(drafts_url(book), json={})).json()
    url = f"/api/v1/books/{book}/summaries"
    saved = await api.post(url, json={"text": DRAFT_TEXT, "draft_id": draft["id"]})
    assert saved.status_code == 201
    assert_matches_contract(saved)
    assert saved.json()["origin"] == "ai" and saved.json()["source_urls"] == [WIKI]
    assert saved.json()["model"] == "claude-opus-5-5"
    edited = await api.post(url, json={"text": "Mine: " + DRAFT_TEXT, "draft_id": draft["id"]})
    assert edited.json()["origin"] == "ai_edited"
    unknown = await api.post(url, json={"text": DRAFT_TEXT, "draft_id": str(uuid.uuid4())})
    assert unknown.json()["origin"] == "manual" and unknown.json()["model"] is None
    plain = await api.post(url, json={"text": "Hand-written."})
    assert plain.status_code == 201 and plain.json()["origin"] == "manual"
