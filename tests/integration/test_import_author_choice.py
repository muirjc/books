"""Choosing between authors who share a name (spec 002 user story 2; T037, T038)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from book_tracker.domain.imports import AuthorCandidate
from tests.conftest import Factory
from tests.fakes import FakeBookSource, listing, work
from tests.integration.import_helpers import member


def _two_sandersons(ol: FakeBookSource) -> None:
    ol.authors["brandon sanderson"] = [
        AuthorCandidate("OL1394865A", "Brandon Sanderson", "19 December 1975", None,
                        "The Final Empire", 238),
        AuthorCandidate("OL16029248A", "Brandon Sanderson", None, None, "Wind and Truth", 14),
    ]  # fmt: skip
    ol.works["OL1394865A"] = listing("OL1394865A", [work(1, "The Final Empire")])
    ol.works["OL16029248A"] = listing("OL16029248A", [work(2, "Wind and Truth")])


@pytest.mark.ac("002/AC-08")
async def test_several_matches_are_listed_with_details(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _two_sandersons(book_source)
    _, client = await member(factory, client_factory, "alice")
    page = await client.get("/import/authors", params={"q": "Brandon Sanderson"})
    assert page.status_code == 200  # no redirect: the member must choose
    assert page.text.count("Brandon Sanderson</strong>") == 2
    assert "born 19 December 1975" in page.text
    assert "best known for <cite>The Final Empire</cite>" in page.text
    assert "238 works" in page.text and "14 works" in page.text
    assert 'href="/import/authors/OL1394865A"' in page.text
    assert 'href="/import/authors/OL16029248A"' in page.text

    chosen = await client.get("/import/authors/OL16029248A")
    assert "Wind and Truth" in chosen.text
    assert "The Final Empire" not in chosen.text
    assert "Books by Brandon Sanderson" in chosen.text  # the chosen author's details


@pytest.mark.ac("002/AC-08")
async def test_works_page_uses_the_chosen_authors_details(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _two_sandersons(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get("/import/authors", params={"q": "Brandon Sanderson"})
    api = await client.get("/api/v1/import/authors/OL1394865A/works")
    assert api.json()["author"]["birth_date"] == "19 December 1975"  # from the search (R3)


@pytest.mark.ac("002/AC-09")
async def test_no_match(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _, client = await member(factory, client_factory, "alice")
    page = await client.get("/import/authors", params={"q": "zzqx qqzz"})
    assert page.status_code == 200
    assert "No author found" in page.text
    assert 'href="/books/add"' in page.text
    api = await client.get("/api/v1/import/authors", params={"q": "zzqx qqzz"})
    assert api.json() == {"authors": []}
    assert await factory.scalar("SELECT count(*) FROM book") == 0


async def test_blank_search_asks_for_a_name(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _, client = await member(factory, client_factory, "alice")
    page = await client.get("/import/authors", params={"q": "   "})
    assert page.status_code == 422
    assert "Enter an author&#39;s name" in page.text or "Enter an author's name" in page.text
    assert book_source.calls == []
