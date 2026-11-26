"""Spec 018 AC-19: the Authors page, the Series view and Upcoming with Now out at 5,000
books and 1,500 authors (marker ``perf``)."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import Factory
from tests.perf.test_list_performance import UPCOMING_DATES, big_list, p95  # noqa: F401 - fixture

pytestmark = pytest.mark.perf


@pytest.mark.ac("018/AC-19")
async def test_navigation_pages_under_one_second(
    big_list: httpx.AsyncClient,  # noqa: F811
    factory: Factory,
) -> None:
    for statement in UPCOMING_DATES:
        await factory.execute(statement)
    # A few dozen favorites, so favorites first and Favorites only have work to do.
    await factory.execute(
        """INSERT INTO favorite_author (user_id, author_id)
           SELECT u.id, a.id FROM (SELECT id FROM author ORDER BY sort_name LIMIT 40 OFFSET 700) a
           CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u"""
    )
    await factory.execute("ANALYZE")
    assert await factory.scalar("SELECT count(*) FROM author") >= 1500
    assert await factory.scalar("SELECT count(*) FROM series") > 0
    first = (await big_list.get("/authors")).text
    assert first.count('class="author-row"') == 50
    assert 'id="now-out"' in (await big_list.get("/upcoming")).text
    results = {
        "authors": await p95(lambda i: big_list.get("/authors")),
        "authors page 20": await p95(lambda i: big_list.get("/authors", params={"page": "20"})),
        "authors search": await p95(lambda i: big_list.get("/authors", params={"q": "a"})),
        "favorites only": await p95(lambda i: big_list.get("/authors", params={"favorites": "1"})),
        "series view": await p95(lambda i: big_list.get("/catalog/series")),
        "series search": await p95(lambda i: big_list.get("/catalog/series", params={"q": "e"})),
        "upcoming + now out": await p95(lambda i: big_list.get("/upcoming")),
        "my books": await p95(lambda i: big_list.get("/")),
        "catalog": await p95(lambda i: big_list.get("/catalog")),
    }
    print("\nspec 018 p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert all(value < 1.0 for value in results.values()), results
