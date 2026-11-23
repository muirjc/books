"""Spec 012 T009: the Claude summary generator against a mocked API (research R1, R2, R7).

Every response is replayed through ``httpx2.MockTransport``; nothing here contacts
Anthropic (Principle V).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import anthropic
import httpx2
import pytest

from book_tracker.domain.drafts import BLOCKED_DOMAINS, BookDescription, BookFacts
from book_tracker.services.errors import AiDeclined, AiUnavailable
from book_tracker.sources.claude import SUBMIT_TOOL, ClaudeSummaryGenerator

FACTS = BookFacts(
    title="Storm Front",
    authors=("Jim Butcher",),
    series_name="The Dresden Files",
    series_number=Decimal("1"),
    isbn13="9780451457813",
    release_year=2000,
)
DESCRIPTION = BookDescription("https://openlibrary.org/works/OL5685119W", "Harry Dresden…")
WIKI = "https://en.wikipedia.org/wiki/Storm_Front_(novel)"


def message(content: list[dict[str, Any]], stop: str = "tool_use",
            model: str = "claude-opus-5-5") -> dict[str, Any]:  # fmt: skip
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


SEARCH = [
    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search",
     "input": {"query": "Storm Front Jim Butcher"}},
    {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": [
        {"type": "web_search_result", "url": WIKI, "title": "Storm Front",
         "encrypted_content": "x", "page_age": None},
    ]},
    {"type": "text", "text": "Found it.", "citations": [
        {"type": "web_search_result_location", "url": WIKI, "title": "Storm Front",
         "encrypted_index": "e", "cited_text": "c"},
    ]},
]  # fmt: skip


def submit(**changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "status": "ok",
        "summary": "Harry Dresden, Chicago's only wizard for hire, takes a police case.",
        "source_urls": [WIKI, DESCRIPTION.work_url],
        "series_name": "The Dresden Files",
        "series_number": "1",
    }
    values.update(changes)
    return {"type": "tool_use", "id": "toolu_1", "name": SUBMIT_TOOL, "input": values}


class Api:
    """Replays responses in order and keeps every request body."""

    def __init__(self, *responses: dict[str, Any] | int | Callable[[], Any]) -> None:
        self.responses = list(responses)
        self.bodies: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []

    async def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        self.headers.append(dict(request.headers))
        item = self.responses.pop(0)
        if callable(item):
            return await item()  # type: ignore[no-any-return]  # test hook
        if isinstance(item, int):
            error = {"type": "error", "error": {"type": "x", "message": "x"}}
            return httpx2.Response(item, json=error)
        return httpx2.Response(200, json=item)


def generator(api: Api, timeout: float = 30.0) -> ClaudeSummaryGenerator:
    client = anthropic.AsyncAnthropic(
        api_key="test-key",
        base_url="http://anthropic.test",
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(api)),
        max_retries=0,
    )
    return ClaudeSummaryGenerator(client, model="claude-opus-5-5", timeout_seconds=timeout)


@pytest.mark.ac("012/AC-02")
async def test_request_shape_and_result() -> None:
    api = Api(message([*SEARCH, submit()]))
    draft = await generator(api).draft(FACTS, DESCRIPTION)
    assert draft.status == "ok"
    assert draft.text.startswith("Harry Dresden")
    assert draft.source_urls == (WIKI, DESCRIPTION.work_url)
    assert WIKI in draft.known_urls and DESCRIPTION.work_url in draft.known_urls
    assert draft.cited_urls == (WIKI,)
    assert (draft.series_name, draft.series_number) == ("The Dresden Files", "1")
    assert draft.model == "claude-opus-5-5"
    body = api.bodies[0]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in api.headers[0]["anthropic-beta"]
    search, tool = body["tools"]
    assert search["type"] == "web_search_20260209" and search["max_uses"] == 3
    assert set(search["blocked_domains"]) == set(BLOCKED_DOMAINS)
    assert tool["name"] == SUBMIT_TOOL and tool["strict"] is True
    assert tool["input_schema"]["additionalProperties"] is False
    assert "tool_choice" not in body or body["tool_choice"] == {"type": "auto"}
    assert "100" in body["system"] and "spoiler" in body["system"].lower()


@pytest.mark.ac("012/AC-09")
async def test_only_book_metadata_is_sent() -> None:
    """Principle IX: the request carries the book's facts and description, nothing else."""
    api = Api(message([submit()]))
    await generator(api).draft(FACTS, DESCRIPTION)
    body = api.bodies[0]
    assert set(body) <= {"model", "max_tokens", "system", "messages", "tools",
                         "output_config", "fallbacks"}  # fmt: skip
    (user,) = body["messages"]
    text = user["content"]
    for value in ("Storm Front", "Jim Butcher", "The Dresden Files", "9780451457813", "2000",
                  "Harry Dresden…", DESCRIPTION.work_url):  # fmt: skip
        assert value in text
    without = Api(message([submit()]))
    await generator(without).draft(BookFacts("Mort", ("Terry Pratchett",)), None)
    assert "Open Library" not in without.bodies[0]["messages"][0]["content"]


async def test_pause_turn_is_resumed() -> None:
    paused = message(SEARCH, stop="pause_turn")
    api = Api(paused, message([submit()]))
    draft = await generator(api).draft(FACTS, None)
    assert draft.status == "ok"
    second = api.bodies[1]["messages"]
    assert second[1]["role"] == "assistant"
    assert second[1]["content"][1]["type"] == "web_search_tool_result"
    assert WIKI in draft.known_urls  # results from the paused turn still count


async def test_served_by_fallback_model_is_recorded() -> None:
    api = Api(message([submit()], model="claude-opus-4-8"))
    assert (await generator(api).draft(FACTS, None)).model == "claude-opus-4-8"


async def test_not_enough_information() -> None:
    api = Api(message([submit(status="not_enough_information", summary="", source_urls=[],
                              series_name=None, series_number=None)]))  # fmt: skip
    draft = await generator(api).draft(FACTS, None)
    assert draft.status == "not_enough_information"
    assert draft.series_name is None and draft.series_number is None


@pytest.mark.ac("012/AC-09")
@pytest.mark.parametrize(
    "response",
    [
        message([{"type": "text", "text": "I can't."}], stop="refusal"),
        message([{"type": "text", "text": "Here is a summary."}], stop="end_turn"),
        message([submit(status="maybe")]),
    ],
)
async def test_declined(response: dict[str, Any]) -> None:
    with pytest.raises(AiDeclined):
        await generator(Api(response)).draft(FACTS, None)


@pytest.mark.ac("012/AC-09")
@pytest.mark.parametrize("status", [429, 500, 529, 401, 400])
async def test_api_errors_are_unavailable(status: int) -> None:
    with pytest.raises(AiUnavailable):
        await generator(Api(status)).draft(FACTS, None)


async def test_connection_error_is_unavailable() -> None:
    async def boom() -> Any:
        raise httpx2.ConnectError("down")

    with pytest.raises(AiUnavailable):
        await generator(Api(boom)).draft(FACTS, None)


@pytest.mark.ac("012/AC-09")
async def test_overall_deadline() -> None:
    async def slow() -> Any:
        await asyncio.sleep(5)
        return httpx2.Response(200, json=message([submit()]))

    with pytest.raises(AiUnavailable):
        await generator(Api(slow), timeout=0.2).draft(FACTS, None)


async def test_too_many_pauses() -> None:
    paused = message(SEARCH, stop="pause_turn")
    with pytest.raises(AiDeclined):
        await generator(Api(paused, paused, paused, paused, paused)).draft(FACTS, None)
