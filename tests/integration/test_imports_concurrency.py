"""Two members importing at once (spec 002 AC-16, SC-003; research R7; task T024)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from book_tracker.domain.enums import ReadingStatus
from book_tracker.services import imports
from tests.conftest import Factory, TestUser
from tests.fakes import FakeBookSource, listing, work

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
KEY = "OL1A"
LOCK = "SELECT pg_advisory_xact_lock(hashtext('book_tracker.import'))"


async def _list(app: Any, ol: FakeBookSource, user: TestUser) -> None:
    async with app.state.db.sessionmaker() as db:
        await imports.list_works(db, ol, user.id, KEY, NOW)
        await db.commit()


async def _confirm(app: Any, user: TestUser, keys: list[str]) -> Any:
    async with app.state.db.sessionmaker() as db:
        result = await imports.confirm_import(
            db, user.id, author_key=KEY, work_keys=keys,
            status=ReadingStatus.FINISHED, now=NOW,
        )  # fmt: skip
        await db.commit()
    return result


@pytest.mark.ac("002/AC-16")
async def test_second_member_reuses_the_first_members_new_book(app: Any, factory: Factory) -> None:
    alice, ben = await factory.user("alice"), await factory.user("ben")
    ol = FakeBookSource(works={KEY: listing(KEY, [work(1, "Same Book")])})
    await _list(app, ol, alice)
    await _list(app, ol, ben)
    await _confirm(app, ben, ["OL1W"])  # commits first
    result = await _confirm(app, alice, ["OL1W"])
    assert [(b.title, b.new_to_catalog) for b in result.added] == [("Same Book", False)]
    assert await factory.scalar("SELECT count(*) FROM book") == 1
    assert await factory.scalar("SELECT count(*) FROM book_source_ref") == 1
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 2


@pytest.mark.ac("002/AC-16")
async def test_confirms_wait_for_the_import_lock(app: Any, factory: Factory) -> None:
    alice = await factory.user("alice")
    ol = FakeBookSource(works={KEY: listing(KEY, [work(1)])})
    await _list(app, ol, alice)
    async with app.state.db.sessionmaker() as holder:
        await holder.execute(text(LOCK))
        task = asyncio.create_task(_confirm(app, alice, ["OL1W"]))
        await asyncio.sleep(0.5)
        assert not task.done()  # waiting for the lock
        await holder.commit()  # releases it
    await asyncio.wait_for(task, timeout=10)
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 1


@pytest.mark.ac("002/AC-16")
async def test_overlapping_imports_do_not_deadlock(app: Any, factory: Factory) -> None:
    alice, ben = await factory.user("alice"), await factory.user("ben")
    shared = ("New Writer", "Other Writer")
    works = [work(1, "W1", shared), work(2, "W2", shared[::-1]), work(3, "W3", shared)]
    ol = FakeBookSource(works={KEY: listing(KEY, works)})
    await _list(app, ol, alice)
    await _list(app, ol, ben)
    a, b = await asyncio.gather(
        _confirm(app, alice, ["OL1W", "OL2W"]), _confirm(app, ben, ["OL3W", "OL1W"])
    )
    assert len(a.added) == 2 and len(b.added) == 2
    assert await factory.scalar("SELECT count(*) FROM book") == 3
    assert await factory.scalar("SELECT count(*) FROM author") == 2


@pytest.mark.ac("002/AC-16")
async def test_database_backstop_without_the_lock(app: Any, factory: Factory) -> None:
    """``_add_new_work`` reuses a book another session committed (Principle VI backstop)."""
    alice, ben = await factory.user("alice"), await factory.user("ben")
    ol = FakeBookSource(works={KEY: listing(KEY, [work(1, "Raced")])})
    await _list(app, ol, ben)
    await _confirm(app, ben, ["OL1W"])
    winner = await factory.scalar("SELECT book_id FROM book_source_ref")
    author_id = await factory.scalar("SELECT id FROM author")
    async with app.state.db.sessionmaker() as db:
        book_id, created = await imports._add_new_work(  # noqa: SLF001 - the backstop itself
            db, alice.id, work(1, "Raced"), [author_id], NOW
        )
        await db.commit()
    assert (book_id, created) == (winner, False)
    assert await factory.scalar("SELECT count(*) FROM book") == 1


async def test_other_database_errors_are_not_swallowed(app: Any, factory: Factory) -> None:
    """Only the source-link race is turned into "reuse the book"; anything else is a bug."""
    alice = await factory.user("alice")
    async with app.state.db.sessionmaker() as db:
        with pytest.raises(IntegrityError):
            await imports._add_new_work(  # noqa: SLF001
                db, alice.id, work(9, "Orphan"), [uuid.uuid4()], NOW
            )
