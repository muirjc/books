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


# --------------------------------------------------------------------------- races (books-0tw.6)


async def test_author_created_since_the_look_up_is_reused(
    app: Any, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another member creates the author between the import's look-up and its insert: the
    import uses that author instead of failing or duplicating it."""
    from book_tracker.persistence import imports as store

    alice = await factory.user("alice")
    ol = FakeBookSource()
    ol.works[KEY] = listing(KEY, [work(1, "Racing")])
    await _list(app, ol, alice)
    real = store.find_authors_by_names

    async def created_meanwhile(db: Any, keys: Any) -> dict[str, uuid.UUID]:
        found = await real(db, keys)
        await db.execute(
            text(
                "INSERT INTO author (id, name, sort_name, created_by, updated_by) "
                "VALUES (gen_random_uuid(), 'Ann Author', 'Author, Ann', :u, :u)"
            ),
            {"u": alice.id},
        )
        return found  # as looked up: before the other member's insert

    monkeypatch.setattr(store, "find_authors_by_names", created_meanwhile)
    result = await _confirm(app, alice, ["OL1W"])
    assert [b.title for b in result.added] == ["Racing"]
    assert await factory.scalar("SELECT count(*) FROM author") == 1
    author_of_book = await factory.scalar("SELECT author_id FROM book_author")
    assert author_of_book == await factory.scalar("SELECT id FROM author")


async def test_other_author_conflicts_are_not_swallowed(
    app: Any, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from book_tracker.services import catalog as catalog_service
    from book_tracker.services.errors import ConflictError

    alice = await factory.user("alice")
    ol = FakeBookSource()
    ol.works[KEY] = listing(KEY, [work(1, "Racing")])
    await _list(app, ol, alice)

    async def refused(*_: Any, **__: Any) -> Any:
        raise ConflictError("something_else", "Something else")

    monkeypatch.setattr(catalog_service, "create_author", refused)
    with pytest.raises(ConflictError):
        await _confirm(app, alice, ["OL1W"])


async def test_entry_added_from_another_page_meanwhile_is_skipped(
    app: Any, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Principle I ownership path: the member adds the same book from another page while
    the import runs. The import reports it as already on the list; no duplicate entry,
    and nothing of any other member's is touched."""
    from book_tracker.persistence.readings import ReadingEntryRepository

    alice, ben = await factory.user("alice"), await factory.user("ben")
    ann = await factory.author("Ann Author", alice)
    book = await factory.book("Racing", alice, author_ids=[ann])
    await factory.entry(ben, book)  # Ben's own entry for the same book is unaffected
    ol = FakeBookSource()
    ol.works[KEY] = listing(KEY, [work(1, "Racing")])
    await _list(app, ol, alice)
    real = ReadingEntryRepository.book_ids_on_list

    async def added_meanwhile(self: ReadingEntryRepository, ids: Any) -> set[uuid.UUID]:
        on_list = await real(self, ids)
        await self._db.execute(
            text(
                "INSERT INTO reading_entry (id, user_id, book_id, status, times_read) "
                "VALUES (gen_random_uuid(), :u, :b, 'reading', 0)"
            ),
            {"u": alice.id, "b": book},
        )
        return on_list  # as checked: before the other page's insert

    monkeypatch.setattr(ReadingEntryRepository, "book_ids_on_list", added_meanwhile)
    result = await _confirm(app, alice, ["OL1W"])
    assert result.added == ()
    assert [(s.title, s.reason.value) for s in result.skipped] == [("Racing", "on_list")]
    rows = await factory.scalar(
        "SELECT array_agg(status ORDER BY status) FROM reading_entry WHERE book_id = :b", b=book
    )
    assert rows == ["finished", "reading"]  # Ben's, and Alice's from the other page


async def test_other_entry_integrity_errors_are_not_swallowed(
    app: Any, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from book_tracker.persistence.readings import ReadingEntryRepository

    alice = await factory.user("alice")
    ol = FakeBookSource()
    ol.works[KEY] = listing(KEY, [work(1, "Racing")])
    await _list(app, ol, alice)

    class Diag:
        constraint_name = "reading_entry_status_check"

    class Orig(Exception):
        diag = Diag()

    async def broken(*_: Any, **__: Any) -> Any:
        raise IntegrityError("INSERT INTO reading_entry", {}, Orig())

    monkeypatch.setattr(ReadingEntryRepository, "add", broken)
    with pytest.raises(IntegrityError):
        await _confirm(app, alice, ["OL1W"])
