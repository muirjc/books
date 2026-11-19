"""Import performance budgets (spec 002 SC-002, SC-006; marker ``perf``; task T047).

The works list is measured with a warm cache against the 5,000-book seed. The confirm runs
are a stand-in for the Pi: CI is faster, so the CI limits are tighter than the Pi's
(200 books: 5 s here, 10 s on the Pi; 500: 12 s here, 25 s on the Pi).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.fakes import FakeBookSource, listing, work
from tests.perf.test_list_performance import SEED, p95

pytestmark = pytest.mark.perf
KEY = "OL1A"


@pytest.fixture
async def reader(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    user = await factory.user("reader")
    for statement in SEED:
        await factory.execute(statement, u=user.id)
    await factory.execute("ANALYZE")
    return await signed_in(client_factory(), user)


@pytest.mark.ac("002/AC-01")
async def test_works_list_from_cache_under_one_second(
    reader: httpx.AsyncClient, book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [work(n, f"Work {n}") for n in range(1, 301)])
    warm = await reader.get(f"/api/v1/import/authors/{KEY}/works")
    assert warm.status_code == 200
    page = await p95(lambda i: reader.get(f"/import/authors/{KEY}"), runs=30)
    api = await p95(lambda i: reader.get(f"/api/v1/import/authors/{KEY}/works"), runs=30)
    print(f"\nworks page p95 {page * 1000:.0f} ms; API p95 {api * 1000:.0f} ms")
    assert page < 1.0 and api < 1.0
    assert book_source.calls == [("author_works", KEY)]  # one fetch; the rest were cached


async def _timed_confirm(app: Any, reader: httpx.AsyncClient, count: int) -> float:
    await reader.get(f"/api/v1/import/authors/{KEY}/works")
    started = time.perf_counter()
    response = await reader.post(
        "/api/v1/me/imports",
        json={"author_key": KEY, "work_keys": [f"OL{n}W" for n in range(1, count + 1)]},
    )
    elapsed = time.perf_counter() - started
    assert response.status_code == 201, response.text
    assert len(response.json()["added"]) == count
    return elapsed


@pytest.mark.ac("002/AC-02")
async def test_confirming_200_and_500_new_books(
    app: Any, reader: httpx.AsyncClient, book_source: FakeBookSource, factory: Factory
) -> None:
    works = [work(n, f"New {n}", (f"Writer {n % 40}",)) for n in range(1, 501)]
    book_source.works[KEY] = listing(KEY, works)
    two_hundred = await _timed_confirm(app, reader, 200)
    await factory.execute("DELETE FROM reading_entry WHERE book_id IN "
                          "(SELECT book_id FROM book_source_ref)")  # fmt: skip
    await factory.execute("DELETE FROM book_source_ref")
    await factory.execute("DELETE FROM book_author WHERE book_id IN "
                          "(SELECT id FROM book WHERE title LIKE 'New %')")  # fmt: skip
    await factory.execute("DELETE FROM book WHERE title LIKE 'New %'")
    five_hundred = await _timed_confirm(app, reader, 500)
    print(f"\nconfirm 200: {two_hundred:.2f} s; confirm 500: {five_hundred:.2f} s")
    assert two_hundred < 5.0
    assert five_hundred < 12.0
