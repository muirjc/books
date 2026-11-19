"""The Open Library adapter against recorded responses (spec 002; research R2-R4, R6, R9, R14).

Responses are replayed with ``httpx.MockTransport``; nothing here contacts Open Library
(Principle V). Fixtures come from ``scripts/record_open_library_fixtures.py``.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.domain.imports import AuthorCandidate
from book_tracker.services.errors import SourceNotFound, SourceUnavailable
from book_tracker.sources.open_library import (
    WORKS_PAGE_SIZE,
    OpenLibrarySource,
    make_client,
    user_agent,
)
from book_tracker.sources.rate_limit import RateLimiter

FIXTURES = Path(__file__).parent / "fixtures" / "open_library"
BASE = "https://openlibrary.test"
ALLOWED_PARAMS = {"q", "author_key", "fields", "limit", "page"}

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return data


class Recorder:
    """Serves fixtures by request and keeps every request for inspection."""

    def __init__(self, routes: dict[tuple[str, str], str | int]) -> None:
        self.routes = routes  # (path, author_key or q or "page2") -> fixture name or status
        self.requests: list[httpx.Request] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = request.url.params
        key = params.get("author_key") or params.get("q") or ""
        if params.get("page") == "2":
            key += ":2"
        target = self.routes.get((request.url.path, key))
        if target is None:
            return httpx.Response(404)
        if isinstance(target, int):
            return httpx.Response(target)
        return httpx.Response(200, json=fixture(target))


def source(handler: Handler, *, budget: float = 10.0) -> OpenLibrarySource:
    client = make_client(BASE, transport=httpx.MockTransport(handler))
    no_wait = RateLimiter(min_interval=0.0)
    return OpenLibrarySource(client, timeout_seconds=budget, limiter=no_wait)


SANDERSON = "OL1394865A"
WORKS = ("/search.json", SANDERSON)
SEARCH = ("/search/authors.json", "Brandon Sanderson")


async def test_author_search_parses_candidates() -> None:
    recorder = Recorder({SEARCH: "authors_brandon_sanderson.json"})
    authors = await source(recorder).search_authors("Brandon Sanderson")
    assert len(authors) == 2
    first = authors[0]
    assert first.source_id == SANDERSON
    assert first.name == "Brandon Sanderson"
    assert first.work_count > 200
    assert first.top_work
    assert first.birth_date


async def test_author_search_with_no_match() -> None:
    recorder = Recorder({("/search/authors.json", "zzqx qqzz"): "authors_none.json"})
    assert await source(recorder).search_authors("zzqx qqzz") == []


async def test_works_list_parses_and_converts_isbns() -> None:
    recorder = Recorder({WORKS: "works_OL1394865A.json"})
    result = await source(recorder).author_works(SANDERSON)
    assert result.total == fixture("works_OL1394865A.json")["numFound"]
    assert not result.truncated
    assert len(result.works) <= result.total
    assert result.author.name == "Brandon Sanderson"  # from the works response (research R3)
    assert result.author.work_count == result.total
    final_empire = next(w for w in result.works if w.title == "The Final Empire")
    assert final_empire.source_id.startswith("OL") and final_empire.source_id.endswith("W")
    assert final_empire.first_publish_year is not None
    assert all(len(i) == 13 and i.isdigit() for i in final_empire.isbn13s)
    assert final_empire.isbn13s  # ISBN-10s were converted


async def test_author_details_from_search_are_kept() -> None:
    recorder = Recorder({WORKS: "works_OL1394865A.json"})
    known = AuthorCandidate(SANDERSON, "Brandon Sanderson", "19 December 1975", None,
                            "The Final Empire", 238)  # fmt: skip
    result = await source(recorder).author_works(SANDERSON, author=known)
    assert result.author == known


async def test_duplicate_works_are_merged() -> None:
    recorder = Recorder({("/search.json", "OL9000001A"): "works_duplicates.json"})
    result = await source(recorder).author_works("OL9000001A")
    titles = sorted(w.title for w in result.works)
    assert titles == ["Another Story", "Hidden Door"]
    hidden = next(w for w in result.works if w.title == "Hidden Door")
    assert hidden.source_id == "OL102W" and hidden.alias_ids == ("OL101W",)


async def test_malformed_works_are_dropped() -> None:
    recorder = Recorder({("/search.json", "OL9000001A"): "works_malformed.json"})
    result = await source(recorder).author_works("OL9000001A")
    assert [w.title for w in result.works] == ["A Good One"]


async def test_works_and_authors_with_bad_ids_are_dropped() -> None:
    """One odd id never stops an import: it is dropped, not stored (review finding 4)."""
    recorder = Recorder({
        ("/search.json", "OL9000001A"): "works_bad_keys.json",
        ("/search/authors.json", "Odd"): "authors_bad_keys.json",
    })  # fmt: skip
    works = await source(recorder).author_works("OL9000001A")
    assert [w.source_id for w in works.works] == ["OL301W"]
    authors = await source(recorder).search_authors("Odd")
    assert [a.source_id for a in authors] == ["OL31353A"]


async def test_control_characters_from_the_site_are_removed() -> None:
    recorder = Recorder({
        ("/search.json", "OL9000001A"): "works_control_chars.json",
        ("/search/authors.json", "Odd"): "authors_control_chars.json",
    })  # fmt: skip
    work = (await source(recorder).author_works("OL9000001A")).works[0]
    assert work.title == "Nul Title" and work.author_names == ("Prolific Writer",)
    found = (await source(recorder).search_authors("Odd"))[0]
    assert "\x00" not in f"{found.name}{found.birth_date}{found.death_date}{found.top_work}"


async def test_repeated_author_is_listed_once() -> None:
    recorder = Recorder({("/search.json", "OL9000001A"): "works_repeated_author.json"})
    result = await source(recorder).author_works("OL9000001A")
    assert result.works[0].author_names == ("Prolific Writer", "Co Author")


async def test_long_values_are_cut_to_fit_the_catalog() -> None:
    recorder = Recorder({("/search.json", "OL9000001A"): "works_long_values.json"})
    work = (await source(recorder).author_works("OL9000001A")).works[0]
    assert len(work.title) <= 300 and work.title.endswith("…")
    assert all(len(n) <= 200 for n in work.author_names)


async def test_large_lists_stop_after_two_pages() -> None:
    recorder = Recorder({
        ("/search.json", "OL9000001A"): "works_large_page1.json",
        ("/search.json", "OL9000001A:2"): "works_large_page2.json",
    })  # fmt: skip
    result = await source(recorder).author_works("OL9000001A")
    assert result.total == 2500
    assert result.truncated
    assert len(result.works) == 2 * WORKS_PAGE_SIZE
    assert len(recorder.requests) == 2


async def test_unknown_author_key() -> None:
    recorder = Recorder({("/search.json", "OL9999999A"): "works_unknown_author.json"})
    with pytest.raises(SourceNotFound):
        await source(recorder).author_works("OL9999999A")


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_errors_from_the_site(status: int) -> None:
    recorder = Recorder({WORKS: status})
    with pytest.raises(SourceUnavailable):
        await source(recorder).author_works(SANDERSON)


async def test_connection_error() -> None:
    async def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(SourceUnavailable):
        await source(refuse).search_authors("anyone")


async def test_slow_site_times_out_within_the_budget() -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json=fixture("authors_none.json"))

    started = time.monotonic()
    with pytest.raises(SourceUnavailable):
        await source(slow, budget=0.1).search_authors("anyone")
    assert time.monotonic() - started < 0.5


async def test_second_page_past_the_budget_fails() -> None:
    """The 10 s budget covers the whole member request, not each call (research R9)."""
    calls = 0

    async def slow_second(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 2:
            await asyncio.sleep(1)
        name = "works_large_page1.json" if calls == 1 else "works_large_page2.json"
        return httpx.Response(200, json=fixture(name))

    with pytest.raises(SourceUnavailable):
        await source(slow_second, budget=0.3).author_works("OL9000001A")


async def test_requests_carry_nothing_but_the_query() -> None:
    """FR-015, FR-018, SC-005: app-only User-Agent, no cookies or other identity."""
    recorder = Recorder({
        ("/search/authors.json", "Brandon Sanderson"): "authors_brandon_sanderson.json",
        WORKS: "works_OL1394865A.json",
    })  # fmt: skip
    ol = source(recorder)
    await ol.search_authors("Brandon Sanderson")
    await ol.author_works(SANDERSON)
    assert recorder.requests
    for request in recorder.requests:
        assert str(request.url).startswith(BASE + "/")
        assert set(request.url.params.keys()) <= ALLOWED_PARAMS
        assert request.headers["user-agent"] == user_agent()
        assert user_agent().startswith("FamilyBookTracker/")
        assert "(" not in user_agent()  # no contact address (Principle IX)
        for header in ("cookie", "from", "referer", "authorization"):
            assert header not in request.headers


async def test_full_import_sends_nothing_personal(settings: Any, app: Any, factory: Any) -> None:
    """SC-005, FR-015, research R8: through the real adapter, a member's import sends only
    the author name and keys; confirming sends nothing at all."""
    from book_tracker.main import create_app
    from tests.conftest import make_client as asgi_client
    from tests.conftest import signed_in

    recorder = Recorder({
        ("/search/authors.json", "Ursula K. Le Guin"): "authors_single.json",
        ("/search.json", "OL31353A"): "works_OL1394865A.json",
    })  # fmt: skip
    live = create_app(settings, book_source=source(recorder))
    member = await factory.user("privatekid", display_name="Private Kid")
    async with asgi_client(live) as client:
        await signed_in(client, member)
        await client.get("/api/v1/import/authors", params={"q": "Ursula K. Le Guin"})
        author_key = fixture("authors_single.json")["docs"][0]["key"]
        recorder.routes[("/search.json", author_key)] = "works_OL1394865A.json"
        listed = await client.get(f"/api/v1/import/authors/{author_key}/works")
        assert listed.status_code == 200, listed.text
        before = len(recorder.requests)
        first = listed.json()["works"][0]["work_key"]
        done = await client.post(
            "/api/v1/me/imports", json={"author_key": author_key, "work_keys": [first]}
        )
        assert done.status_code == 201, done.text
        assert len(recorder.requests) == before  # confirm made no request
        session_cookie = client.cookies.get("__Host-session") or ""
    assert recorder.requests
    for request in recorder.requests:
        sent = str(request.url) + " " + " ".join(f"{k}: {v}" for k, v in request.headers.items())
        for secret in ("privatekid", "Private Kid", str(member.id), session_cookie or "-"):
            assert secret not in sent
