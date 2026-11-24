"""Spec 016 AC-15: the book page for a 50-story collection at 5,000 books (marker ``perf``).

The Catalog, author and series budgets are re-checked by the rest of the perf suite.
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from tests.conftest import Factory, TestUser
from tests.perf.test_list_performance import big_list, p95  # noqa: F401 - fixture

pytestmark = pytest.mark.perf


@pytest.mark.ac("016/AC-15")
async def test_book_page_with_fifty_stories_under_one_second(
    big_list: httpx.AsyncClient,  # noqa: F811
    factory: Factory,
) -> None:
    actor = TestUser(id=uuid.UUID(str(await factory.scalar("SELECT id FROM app_user LIMIT 1"))),
                     login="", display_name="", password="", role="member")  # fmt: skip
    author = uuid.UUID(str(await factory.scalar("SELECT id FROM author WHERE name = 'Author 1'")))
    series = uuid.UUID(str(await factory.scalar("SELECT id FROM series WHERE name = 'Series 1'")))
    book = await factory.book("Big Collection", actor, author_ids=[author])
    other = await factory.book("Other Collection", actor, author_ids=[author])
    for i in range(50):  # each story is also in another book: 50 "Also in" links
        await factory.story(f"Story {i}", actor, series_id=series, series_number=f"900.{i:02d}",
                            author_ids=[author], book_ids=[book, other])  # fmt: skip
    page = (await big_list.get(f"/books/{book}")).text
    assert page.count(f'href="/books/{other}"') == 50
    timing = await p95(lambda i: big_list.get(f"/books/{book}"))
    print(f"\nbook page (50 stories) p95 {timing * 1000:.0f} ms")
    assert timing < 1.0
