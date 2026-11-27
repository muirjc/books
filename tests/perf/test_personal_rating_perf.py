"""Spec 020 AC-15: My books sorted and filtered by rating at 5,000 books with mixed ratings
(marker ``perf``)."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import Factory
from tests.perf.test_list_performance import big_list, p95  # noqa: F401 - fixture

pytestmark = pytest.mark.perf


@pytest.mark.ac("020/AC-15")
async def test_rating_sort_and_filter_under_one_second(
    big_list: httpx.AsyncClient,  # noqa: F811
    factory: Factory,
) -> None:
    # Mixed ratings: one entry in six unrated, the rest spread over 1 to 5.
    await factory.execute(
        "UPDATE reading_entry SET rating = CASE WHEN abs(hashtext(id::text)) % 6 = 0 THEN NULL "
        "ELSE abs(hashtext(id::text)) % 5 + 1 END"
    )
    assert await factory.scalar("SELECT count(*) FROM reading_entry WHERE rating IS NULL") > 0
    assert await factory.scalar("SELECT count(DISTINCT rating) FROM reading_entry") == 5
    results = {
        "highest rated": await p95(lambda i: big_list.get("/", params={"sort": "-rating"})),
        "4 and up": await p95(lambda i: big_list.get("/", params={"rating": "4"})),
        "not rated": await p95(lambda i: big_list.get("/", params={"rating": "unrated"})),
        "last page, highest": await p95(
            lambda i: big_list.get("/", params={"sort": "-rating", "page": "100"})
        ),
        "api": await p95(
            lambda i: big_list.get(
                "/api/v1/me/readings", params={"sort": "-rating", "min_rating": "4"}
            )
        ),
    }
    print("\nspec 020 p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert all(v < 1.0 for v in results.values()), results
