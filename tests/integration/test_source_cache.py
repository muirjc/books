"""The 24-hour cache of Open Library answers (FR-017; research R5; task T012)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from book_tracker.domain.imports import AuthorCandidate, WorkCandidate, WorkList
from book_tracker.persistence import source_cache

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
AUTHOR = AuthorCandidate("OL1A", "Ann Author", "1950", None, "First Book", 2)
WORK = WorkCandidate("OL1W", ("OL9W",), "First Book", 1990, ("Ann Author",),
                     frozenset({"9780000000002"}), 3)  # fmt: skip


async def test_put_then_get_round_trips(app: Any) -> None:
    async with app.state.db.sessionmaker() as db:
        await source_cache.put_authors(db, "ann author", [AUTHOR], NOW)
        listing = WorkList(author=AUTHOR, works=(WORK,), total=2, truncated=False)
        await source_cache.put_works(db, "OL1A", listing, NOW)
        await db.commit()
    async with app.state.db.sessionmaker() as db:
        authors = await source_cache.get_authors(db, "ann author", NOW + timedelta(hours=1))
        works = await source_cache.get_works(db, "OL1A", NOW + timedelta(hours=1))
    assert authors is not None and authors.value == [AUTHOR]
    assert works is not None and works.value == listing
    assert works.fetched_at == NOW and works.expires_at == NOW + timedelta(hours=24)


async def test_expired_rows_are_not_returned(app: Any) -> None:
    async with app.state.db.sessionmaker() as db:
        await source_cache.put_authors(db, "ann author", [AUTHOR], NOW)
        await db.commit()
        assert await source_cache.get_authors(db, "ann author", NOW + timedelta(hours=25)) is None


async def test_writing_deletes_expired_rows_and_upserts(app: Any) -> None:
    async with app.state.db.sessionmaker() as db:
        await source_cache.put_authors(db, "old", [AUTHOR], NOW)
        await source_cache.put_authors(db, "ann author", [], NOW)
        later = NOW + timedelta(hours=30)
        await source_cache.put_authors(db, "ann author", [AUTHOR], later)  # upsert
        await db.commit()
        assert await source_cache.count_rows(db) == 1  # "old" expired and was removed
        cached = await source_cache.get_authors(db, "ann author", later)
    assert cached is not None and cached.value == [AUTHOR]
