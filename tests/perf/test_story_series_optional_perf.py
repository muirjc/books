"""Spec 019 AC-16: an anthology of stories without a series, at 5,000 books (marker
``perf``)."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import Factory
from tests.perf.test_list_performance import BIG_SERIES, STORIES, big_list, p95  # noqa: F401

pytestmark = pytest.mark.perf

ANTHOLOGY = [
    """INSERT INTO book (id, title, created_by, updated_by)
       SELECT gen_random_uuid(), 'Plain anthology', id, id FROM app_user WHERE login = 'reader'""",
    """INSERT INTO book_author (book_id, author_id, position)
       SELECT id, (SELECT id FROM author ORDER BY name LIMIT 1), 1 FROM book
       WHERE title = 'Plain anthology'""",
    """INSERT INTO story (id, title, created_by, updated_by)
       SELECT gen_random_uuid(), 'Plain story ' || i, u.id, u.id
       FROM generate_series(1, 30) AS i
       CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u""",
    """INSERT INTO story_author (story_id, author_id, position)
       SELECT st.id, (SELECT id FROM author ORDER BY name LIMIT 1), 1 FROM story st
       WHERE st.series_id IS NULL""",
    """INSERT INTO book_story (book_id, story_id)
       SELECT (SELECT id FROM book WHERE title = 'Plain anthology'), id FROM story
       WHERE series_id IS NULL ORDER BY title""",
    """INSERT INTO reading_entry (id, user_id, book_id, status, times_read)
       SELECT gen_random_uuid(), u.id, b.id, 'reading', 0
       FROM book b CROSS JOIN (SELECT id FROM app_user WHERE login = 'reader') u
       WHERE b.title = 'Plain anthology'""",
]


@pytest.mark.ac("019/AC-16")
async def test_pages_with_stories_without_a_series(
    big_list: httpx.AsyncClient,  # noqa: F811
    factory: Factory,
) -> None:
    for statement in BIG_SERIES + STORIES + ANTHOLOGY:
        await factory.execute(statement)
    await factory.execute("ANALYZE")
    book = await factory.scalar("SELECT id FROM book WHERE title = 'Plain anthology'")
    entry = await factory.scalar(f"SELECT id FROM reading_entry WHERE book_id = '{book}'")
    series = await factory.scalar("SELECT id FROM series WHERE name = 'A long series'")
    assert await factory.scalar(f"SELECT count(*) FROM book_story WHERE book_id = '{book}'") == 30
    results = {
        "book page": await p95(lambda i: big_list.get(f"/books/{book}")),
        "entry page": await p95(lambda i: big_list.get(f"/entries/{entry}")),
        "edit book": await p95(lambda i: big_list.get(f"/catalog/books/{book}/edit")),
        "series page": await p95(lambda i: big_list.get(f"/series/{series}")),
    }
    print("\nspec 019 p95: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in results.items()))
    assert all(value < 1.0 for value in results.values()), results
