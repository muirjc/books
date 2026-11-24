"""Spec 015 AC-14: Catalog pages with quick-add rows, and the quick add itself, at 5,000
books (marker ``perf``)."""

from __future__ import annotations

import statistics
import time

import httpx
import pytest

from tests.conftest import Factory, ui_csrf
from tests.perf.test_list_performance import big_list, p95  # noqa: F401 - fixture

pytestmark = pytest.mark.perf


@pytest.mark.ac("015/AC-14")
async def test_catalog_rows_and_quick_add_under_one_second(
    big_list: httpx.AsyncClient,  # noqa: F811
    factory: Factory,
) -> None:
    pages = [{}, {"page": "50"}, {"q": "title 12"}, {"not_mine": "1"}, {"sort": "author"}]
    catalog = await p95(lambda i: big_list.get("/catalog", params=pages[i % len(pages)]))
    csrf = await ui_csrf(big_list)
    joined = await factory.scalar(
        "SELECT string_agg(id::text, ',') FROM (SELECT b.id FROM book b "
        "LEFT JOIN reading_entry e ON e.book_id = b.id WHERE e.id IS NULL "
        "ORDER BY b.title LIMIT 40) AS free"
    )
    books = str(joined).split(",")
    timings: list[float] = []
    for book in books:
        start = time.perf_counter()
        response = await big_list.post(
            f"/books/{book}/want-to-read", data={"back": "/catalog?page=3", "csrf_token": csrf}
        )
        timings.append(time.perf_counter() - start)
        assert response.status_code == 303
    quick = statistics.quantiles(timings, n=20)[18]
    print(f"\ncatalog p95 {catalog * 1000:.0f} ms; quick add p95 {quick * 1000:.0f} ms")
    assert catalog < 1.0 and quick < 1.0
