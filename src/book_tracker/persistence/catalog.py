"""Shared catalog: authors, series, books and summaries. Returns domain objects only."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, exists, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain import models as domain
from book_tracker.persistence import models
from book_tracker.persistence.mappers import to_author, to_book, to_series, to_summary

# --------------------------------------------------------------------------- reads


async def get_author(db: AsyncSession, author_id: uuid.UUID) -> domain.Author | None:
    row = (
        await db.execute(
            select(models.Author)
            .where(models.Author.id == author_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    return to_author(row) if row else None


async def get_series(db: AsyncSession, series_id: uuid.UUID) -> domain.Series | None:
    row = (
        await db.execute(
            select(models.Series)
            .where(models.Series.id == series_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    return to_series(row) if row else None


async def get_book(db: AsyncSession, book_id: uuid.UUID) -> domain.Book | None:
    row = (
        await db.execute(
            select(models.Book)
            .where(models.Book.id == book_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    return to_book(row) if row else None


async def book_exists(db: AsyncSession, book_id: uuid.UUID) -> bool:
    return bool(await db.scalar(select(exists().where(models.Book.id == book_id))))


async def series_exists(db: AsyncSession, series_id: uuid.UUID) -> bool:
    return bool(await db.scalar(select(exists().where(models.Series.id == series_id))))


async def existing_author_ids(db: AsyncSession, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    rows = await db.scalars(select(models.Author.id).where(models.Author.id.in_(ids)))
    return set(rows)


# Look-ups used to explain uniqueness conflicts (research R9).


async def find_author_by_name(db: AsyncSession, name: str) -> tuple[uuid.UUID, str] | None:
    row = (
        await db.execute(
            select(models.Author.id, models.Author.name).where(
                func.lower(models.Author.name) == name.lower()
            )
        )
    ).first()
    return (row[0], row[1]) if row else None


async def find_series_by_name(db: AsyncSession, name: str) -> tuple[uuid.UUID, str] | None:
    row = (
        await db.execute(
            select(models.Series.id, models.Series.name).where(
                func.lower(models.Series.name) == name.lower()
            )
        )
    ).first()
    return (row[0], row[1]) if row else None


async def find_book_by_isbn(db: AsyncSession, isbn_13: str) -> tuple[uuid.UUID, str] | None:
    row = (
        await db.execute(
            select(models.Book.id, models.Book.title).where(models.Book.isbn_13 == isbn_13)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def find_book_by_series_number(
    db: AsyncSession, series_id: uuid.UUID, number: Decimal
) -> tuple[uuid.UUID, str] | None:
    row = (
        await db.execute(
            select(models.Book.id, models.Book.title).where(
                models.Book.series_id == series_id, models.Book.series_number == number
            )
        )
    ).first()
    return (row[0], row[1]) if row else None


async def author_names(db: AsyncSession) -> list[tuple[uuid.UUID, str, str | None]]:
    """(id, name, real name) of every catalog author, for "did you mean" (spec 005)."""
    rows = await db.execute(select(models.Author.id, models.Author.name, models.Author.real_name))
    return [(r[0], r[1], r[2]) for r in rows]


async def series_names(db: AsyncSession) -> list[tuple[uuid.UUID, str]]:
    """(id, name) of every catalog series, for "did you mean" (spec 005)."""
    rows = await db.execute(select(models.Series.id, models.Series.name))
    return [(r[0], r[1]) for r in rows]


async def list_series_books(db: AsyncSession, series_id: uuid.UUID) -> list[domain.Book]:
    """Every catalog book in a series, on anyone's list or none: by number, unnumbered
    last, then by title."""
    rows = (
        (
            await db.execute(
                select(models.Book)
                .where(models.Book.series_id == series_id)
                .order_by(
                    models.Book.series_number.asc().nulls_last(), func.lower(models.Book.title)
                )
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return [to_book(row) for row in rows]


def _has_no_books() -> Any:
    return ~exists().where(models.BookAuthor.author_id == models.Author.id)


async def author_books(db: AsyncSession, author_id: uuid.UUID) -> list[domain.Book]:
    """The catalog books that list this author, by title (spec 008)."""
    rows = (
        (
            await db.execute(
                select(models.Book)
                .join(models.BookAuthor, models.BookAuthor.book_id == models.Book.id)
                .where(models.BookAuthor.author_id == author_id)
                .order_by(func.lower(models.Book.title), models.Book.id)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return [to_book(row) for row in rows]


async def unused_authors(db: AsyncSession) -> list[domain.Author]:
    """Authors no book lists, by sort name (spec 008)."""
    rows = (
        (
            await db.execute(
                select(models.Author)
                .where(_has_no_books())
                .order_by(func.lower(models.Author.sort_name), models.Author.id)
            )
        )
        .scalars()
        .all()
    )
    return [to_author(row) for row in rows]


async def unused_author_count(db: AsyncSession) -> int:
    count = await db.scalar(select(func.count()).select_from(models.Author).where(_has_no_books()))
    return int(count or 0)


async def delete_unused_author(db: AsyncSession, author_id: uuid.UUID) -> bool:
    """Delete the author only if no book lists it, in one statement, so a book linked
    meanwhile keeps it (spec 008 FR-003). False when it wasn't deleted."""
    deleted = await db.execute(
        delete(models.Author)
        .where(models.Author.id == author_id, _has_no_books())
        .returning(models.Author.id)
    )
    return deleted.scalar_one_or_none() is not None


async def upcoming_books(db: AsyncSession, today: date) -> list[domain.Book]:
    """Catalog books with a release date after today, soonest first, then by title
    (spec 007). Catalog data only: no reading entries are read."""
    rows = (
        (
            await db.execute(
                select(models.Book)
                .where(models.Book.release_date > today)
                .order_by(
                    models.Book.release_date.asc(), func.lower(models.Book.title), models.Book.id
                )
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return [to_book(row) for row in rows]


# --------------------------------------------------------------------------- writes


async def create_author(
    db: AsyncSession,
    *,
    name: str,
    sort_name: str,
    is_pen_name: bool,
    real_name: str | None,
    actor_id: uuid.UUID,
) -> domain.Author:
    row = models.Author(
        id=uuid.uuid4(),
        name=name,
        sort_name=sort_name,
        is_pen_name=is_pen_name,
        real_name=real_name,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(row)
    await db.flush()
    author = await get_author(db, row.id)
    assert author is not None  # noqa: S101 - just inserted
    return author


async def create_series(db: AsyncSession, *, name: str, actor_id: uuid.UUID) -> domain.Series:
    row = models.Series(id=uuid.uuid4(), name=name, created_by=actor_id, updated_by=actor_id)
    db.add(row)
    await db.flush()
    series = await get_series(db, row.id)
    assert series is not None  # noqa: S101 - just inserted
    return series


async def create_book(
    db: AsyncSession,
    *,
    title: str,
    author_ids: list[uuid.UUID],
    series_id: uuid.UUID | None,
    series_number: Decimal | None,
    isbn_13: str | None,
    actor_id: uuid.UUID,
    release_date: date | None = None,
) -> domain.Book:
    book_id = uuid.uuid4()
    db.add(
        models.Book(
            id=book_id,
            title=title,
            series_id=series_id,
            series_number=series_number,
            isbn_13=isbn_13,
            release_date=release_date,
            created_by=actor_id,
            updated_by=actor_id,
        )
    )
    await db.flush()
    for position, author_id in enumerate(author_ids, start=1):
        db.add(models.BookAuthor(book_id=book_id, author_id=author_id, position=position))
    await db.flush()
    book = await get_book(db, book_id)
    assert book is not None  # noqa: S101 - just inserted
    return book


# --------------------------------------------------------------------------- search


def like_patterns(q: str) -> tuple[str, str]:
    """(contains, prefix) ILIKE patterns with ``%``, ``_`` and ``\\`` taken literally."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%", f"{escaped}%"


async def search_books(
    db: AsyncSession, q: str, limit: int, isbn_13: str | None = None
) -> list[domain.Book]:
    """Title, author name or real name; an exact ISBN match ranks first (research R7)."""
    contains, prefix = like_patterns(q)
    by_author = exists().where(
        models.BookAuthor.book_id == models.Book.id,
        models.BookAuthor.author_id == models.Author.id,
        or_(
            models.Author.name.ilike(contains, escape="\\"),
            models.Author.real_name.ilike(contains, escape="\\"),
        ),
    )
    conditions = [models.Book.title.ilike(contains, escape="\\"), by_author]
    order: list[Any] = []
    if isbn_13 is not None:
        conditions.append(models.Book.isbn_13 == isbn_13)
        order.append(func.coalesce(models.Book.isbn_13 == isbn_13, False).desc())
    order += [models.Book.title.ilike(prefix, escape="\\").desc(), func.lower(models.Book.title)]
    rows = (
        (
            await db.execute(
                select(models.Book).where(or_(*conditions)).order_by(*order).limit(limit)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return [to_book(row) for row in rows]


async def search_authors(db: AsyncSession, q: str, limit: int) -> list[domain.Author]:
    contains, prefix = like_patterns(q)
    rows = (
        (
            await db.execute(
                select(models.Author)
                .where(
                    or_(
                        models.Author.name.ilike(contains, escape="\\"),
                        models.Author.real_name.ilike(contains, escape="\\"),
                    )
                )
                .order_by(
                    models.Author.name.ilike(prefix, escape="\\").desc(),
                    func.lower(models.Author.name),
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [to_author(row) for row in rows]


async def search_series(db: AsyncSession, q: str, limit: int) -> list[domain.Series]:
    contains, prefix = like_patterns(q)
    rows = (
        (
            await db.execute(
                select(models.Series)
                .where(models.Series.name.ilike(contains, escape="\\"))
                .order_by(
                    models.Series.name.ilike(prefix, escape="\\").desc(),
                    func.lower(models.Series.name),
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [to_series(row) for row in rows]


# --------------------------------------------------------------------------- updates


async def update_author(
    db: AsyncSession, author_id: uuid.UUID, actor_id: uuid.UUID, **fields: object
) -> domain.Author | None:
    """None when the author no longer exists (deleted meanwhile, spec 008)."""
    updated = await db.execute(
        update(models.Author)
        .where(models.Author.id == author_id)
        .values(**fields, updated_by=actor_id, updated_at=func.now())
        .returning(models.Author.id)
    )
    if updated.scalar_one_or_none() is None:
        return None
    return await get_author(db, author_id)


async def update_series(
    db: AsyncSession, series_id: uuid.UUID, actor_id: uuid.UUID, *, name: str
) -> domain.Series:
    await db.execute(
        update(models.Series)
        .where(models.Series.id == series_id)
        .values(name=name, updated_by=actor_id, updated_at=func.now())
    )
    series = await get_series(db, series_id)
    assert series is not None  # noqa: S101 - checked by the service
    return series


async def update_book(
    db: AsyncSession,
    book_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    author_ids: list[uuid.UUID] | None = None,
    **fields: object,
) -> domain.Book:
    await db.execute(
        update(models.Book)
        .where(models.Book.id == book_id)
        .values(**fields, updated_by=actor_id, updated_at=func.now())
    )
    if author_ids is not None:
        await db.execute(delete(models.BookAuthor).where(models.BookAuthor.book_id == book_id))
        # Core insert: the same (book, author) keys may still be in the session's identity map.
        await db.execute(
            insert(models.BookAuthor),
            [
                {"book_id": book_id, "author_id": author_id, "position": position}
                for position, author_id in enumerate(author_ids, start=1)
            ],
        )
    book = await get_book(db, book_id)
    assert book is not None  # noqa: S101 - checked by the service
    return book


# --------------------------------------------------------------------------- summaries


async def list_summaries(db: AsyncSession, book_id: uuid.UUID) -> list[domain.Summary]:
    rows = (
        (
            await db.execute(
                select(models.BookSummary)
                .where(models.BookSummary.book_id == book_id)
                .order_by(
                    models.BookSummary.created_at.desc(), models.BookSummary.is_current.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    return [to_summary(row) for row in rows]


async def save_summary(
    db: AsyncSession, book_id: uuid.UUID, text: str, origin: str, actor_id: uuid.UUID
) -> domain.Summary:
    """Make ``text`` the book's current summary, keeping the old one as history (FR-024).

    The book row is locked so concurrent saves can't leave two current summaries.
    """
    await db.execute(select(models.Book.id).where(models.Book.id == book_id).with_for_update())
    await db.execute(
        update(models.BookSummary)
        .where(models.BookSummary.book_id == book_id, models.BookSummary.is_current)
        .values(is_current=False, updated_at=func.now())
    )
    summary_id = uuid.uuid4()
    await db.execute(
        insert(models.BookSummary).values(
            id=summary_id,
            book_id=book_id,
            text=text,
            origin=origin,
            created_by=actor_id,
            is_current=True,
        )
    )
    row = (
        await db.execute(
            select(models.BookSummary)
            .where(models.BookSummary.id == summary_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return to_summary(row)
