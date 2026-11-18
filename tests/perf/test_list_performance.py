"""T108: performance budgets with a full-size catalog (SC-002, SC-008; marker ``perf``).

Seeds 5,000 books, 1,500 authors, 300 series and 2,000 entries for one member, then
measures in-process request times: list pages p95 under 1 s, type-ahead p95 under 300 ms.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in

pytestmark = pytest.mark.perf

SEED = [
    """INSERT INTO author (id, name, sort_name, created_by, updated_by)
       SELECT gen_random_uuid(), 'Author ' || i, 'Author, ' || i, :u, :u
       FROM generate_series(1, 1500) AS i""",
    """INSERT INTO series (id, name, created_by, updated_by)
       SELECT gen_random_uuid(), 'Series ' || i, :u, :u FROM generate_series(1, 300) AS i""",
    """INSERT INTO book (id, title, series_id, series_number, created_by, updated_by)
       SELECT gen_random_uuid(), 'Book title ' || i,
              CASE WHEN i % 3 = 0 THEN s.id END,
              CASE WHEN i % 3 = 0 THEN ((i / 3) / 300) + 1 END, :u, :u
       FROM generate_series(1, 5000) AS i
       LEFT JOIN LATERAL (SELECT id FROM series ORDER BY name OFFSET ((i / 3) % 300) LIMIT 1) s
         ON true""",
    """INSERT INTO book_author (book_id, author_id, position)
       SELECT b.id, a.id, 1
       FROM (SELECT id, row_number() OVER (ORDER BY title) AS n FROM book) b
       JOIN (SELECT id, row_number() OVER (ORDER BY name) AS n FROM author) a
         ON a.n = (b.n % 1500) + 1""",
    """INSERT INTO reading_entry (id, user_id, book_id, status, times_read, finished_on, notes)
       SELECT gen_random_uuid(), :u, id,
              (ARRAY['finished', 'reading', 'want_to_read'])[1 + (n % 3)],
              CASE WHEN n % 3 = 0 THEN 1 ELSE 0 END,
              CASE WHEN n % 3 = 0 THEN DATE '2020-01-01' + (n % 1500)::int END,
              CASE WHEN n % 5 = 0 THEN 'A note' END
       FROM (SELECT id, row_number() OVER (ORDER BY id) AS n FROM book) b
       WHERE n <= 2000""",
]


@pytest.fixture
async def big_list(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    reader: TestUser = await factory.user("reader")
    for statement in SEED:
        await factory.execute(statement, u=reader.id)
    await factory.execute("ANALYZE")
    assert await factory.scalar("SELECT count(*) FROM book") == 5000
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 2000
    return await signed_in(client_factory(), reader)


async def p95(make: Callable[[int], Awaitable[httpx.Response]], runs: int = 100) -> float:
    timings: list[float] = []
    for i in range(runs):
        start = time.perf_counter()
        response = await make(i)
        timings.append(time.perf_counter() - start)
        assert response.status_code == 200, response.text[:200]
    return statistics.quantiles(timings, n=20)[18]  # 95th percentile


LIST_PARAMS: list[dict[str, Any]] = [
    {},
    {"sort": "author"},
    {"sort": "series"},
    {"sort": "-finished_on"},
    {"status": "reading"},
    {"q": "title 12"},
    {"q": "author 7"},
    {"page": "20"},
]


async def test_list_pages_under_one_second(big_list: httpx.AsyncClient) -> None:
    page = await p95(lambda i: big_list.get("/", params=LIST_PARAMS[i % len(LIST_PARAMS)]))
    api = await p95(
        lambda i: big_list.get("/api/v1/me/readings", params=LIST_PARAMS[i % len(LIST_PARAMS)])
    )
    print(f"\nlist page p95 {page * 1000:.0f} ms; API p95 {api * 1000:.0f} ms")
    assert page < 1.0
    assert api < 1.0


async def test_type_ahead_under_300_ms(big_list: httpx.AsyncClient) -> None:
    results = {}
    for kind, term in (("books", "title 4"), ("authors", "author 1"), ("series", "series 2")):
        results[kind] = await p95(
            lambda i, kind=kind, term=term: big_list.get(
                f"/api/v1/{kind}", params={"q": f"{term}{i % 10}"}
            )
        )
    print("\ntype-ahead p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert all(value < 0.3 for value in results.values()), results
