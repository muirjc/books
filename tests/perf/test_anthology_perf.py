"""Spec 013 SC-002: Add a book with 50 story rows in the 5,000-book catalog (marker ``perf``)."""

from __future__ import annotations

import statistics
import time

import httpx
import pytest

from tests.conftest import Factory, ui_csrf
from tests.perf.test_list_performance import big_list, p95  # noqa: F401 - fixture

pytestmark = pytest.mark.perf


async def _book(factory: Factory, k: int) -> dict[str, str]:
    author = await factory.scalar("SELECT id FROM author WHERE name = 'Author 1'")
    series = await factory.scalar("SELECT id FROM series WHERE name = 'Series 1'")
    data = {
        "title": f"Anthology {k}", "author_name_0": "Author 1", "author_id_0": str(author),
        "series_name": "Series 1", "series_id": str(series), "status": "finished",
        "anthology": "yes",
    }  # fmt: skip
    for i in range(50):
        data[f"story_title_{i}"] = f"Story {k}-{i}"
        data[f"story_number_{i}"] = f"{500 + k}.{i:02d}"
    return data


@pytest.mark.ac("013/AC-06")
async def test_fifty_story_save_under_one_second(
    big_list: httpx.AsyncClient,  # noqa: F811
    factory: Factory,
) -> None:
    csrf = await ui_csrf(big_list)
    timings: list[float] = []
    for k in range(20):
        data = {**await _book(factory, k), "csrf_token": csrf}
        start = time.perf_counter()
        response = await big_list.post("/books/add", data=data)
        timings.append(time.perf_counter() - start)
        assert response.status_code == 303, response.text[:300]
    assert await factory.scalar("SELECT count(*) FROM story") == 1000
    save = statistics.quantiles(timings, n=20)[18]
    rows = await _book(factory, 99)
    del rows["story_title_49"], rows["story_number_49"]
    redraw = await p95(
        lambda i: big_list.post(
            "/books/add", data={**rows, "csrf_token": csrf, "action": "add_story"}
        ),
        runs=30,
    )
    print(f"\n50-story save p95 {save * 1000:.0f} ms; add-a-row redraw p95 {redraw * 1000:.0f} ms")
    assert save < 1.0
    assert redraw < 1.0
