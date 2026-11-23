"""Spec 012 research R3: Open Library's description of one book, from recorded responses.

Responses are replayed with ``httpx.MockTransport``; nothing here contacts Open Library
(Principle V). Fixtures were recorded with the app's User-Agent, sending only the ISBN,
title and author.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from book_tracker.services.errors import SourceUnavailable
from book_tracker.sources.open_library import OpenLibrarySource, make_client
from book_tracker.sources.rate_limit import RateLimiter

FIXTURES = Path(__file__).parent / "fixtures" / "open_library"
BASE = "https://openlibrary.test"
ISBN = "9780451457813"


class Routes:
    def __init__(self, routes: dict[tuple[str, str], str | int]) -> None:
        self.routes = routes  # (path, isbn or title) -> fixture or status
        self.requests: list[httpx.Request] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = request.url.params
        target = self.routes.get((request.url.path, params.get("isbn") or params.get("title", "")))
        if target is None:
            return httpx.Response(404)
        if isinstance(target, int):
            return httpx.Response(target)
        body = (FIXTURES / target).read_bytes()
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})


def source(routes: Routes) -> OpenLibrarySource:
    client = make_client(BASE, transport=httpx.MockTransport(routes))
    return OpenLibrarySource(client, limiter=RateLimiter(min_interval=0.0))


STORM_WORK = ("/works/OL5685119W.json", "")


async def test_by_isbn() -> None:
    routes = Routes({
        ("/search.json", ISBN): "describe_search_isbn.json",
        STORM_WORK: "describe_work_OL5685119W.json",
    })  # fmt: skip
    found = await source(routes).describe_book("Storm Front", ["Jim Butcher"], ISBN)
    assert found is not None
    assert found.work_url == f"{BASE}/works/OL5685119W"
    assert found.description.startswith("The novels of the Dresden Files")
    search = routes.requests[0].url.params
    assert dict(search) == {"isbn": ISBN, "limit": "1", "fields": "key"}  # metadata only


async def test_by_title_and_author_when_no_isbn_match() -> None:
    routes = Routes({
        ("/search.json", ISBN): "authors_none.json",  # {"numFound": 0, "docs": []}
        ("/search.json", "Storm Front"): "describe_search_title.json",
        STORM_WORK: "describe_work_OL5685119W.json",
    })  # fmt: skip
    found = await source(routes).describe_book("Storm Front", ["Jim Butcher", "X"], ISBN)
    assert found is not None and found.work_url.endswith("/works/OL5685119W")
    title_search = routes.requests[1].url.params
    assert title_search["title"] == "Storm Front" and title_search["author"] == "Jim Butcher"


async def test_description_object_form() -> None:
    routes = Routes({
        ("/search.json", "The Lord of the Rings"): "describe_search_lotr.json",
        ("/works/OL27448W.json", ""): "describe_work_OL27448W.json",
    })  # fmt: skip
    found = await source(routes).describe_book("The Lord of the Rings", ["J.R.R. Tolkien"], None)
    assert found is not None and found.description.startswith("Originally published")


async def test_nothing_found() -> None:
    routes = Routes({("/search.json", "Zzqx"): "authors_none.json"})
    assert await source(routes).describe_book("Zzqx", ["Nobody"], None) is None


async def test_work_without_description() -> None:
    routes = Routes({
        ("/search.json", "Bare"): "describe_search_bare.json",
        ("/works/OL1W.json", ""): "describe_work_bare.json",
    })  # fmt: skip
    assert await source(routes).describe_book("Bare", ["Ann"], None) is None


async def test_long_description_is_cut() -> None:
    routes = Routes({
        ("/search.json", "Long"): "describe_search_bare.json",
        ("/works/OL1W.json", ""): "describe_work_long.json",
    })  # fmt: skip
    found = await source(routes).describe_book("Long", ["Ann"], None)
    assert found is not None and len(found.description) <= 4000
    assert found.description.endswith("…")


async def test_odd_work_key_is_ignored() -> None:
    routes = Routes({("/search.json", "Odd"): "describe_search_odd.json"})
    assert await source(routes).describe_book("Odd", ["Ann"], None) is None
    assert len(routes.requests) == 1  # never fetched


@pytest.mark.parametrize("status", [500, 503])
async def test_open_library_down_raises(status: int) -> None:
    routes = Routes({("/search.json", "Storm Front"): status})
    with pytest.raises(SourceUnavailable):
        await source(routes).describe_book("Storm Front", ["Jim Butcher"], None)
