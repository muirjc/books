"""``ReadingEntryRepository.book_ids_on_list`` is bound to its user (Principle I; T013)."""

from __future__ import annotations

from typing import Any

from book_tracker.persistence.readings import ReadingEntryRepository
from tests.conftest import Factory


async def test_only_the_bound_users_books(app: Any, factory: Factory) -> None:
    alice, ben = await factory.user("alice"), await factory.user("ben")
    b1, b2, b3 = [await factory.book(t, alice) for t in ("One", "Two", "Three")]
    await factory.entry(alice, b1)
    await factory.entry(ben, b2)
    async with app.state.db.sessionmaker() as db:
        assert await ReadingEntryRepository(db, alice.id).book_ids_on_list([b1, b2, b3]) == {b1}
        assert await ReadingEntryRepository(db, ben.id).book_ids_on_list([b1, b2, b3]) == {b2}
        assert await ReadingEntryRepository(db, alice.id).book_ids_on_list([]) == set()
