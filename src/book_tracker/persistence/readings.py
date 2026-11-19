"""Personal reading entries, always filtered by the bound user (Constitution Principle I).

A repository is created with the session user's id. Every statement adds
``reading_entry.user_id = <bound user>``, and no method takes a user id from its caller,
so another member's entry is indistinguishable from one that doesn't exist.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Select, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.models import ReadingEntry, ReadingEntryPage
from book_tracker.persistence import models
from book_tracker.persistence.catalog import like_patterns
from book_tracker.persistence.mappers import to_reading_entry

FilterOptions = list[tuple[uuid.UUID, str]]

SORTS = ("title", "-title", "author", "-author", "series", "-series", "finished_on", "-finished_on")


def _matches(q: str) -> ColumnElement[bool]:
    """Title, author name, author real name or series name (FR-023)."""
    pattern = like_patterns(q)[0]
    by_author = exists().where(
        models.BookAuthor.book_id == models.Book.id,
        models.BookAuthor.author_id == models.Author.id,
        or_(
            models.Author.name.ilike(pattern, escape="\\"),
            models.Author.real_name.ilike(pattern, escape="\\"),
        ),
    )
    return or_(
        models.Book.title.ilike(pattern, escape="\\"),
        by_author,
        models.Series.name.ilike(pattern, escape="\\"),
    )


def _order(sort: str) -> list[Any]:
    descending = sort.startswith("-")
    key = sort.lstrip("-")
    title = func.lower(models.Book.title)
    first_author = (
        select(func.lower(models.Author.sort_name))
        .join(models.BookAuthor, models.BookAuthor.author_id == models.Author.id)
        .where(models.BookAuthor.book_id == models.Book.id)
        .order_by(models.BookAuthor.position)
        .limit(1)
        .scalar_subquery()
    )
    primary: list[Any]
    if key == "author":
        primary = [first_author]
    elif key == "series":
        primary = [func.lower(models.Series.name), models.Book.series_number]
    elif key == "finished_on":
        primary = [models.ReadingEntry.finished_on]
    else:
        primary = [title]
    ordered = [(c.desc() if descending else c.asc()).nulls_last() for c in primary]
    if key != "title":
        ordered.append(title.asc())
    return [*ordered, models.ReadingEntry.id.asc()]


class ReadingEntryRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._db = session
        self._user_id = user_id

    def _owned(self) -> Select[models.ReadingEntry]:
        return select(models.ReadingEntry).where(models.ReadingEntry.user_id == self._user_id)

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        q: str | None = None,
        author_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        status: ReadingStatus | None = None,
        sort: str = "title",
    ) -> ReadingEntryPage:
        filtered = (
            self._owned()
            .join(models.Book, models.Book.id == models.ReadingEntry.book_id)
            .outerjoin(models.Series, models.Series.id == models.Book.series_id)
        )
        if q:
            filtered = filtered.where(_matches(q))
        if author_id is not None:
            filtered = filtered.where(
                exists().where(
                    models.BookAuthor.book_id == models.Book.id,
                    models.BookAuthor.author_id == author_id,
                )
            )
        if series_id is not None:
            filtered = filtered.where(models.Book.series_id == series_id)
        if status is not None:
            filtered = filtered.where(models.ReadingEntry.status == status.value)
        total = await self._db.scalar(select(func.count()).select_from(filtered.subquery()))
        rows = (
            (
                await self._db.execute(
                    filtered.order_by(*_order(sort))
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .unique()
            .all()
        )
        return ReadingEntryPage(
            items=tuple(to_reading_entry(row) for row in rows),
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )

    async def list_series(self, series_id: uuid.UUID) -> tuple[ReadingEntry, ...]:
        """My books in one series: numbered ascending, then unnumbered by title (FR-022)."""
        rows = (
            (
                await self._db.execute(
                    self._owned()
                    .join(models.Book, models.Book.id == models.ReadingEntry.book_id)
                    .where(models.Book.series_id == series_id)
                    .order_by(
                        models.Book.series_number.asc().nulls_last(),
                        func.lower(models.Book.title),
                    )
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .unique()
            .all()
        )
        return tuple(to_reading_entry(row) for row in rows)

    async def filter_options(self) -> tuple[FilterOptions, FilterOptions]:
        """Authors and series that appear on my list, for the filter menus."""
        mine = self._owned().with_only_columns(models.ReadingEntry.book_id).scalar_subquery()
        authors = await self._db.execute(
            select(models.Author.id, models.Author.name)
            .join(models.BookAuthor, models.BookAuthor.author_id == models.Author.id)
            .where(models.BookAuthor.book_id.in_(mine))
            .distinct()
            .order_by(models.Author.name)
        )
        series = await self._db.execute(
            select(models.Series.id, models.Series.name)
            .join(models.Book, models.Book.series_id == models.Series.id)
            .where(models.Book.id.in_(mine))
            .distinct()
            .order_by(models.Series.name)
        )
        return ([(r[0], r[1]) for r in authors], [(r[0], r[1]) for r in series])

    async def get(self, entry_id: uuid.UUID) -> ReadingEntry | None:
        row = (
            await self._db.execute(
                self._owned()
                .where(models.ReadingEntry.id == entry_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return to_reading_entry(row) if row else None

    async def get_by_book(self, book_id: uuid.UUID) -> ReadingEntry | None:
        row = (
            await self._db.execute(
                self._owned()
                .where(models.ReadingEntry.book_id == book_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return to_reading_entry(row) if row else None

    async def book_ids_on_list(self, book_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        """Which of these catalog books are on the bound user's list (spec 002 FR-005)."""
        if not book_ids:
            return set()
        rows = await self._db.scalars(
            self._owned()
            .where(models.ReadingEntry.book_id.in_(list(book_ids)))
            .with_only_columns(models.ReadingEntry.book_id)
        )
        return set(rows)

    async def add(
        self,
        *,
        book_id: uuid.UUID,
        status: ReadingStatus,
        finished_on: date | None,
        times_read: int,
        notes: str | None,
    ) -> ReadingEntry:
        row = models.ReadingEntry(
            id=uuid.uuid4(),
            user_id=self._user_id,
            book_id=book_id,
            status=status.value,
            finished_on=finished_on,
            times_read=times_read,
            notes=notes,
        )
        self._db.add(row)
        await self._db.flush()
        entry = await self.get(row.id)
        assert entry is not None  # noqa: S101 - just inserted in this transaction
        return entry

    async def update(self, entry_id: uuid.UUID, **fields: object) -> ReadingEntry | None:
        values = {k: (v.value if isinstance(v, ReadingStatus) else v) for k, v in fields.items()}
        result = await self._db.execute(
            update(models.ReadingEntry)
            .where(models.ReadingEntry.id == entry_id, models.ReadingEntry.user_id == self._user_id)
            .values(**values, updated_at=func.now())
            .returning(models.ReadingEntry.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get(entry_id)

    async def delete(self, entry_id: uuid.UUID) -> bool:
        result = await self._db.execute(
            delete(models.ReadingEntry)
            .where(models.ReadingEntry.id == entry_id, models.ReadingEntry.user_id == self._user_id)
            .returning(models.ReadingEntry.id)
        )
        return result.scalar_one_or_none() is not None
