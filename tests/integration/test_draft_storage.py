"""Spec 012 T007: the draft cache, the per-member allowance, and cached book descriptions."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from book_tracker.domain.drafts import DRAFT_TTL, BookDescription
from book_tracker.persistence import drafts, source_cache
from book_tracker.persistence.draft_usage import DraftUsageRepository
from tests.conftest import Factory

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
TODAY = date(2026, 11, 23)


async def _add(app: Any, key: str, text: str, at: datetime) -> str:
    async with app.state.db.sessionmaker() as db:
        draft = await drafts.add(
            db,
            draft_key=key,
            text=text,
            source_urls=("https://en.wikipedia.org/wiki/X",),
            model="claude-opus-5-5",
            series_name="The Dresden Files",
            series_number=Decimal("2"),
            now=at,
        )
        await db.commit()
    return draft.id


@pytest.mark.ac("012/AC-15")
async def test_newest_draft_for_a_key_within_30_days(app: Any) -> None:
    await _add(app, "isbn:1", "old", NOW - timedelta(days=3))
    newest = await _add(app, "isbn:1", "new", NOW - timedelta(days=1))
    await _add(app, "isbn:2", "other book", NOW)
    async with app.state.db.sessionmaker() as db:
        found = await drafts.newest(db, "isbn:1", NOW)
        assert found is not None and found.id == newest and found.text == "new"
        assert found.source_urls == ("https://en.wikipedia.org/wiki/X",)
        assert found.series_number == Decimal("2")
        assert await drafts.newest(db, "isbn:1", NOW + DRAFT_TTL) is None  # all expired
        assert await drafts.newest(db, "isbn:3", NOW) is None


@pytest.mark.ac("012/AC-16")
async def test_get_by_id_and_prune(app: Any) -> None:
    old = await _add(app, "isbn:1", "old", NOW - DRAFT_TTL - timedelta(days=1))
    kept = await _add(app, "isbn:1", "kept", NOW - timedelta(days=1))
    async with app.state.db.sessionmaker() as db:
        draft = await drafts.get(db, kept)
        assert draft is not None and draft.text == "kept"
        assert await drafts.get(db, "not-a-uuid") is None
        await drafts.prune(db, NOW)
        await db.commit()
        assert await drafts.get(db, old) is None
        assert await drafts.get(db, kept) is not None


async def test_draft_constraints(app: Any, factory: Factory) -> None:
    with pytest.raises(IntegrityError, match="summary_draft_text_check"):
        await _add(app, "isbn:1", "   ", NOW)
    with pytest.raises(IntegrityError, match="summary_draft_source_urls_check"):
        await factory.execute(
            "INSERT INTO summary_draft (id, draft_key, text, source_urls, model) "
            "VALUES (gen_random_uuid(), 'k', 't', '{}'::jsonb, 'm')"
        )


@pytest.mark.ac("012/AC-10")
async def test_allowance_counts_to_the_limit_per_member(app: Any, factory: Factory) -> None:
    alice, ben = await factory.user("alice"), await factory.user("ben")
    async with app.state.db.sessionmaker() as db:
        mine, bens = DraftUsageRepository(db, alice.id), DraftUsageRepository(db, ben.id)
        assert await mine.left(TODAY, 3) == 3
        assert [await mine.reserve(TODAY, 3) for _ in range(4)] == [1, 2, 3, None]
        assert await mine.left(TODAY, 3) == 0
        assert await bens.left(TODAY, 3) == 3  # one member's use never affects another's
        assert await mine.left(TODAY + timedelta(days=1), 3) == 3  # a new day
        assert await mine.reserve(TODAY + timedelta(days=1), 3) == 1
        await db.commit()


@pytest.mark.ac("012/AC-10")
async def test_allowance_is_atomic_under_concurrency(app: Any, factory: Factory) -> None:
    alice = await factory.user("alice")

    async def one() -> int | None:
        async with app.state.db.sessionmaker() as db:
            got = await DraftUsageRepository(db, alice.id).reserve(TODAY, 10)
            await db.commit()
            return got

    results = await asyncio.gather(*(one() for _ in range(15)))
    assert sorted(r for r in results if r is not None) == list(range(1, 11))
    assert results.count(None) == 5


async def test_allowance_prunes_old_days_and_cascades(app: Any, factory: Factory) -> None:
    alice = await factory.user("alice")
    async with app.state.db.sessionmaker() as db:
        repo = DraftUsageRepository(db, alice.id)
        await repo.reserve(TODAY - timedelta(days=31), 10)
        await repo.reserve(TODAY - timedelta(days=5), 10)
        await repo.reserve(TODAY, 10)
        await db.commit()
    days = await factory.scalar(
        "SELECT string_agg(day::text, ',' ORDER BY day) FROM ai_draft_usage"
    )
    assert days == "2026-11-18,2026-11-23"  # the 31-day-old row is gone
    with pytest.raises(IntegrityError, match="ai_draft_usage_count_check"):
        await factory.execute(
            "INSERT INTO ai_draft_usage (user_id, day, count) VALUES (:u, '2026-01-01', 0)",
            u=alice.id,
        )
    await factory.execute("DELETE FROM app_user WHERE id = :u", u=alice.id)
    assert await factory.scalar("SELECT count(*) FROM ai_draft_usage") == 0


@pytest.mark.ac("012/AC-15")
async def test_book_descriptions_are_cached_for_a_day(app: Any) -> None:
    found = BookDescription("https://openlibrary.org/works/OL1W", "A wizard for hire.")
    async with app.state.db.sessionmaker() as db:
        assert await source_cache.get_description(db, "isbn:1", NOW) is None
        await source_cache.put_description(db, "isbn:1", found, NOW)
        await source_cache.put_description(db, "ta:nothing|x", None, NOW)
        await db.commit()
        hit = await source_cache.get_description(db, "isbn:1", NOW + timedelta(hours=23))
        assert hit is not None and hit.value == found
        miss = await source_cache.get_description(db, "ta:nothing|x", NOW)
        assert miss is not None and miss.value is None  # "none found" is cached too
        assert await source_cache.get_description(db, "isbn:1", NOW + timedelta(hours=25)) is None
        long_key = "ta:" + "x" * 900
        await source_cache.put_description(db, long_key, found, NOW)  # hashed key (R3)
        await db.commit()
        again = await source_cache.get_description(db, long_key, NOW)
        assert again is not None and again.value == found
