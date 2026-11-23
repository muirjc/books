"""Favorite authors (spec 011), always filtered by the bound user (Constitution Principle I).

As with ``ReadingEntryRepository``, the repository is created with the session user's id.
Every statement adds ``favorite_author.user_id = <bound user>``, and no method takes a user
id from its caller.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain import models as domain
from book_tracker.persistence import models
from book_tracker.persistence.mappers import to_author


class FavoriteAuthorRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._db = session
        self._user_id = user_id

    def _mine(self) -> ColumnElement[bool]:
        return models.FavoriteAuthor.user_id == self._user_id

    async def list(self) -> list[domain.Author]:
        """My favorite authors, by sort name."""
        rows = await self._db.scalars(
            select(models.Author)
            .join(models.FavoriteAuthor, models.FavoriteAuthor.author_id == models.Author.id)
            .where(self._mine())
            .order_by(func.lower(models.Author.sort_name), models.Author.id)
        )
        return [to_author(row) for row in rows]

    async def has(self, author_id: uuid.UUID) -> bool:
        found = await self._db.scalar(
            select(exists().where(self._mine(), models.FavoriteAuthor.author_id == author_id))
        )
        return bool(found)

    async def add(self, author_id: uuid.UUID) -> bool:
        """Add a favorite; already one is fine. False when the author doesn't exist (it may
        have been deleted a moment ago, AC-17)."""
        try:
            async with self._db.begin_nested():
                await self._db.execute(
                    pg_insert(models.FavoriteAuthor)
                    .values(user_id=self._user_id, author_id=author_id)
                    .on_conflict_do_nothing()
                )
        except IntegrityError:  # favorite_author_author_id_fkey: no such author
            return False
        return True

    async def remove(self, author_id: uuid.UUID) -> bool:
        """True when a favorite was removed."""
        removed = await self._db.execute(
            delete(models.FavoriteAuthor)
            .where(self._mine(), models.FavoriteAuthor.author_id == author_id)
            .returning(models.FavoriteAuthor.author_id)
        )
        return removed.scalar_one_or_none() is not None

    def condition(self) -> ColumnElement[bool]:
        """A condition on ``Book``: one of its authors is my favorite (the My books filter,
        research R3)."""
        return exists().where(
            models.BookAuthor.book_id == models.Book.id,
            models.FavoriteAuthor.author_id == models.BookAuthor.author_id,
            self._mine(),
        )
