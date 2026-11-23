"""T047: ReadingEntryRepository is bound to one user (Principle I); covers the module."""

from __future__ import annotations

import inspect
import uuid
from typing import Any

import pytest
from sqlalchemy import select

from book_tracker.domain.enums import ReadingStatus
from book_tracker.persistence import models
from book_tracker.persistence.readings import ReadingEntryRepository
from tests.conftest import Factory


@pytest.fixture
async def world(factory: Factory) -> dict[str, Any]:
    alice = await factory.user("alice")
    ben = await factory.user("ben")
    hobbit = await factory.book("The Hobbit", alice)
    dune = await factory.book("Dune", alice)
    return {
        "alice": alice,
        "ben": ben,
        "hobbit": hobbit,
        "dune": dune,
        "alice_hobbit": await factory.entry(alice, hobbit, notes="Alice's note"),
        "alice_dune": await factory.entry(alice, dune, status="reading"),
        "ben_hobbit": await factory.entry(ben, hobbit, notes="Ben's note"),
    }


@pytest.mark.ac("001/AC-04")
async def test_lists_only_own_entries(app: Any, world: dict[str, Any]) -> None:
    async with app.state.db.sessionmaker() as db:
        page = await ReadingEntryRepository(db, world["alice"].id).list(page=1, page_size=50)
    assert {e.id for e in page.items} == {world["alice_hobbit"], world["alice_dune"]}
    assert page.total == 2
    assert [e.book.title for e in page.items] == ["Dune", "The Hobbit"]  # by title


async def test_pagination(app: Any, world: dict[str, Any]) -> None:
    async with app.state.db.sessionmaker() as db:
        repo = ReadingEntryRepository(db, world["alice"].id)
        first = await repo.list(page=1, page_size=1)
        second = await repo.list(page=2, page_size=1)
    assert first.total == second.total == 2
    assert [e.book.title for e in first.items + second.items] == ["Dune", "The Hobbit"]


@pytest.mark.ac("001/AC-04")
async def test_get_other_users_entry_is_none(app: Any, world: dict[str, Any]) -> None:
    async with app.state.db.sessionmaker() as db:
        repo = ReadingEntryRepository(db, world["alice"].id)
        assert await repo.get(world["ben_hobbit"]) is None
        assert await repo.get(uuid.uuid4()) is None
        own = await repo.get(world["alice_hobbit"])
        assert own is not None and own.notes == "Alice's note"
        by_book = await repo.get_by_book(world["hobbit"])
        assert by_book is not None and by_book.id == world["alice_hobbit"]


@pytest.mark.ac("001/AC-04")
async def test_update_and_delete_only_own(app: Any, world: dict[str, Any]) -> None:
    async with app.state.db.sessionmaker() as db:
        repo = ReadingEntryRepository(db, world["alice"].id)
        assert await repo.update(world["ben_hobbit"], notes="hijack") is None
        assert await repo.delete(world["ben_hobbit"]) is False
        updated = await repo.update(
            world["alice_dune"], status=ReadingStatus.FINISHED, times_read=1
        )
        assert updated is not None and updated.status is ReadingStatus.FINISHED
        assert await repo.delete(world["alice_hobbit"]) is True
        await db.commit()
    async with app.state.db.sessionmaker() as db:
        ben_entry = await ReadingEntryRepository(db, world["ben"].id).get(world["ben_hobbit"])
    assert ben_entry is not None and ben_entry.notes == "Ben's note"


async def test_add(app: Any, world: dict[str, Any], factory: Factory) -> None:
    book = await factory.book("New", world["alice"])
    async with app.state.db.sessionmaker() as db:
        repo = ReadingEntryRepository(db, world["ben"].id)
        entry = await repo.add(
            book_id=book,
            status=ReadingStatus.WANT_TO_READ,
            finished_on=None,
            times_read=0,
            notes=None,
        )
    assert entry.book.title == "New"
    assert entry.status is ReadingStatus.WANT_TO_READ


def test_no_method_accepts_a_user_id() -> None:
    for name, member in inspect.getmembers(ReadingEntryRepository, inspect.isfunction):
        if name.startswith("_"):
            continue
        assert "user_id" not in inspect.signature(member).parameters, name


@pytest.mark.ac("009/AC-15")
async def test_list_books_returns_only_own_entries(app: Any, world: dict[str, Any]) -> None:
    """Spec 009 R3: the entries behind a story's status are the bound user's only."""
    async with app.state.db.sessionmaker() as db:
        ben = ReadingEntryRepository(db, world["ben"].id)
        assert [e.id for e in await ben.list_books({world["hobbit"], world["dune"]})] == [
            world["ben_hobbit"]
        ]
        assert await ben.list_books(set()) == ()


@pytest.mark.ac("010/AC-14")
async def test_not_on_list_excludes_only_own_books(app: Any, world: dict[str, Any]) -> None:
    """Spec 010 R3: the Catalog page's Not on my list condition is bound to the user."""
    async with app.state.db.sessionmaker() as db:
        for user, expected in (("alice", set()), ("ben", {world["dune"]})):
            condition = ReadingEntryRepository(db, world[user].id).not_on_list()
            rows = await db.scalars(select(models.Book.id).where(condition))
            assert set(rows) == expected, user
