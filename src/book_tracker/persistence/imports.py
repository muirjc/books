"""Catalog look-ups and writes for importing an author's books (spec 002; research R6, R7).

Id and ISBN sets are passed as one PostgreSQL array parameter (``= ANY(:ids)``), so a
prolific author's thousands of ISBNs stay a single bind parameter. Author names are
compared as ``lower(normalize(name, NFKC))``, the same form the import service uses.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import ColumnElement, String, any_, bindparam, func, literal_column, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import CollectionAggregate

from book_tracker.domain.imports import SOURCE_OPEN_LIBRARY, SourceRef
from book_tracker.persistence import models


def _array(name: str, values: Collection[str]) -> CollectionAggregate[bool]:
    return any_(bindparam(name, sorted(values), type_=ARRAY(String)))


def _name_key() -> ColumnElement[str]:
    return func.lower(func.normalize(models.Author.name, literal_column("NFKC")))


async def find_books_by_source_ids(
    db: AsyncSession, source_ids: Collection[str]
) -> dict[str, uuid.UUID]:
    if not source_ids:
        return {}
    rows = await db.execute(
        select(models.BookSourceRef.source_work_id, models.BookSourceRef.book_id).where(
            models.BookSourceRef.source == SOURCE_OPEN_LIBRARY,
            models.BookSourceRef.source_work_id == _array("ids", source_ids),
        )
    )
    return {r[0]: r[1] for r in rows}


async def find_books_by_isbns(db: AsyncSession, isbns: Collection[str]) -> dict[str, uuid.UUID]:
    if not isbns:
        return {}
    rows = await db.execute(
        select(models.Book.isbn_13, models.Book.id).where(
            models.Book.isbn_13 == _array("isbns", isbns)
        )
    )
    return {r[0]: r[1] for r in rows if r[0] is not None}


async def books_by_first_author_names(
    db: AsyncSession, name_keys: Collection[str]
) -> list[tuple[uuid.UUID, str, str]]:
    """(book id, title, first author's name key) for books whose first author matches."""
    if not name_keys:
        return []
    key = _name_key()
    rows = await db.execute(
        select(models.Book.id, models.Book.title, key)
        .join(models.BookAuthor, models.BookAuthor.book_id == models.Book.id)
        .join(models.Author, models.Author.id == models.BookAuthor.author_id)
        .where(models.BookAuthor.position == 1, key == _array("names", name_keys))
    )
    return [(r[0], r[1], r[2]) for r in rows]


async def find_authors_by_names(
    db: AsyncSession, name_keys: Collection[str]
) -> dict[str, uuid.UUID]:
    if not name_keys:
        return {}
    key = _name_key()
    rows = await db.execute(select(key, models.Author.id).where(key == _array("names", name_keys)))
    return {r[0]: r[1] for r in rows}


async def create_imported_book(
    db: AsyncSession, *, title: str, author_ids: list[uuid.UUID], actor_id: uuid.UUID
) -> uuid.UUID:
    """A catalog book with a title and authors only: no series, number or ISBN (FR-010/011)."""
    book_id = uuid.uuid4()
    db.add(models.Book(id=book_id, title=title, created_by=actor_id, updated_by=actor_id))
    await db.flush()
    for position, author_id in enumerate(author_ids, start=1):
        db.add(models.BookAuthor(book_id=book_id, author_id=author_id, position=position))
    await db.flush()
    return book_id


async def insert_source_ref(
    db: AsyncSession, *, book_id: uuid.UUID, work_id: str, actor_id: uuid.UUID, now: datetime
) -> None:
    db.add(
        models.BookSourceRef(
            id=uuid.uuid4(),
            book_id=book_id,
            source=SOURCE_OPEN_LIBRARY,
            source_work_id=work_id,
            imported_by=actor_id,
            imported_at=now,
        )
    )
    await db.flush()


async def source_ref_for_book(db: AsyncSession, book_id: uuid.UUID) -> SourceRef | None:
    row = (
        await db.execute(
            select(
                models.BookSourceRef.source,
                models.BookSourceRef.source_work_id,
                models.BookSourceRef.imported_at,
            ).where(models.BookSourceRef.book_id == book_id)
        )
    ).first()
    return SourceRef(row[0], row[1], row[2]) if row else None
