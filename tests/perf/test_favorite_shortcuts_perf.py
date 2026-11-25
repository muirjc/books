"""Spec 017 AC-15: favorite stars and the offer at 5,000 books (marker ``perf``)."""

from __future__ import annotations

import uuid

import httpx
import pytest

from tests.conftest import Factory
from tests.perf.test_list_performance import big_list, p95  # noqa: F401 - fixture

pytestmark = pytest.mark.perf

# A Finished entry of the reader's whose author has other Finished books on the list.
PICK = """
SELECT e.id AS entry, e.book_id AS book
FROM reading_entry e JOIN book_author ba ON ba.book_id = e.book_id
WHERE e.status = 'finished' AND ba.author_id IN (
  SELECT ba2.author_id FROM reading_entry e2 JOIN book_author ba2 ON ba2.book_id = e2.book_id
  WHERE e2.status = 'finished' GROUP BY ba2.author_id HAVING count(*) >= 2)
LIMIT 1"""


@pytest.mark.ac("017/AC-15")
async def test_star_pages_and_finishing_save_under_one_second(
    big_list: httpx.AsyncClient,  # noqa: F811
    factory: Factory,
) -> None:
    row = await factory.row(PICK)
    entry, book = uuid.UUID(str(row["entry"])), uuid.UUID(str(row["book"]))

    timing = await p95(lambda i: big_list.get(f"/books/{book}"))
    print(f"\nbook page with stars p95 {timing * 1000:.0f} ms")
    assert timing < 1.0
    timing = await p95(lambda i: big_list.get(f"/entries/{entry}?finished={book}"))
    page = (await big_list.get(f"/entries/{entry}?finished={book}")).text
    assert "favorite-offer" in page
    print(f"entry page with stars and the offer p95 {timing * 1000:.0f} ms")
    assert timing < 1.0

    async def finish_and_land(i: int) -> httpx.Response:
        await factory.execute("UPDATE reading_entry SET status = 'reading' WHERE id = :e", e=entry)
        saved = await big_list.post(
            f"/entries/{entry}",
            data={"status": "finished", "finished_on": "2026-11-20", "times_read": "1",
                  "notes": "", "pre_ordered": ""},
        )  # fmt: skip
        assert saved.status_code == 303 and "finished=" in saved.headers["location"]
        return await big_list.get(saved.headers["location"])

    timing = await p95(finish_and_land, runs=40)
    print(f"finishing save and landing page p95 {timing * 1000:.0f} ms")
    assert timing < 1.0
