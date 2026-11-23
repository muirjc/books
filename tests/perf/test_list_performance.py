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


BIG_SERIES = [
    """INSERT INTO series (id, name, created_by, updated_by)
       SELECT gen_random_uuid(), 'A long series', id, id FROM app_user WHERE login = 'reader'""",
    """INSERT INTO book (id, title, series_id, series_number, created_by, updated_by)
       SELECT gen_random_uuid(), 'Long series book ' || i, s.id, i, u.id, u.id
       FROM generate_series(1, 120) AS i
       CROSS JOIN (SELECT id FROM series WHERE name = 'A long series') s
       CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u
       WHERE i % 6 <> 0""",
    """INSERT INTO book_author (book_id, author_id, position)
       SELECT b.id, (SELECT id FROM author ORDER BY name LIMIT 1), 1
       FROM book b JOIN series s ON s.id = b.series_id WHERE s.name = 'A long series'""",
    """INSERT INTO reading_entry (id, user_id, book_id, status, times_read)
       SELECT gen_random_uuid(), u.id, b.id, 'finished', 1
       FROM book b JOIN series s ON s.id = b.series_id
       CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u
       WHERE s.name = 'A long series' AND b.series_number % 2 = 0""",
]


async def test_series_page_under_one_second(big_list: httpx.AsyncClient, factory: Factory) -> None:
    """Spec 006 SC-002: a 100-book series (with 20 gaps) in the 5,000-book catalog."""
    for statement in BIG_SERIES:
        await factory.execute(statement)
    await factory.execute("ANALYZE")
    series = await factory.scalar("SELECT id FROM series WHERE name = 'A long series'")
    assert await factory.scalar(f"SELECT count(*) FROM book WHERE series_id = '{series}'") == 100
    page = await p95(lambda i: big_list.get(f"/series/{series}"))
    print(f"\nseries page p95 {page * 1000:.0f} ms")
    assert page < 1.0


UPCOMING_DATES = [
    # 200 dated books: 150 not out yet (about a third on the reader's list), and 50 out in
    # the last 20 days (some on the list as Want to read, for the notice).
    """UPDATE book SET release_date = CURRENT_DATE + ((n % 365) + 1)::int
       FROM (SELECT id, row_number() OVER (ORDER BY title) AS n FROM book) b
       WHERE book.id = b.id AND b.n % 25 = 0 AND b.n <= 3750""",
    """UPDATE book SET release_date = CURRENT_DATE - (n % 20)::int
       FROM (SELECT id, row_number() OVER (ORDER BY title) AS n FROM book) b
       WHERE book.id = b.id AND b.n % 25 = 1 AND b.n <= 1250""",
    "UPDATE reading_entry SET pre_ordered = true WHERE status = 'want_to_read'",
]


async def test_upcoming_views_under_one_second(
    big_list: httpx.AsyncClient, factory: Factory
) -> None:
    """Spec 007 SC-002: My books with the notice, the Upcoming filter and the Upcoming page,
    with 200 dated books in the 5,000-book catalog."""
    for statement in UPCOMING_DATES:
        await factory.execute(statement)
    await factory.execute("ANALYZE")
    assert await factory.scalar("SELECT count(*) FROM book WHERE release_date IS NOT NULL") == 200
    results = {
        "my books + notice": await p95(lambda i: big_list.get("/")),
        "upcoming filter": await p95(lambda i: big_list.get("/", params={"upcoming": "1"})),
        "upcoming page": await p95(lambda i: big_list.get("/upcoming")),
    }
    print("\nspec 007 p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert all(value < 1.0 for value in results.values()), results


async def test_unused_authors_under_one_second(
    big_list: httpx.AsyncClient, factory: Factory
) -> None:
    """Spec 008 SC-003: 1,500 authors, all with books, plus 200 with none."""
    await factory.execute(
        """INSERT INTO author (id, name, sort_name, created_by, updated_by)
           SELECT gen_random_uuid(), 'Unused ' || i, 'Unused, ' || i, u.id, u.id
           FROM generate_series(1, 200) AS i
           CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u"""
    )
    await factory.execute("ANALYZE")
    results = {
        "unused authors": await p95(lambda i: big_list.get("/catalog/authors/unused")),
        "my books + link": await p95(lambda i: big_list.get("/")),
    }
    print("\nspec 008 p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert all(value < 1.0 for value in results.values()), results


STORIES = [
    # Spec 009: ten collections (in no series) holding 100 stories of the long series at
    # n.5, ten each; the reader has finished half of the collections.
    """INSERT INTO book (id, title, created_by, updated_by)
       SELECT gen_random_uuid(), 'Collection ' || i, u.id, u.id
       FROM generate_series(1, 10) AS i
       CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u""",
    """INSERT INTO book_author (book_id, author_id, position)
       SELECT b.id, (SELECT id FROM author ORDER BY name LIMIT 1), 1
       FROM book b WHERE b.title LIKE 'Collection %'""",
    """INSERT INTO story (id, title, series_id, series_number, created_by, updated_by)
       SELECT gen_random_uuid(), 'Story ' || i, s.id, i + 0.5, u.id, u.id
       FROM generate_series(1, 100) AS i
       CROSS JOIN (SELECT id FROM series WHERE name = 'A long series') s
       CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u""",
    """INSERT INTO story_author (story_id, author_id, position)
       SELECT st.id, (SELECT id FROM author ORDER BY name LIMIT 1), 1 FROM story st""",
    """INSERT INTO book_story (book_id, story_id)
       SELECT b.id, st.id FROM story st
       JOIN book b ON b.title = 'Collection ' || ((floor(st.series_number)::int % 10) + 1)""",
    """INSERT INTO reading_entry (id, user_id, book_id, status, times_read)
       SELECT gen_random_uuid(), u.id, b.id, 'finished', 1
       FROM book b CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u
       WHERE b.title IN ('Collection 1', 'Collection 3', 'Collection 5', 'Collection 7',
                         'Collection 9')""",
    # One more collection with 50 stories, for Edit book.
    """INSERT INTO book (id, title, created_by, updated_by)
       SELECT gen_random_uuid(), 'Big collection', id, id FROM app_user WHERE login = 'reader'""",
    """INSERT INTO book_author (book_id, author_id, position)
       SELECT id, (SELECT id FROM author ORDER BY name LIMIT 1), 1 FROM book
       WHERE title = 'Big collection'""",
    """INSERT INTO book_story (book_id, story_id)
       SELECT (SELECT id FROM book WHERE title = 'Big collection'), id FROM story
       WHERE series_number < 51""",
]


async def test_series_page_with_stories_under_one_second(
    big_list: httpx.AsyncClient, factory: Factory
) -> None:
    """Spec 009 SC-002: a series of 100 books and 100 stories in the 5,000-book catalog,
    and Edit book for a collection of 50 stories."""
    for statement in BIG_SERIES + STORIES:
        await factory.execute(statement)
    await factory.execute("ANALYZE")
    series = await factory.scalar("SELECT id FROM series WHERE name = 'A long series'")
    big = await factory.scalar("SELECT id FROM book WHERE title = 'Big collection'")
    assert await factory.scalar("SELECT count(*) FROM story") == 100
    assert await factory.scalar(f"SELECT count(*) FROM book_story WHERE book_id = '{big}'") == 50
    results = {
        "series page": await p95(lambda i: big_list.get(f"/series/{series}")),
        "edit book": await p95(lambda i: big_list.get(f"/catalog/books/{big}/edit")),
        "type-ahead": await p95(
            lambda i: big_list.get("/suggest/books", params={"field": "title", "title": "Story 4"})
        ),
    }
    print("\nspec 009 p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert results["series page"] < 1.0 and results["edit book"] < 1.0, results
    assert results["type-ahead"] < 0.3, results


CATALOG_PARAMS: dict[str, dict[str, str]] = {
    "plain": {},
    "search": {"q": "title 12"},
    "author search": {"q": "author 7"},
    "isbn": {"q": "978-0-14-143958-7"},
    "z-a": {"sort": "-title"},
    "author sort": {"sort": "author"},
    "series sort": {"sort": "series"},
    "newest": {"sort": "-added"},
    "not on my list": {"not_mine": "1"},
    "late page": {"page": "90"},
}


@pytest.mark.ac("010/AC-06")
async def test_catalog_page_under_one_second(big_list: httpx.AsyncClient) -> None:
    """Spec 010 SC-001: 5,000 catalog books, 2,000 on the viewer's list."""
    results = {
        name: await p95(lambda i, params=params: big_list.get("/catalog", params=params), runs=40)
        for name, params in CATALOG_PARAMS.items()
    }
    print("\nspec 010 p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert all(value < 1.0 for value in results.values()), results
