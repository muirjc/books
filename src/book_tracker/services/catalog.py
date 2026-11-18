"""Shared catalog use cases. Any member may add or edit entries (FR-009).

Uniqueness is left to the database; a violation is turned into a ``ConflictError`` that
names the existing row, so the caller can offer it instead (research R9).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain import models as domain
from book_tracker.domain.values import (
    PEN_NAME_FIRST,
    default_sort_name,
    normalize_name,
    parse_isbn13,
)
from book_tracker.persistence import catalog
from book_tracker.services.errors import (
    ConflictError,
    FieldError,
    NotFoundError,
    ValidationFailed,
)

T = TypeVar("T")

CONFLICT_TITLES = {
    "author_exists": "An author with this name is already in the catalog",
    "series_exists": "A series with this name is already in the catalog",
    "isbn_exists": "A book with this ISBN is already in the catalog",
    "series_number_taken": "Another book already has this number in the series",
}


@dataclass(frozen=True, slots=True)
class NewBook:
    title: str
    author_ids: list[uuid.UUID]
    series_id: uuid.UUID | None = None
    series_number: Decimal | None = None
    isbn_13: str | None = None
    summary: str | None = None


def _constraint(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return str(name) if name else None


async def _conflict(
    db: AsyncSession,
    exc: IntegrityError,
    *,
    name: str | None = None,
    isbn_13: str | None = None,
    series_id: uuid.UUID | None = None,
    series_number: Decimal | None = None,
) -> ConflictError | None:
    constraint = _constraint(exc)
    found: tuple[uuid.UUID, str] | None = None
    code: str | None = None
    if constraint == "author_name_lower_uq" and name is not None:
        code, found = "author_exists", await catalog.find_author_by_name(db, name)
    elif constraint == "series_name_lower_uq" and name is not None:
        code, found = "series_exists", await catalog.find_series_by_name(db, name)
    elif constraint == "book_isbn_13_key" and isbn_13 is not None:
        code, found = "isbn_exists", await catalog.find_book_by_isbn(db, isbn_13)
    elif (
        constraint == "book_series_number_uq"
        and series_id is not None
        and series_number is not None
    ):
        code = "series_number_taken"
        found = await catalog.find_book_by_series_number(db, series_id, series_number)
    if code is None or found is None:
        return None
    return ConflictError(code, CONFLICT_TITLES[code], existing_id=found[0], existing_label=found[1])


async def guarded[T](
    db: AsyncSession,
    action: Callable[[], Awaitable[T]],
    *,
    name: str | None = None,
    isbn_13: str | None = None,
    series_id: uuid.UUID | None = None,
    series_number: Decimal | None = None,
) -> T:
    """Run a write in a savepoint; turn a uniqueness violation into ``ConflictError``."""
    try:
        async with db.begin_nested():
            return await action()
    except IntegrityError as exc:
        conflict = await _conflict(
            db, exc, name=name, isbn_13=isbn_13, series_id=series_id, series_number=series_number
        )
        if conflict is None:
            raise
        raise conflict from None


# --------------------------------------------------------------------------- reads


async def get_author(db: AsyncSession, author_id: uuid.UUID) -> domain.Author:
    author = await catalog.get_author(db, author_id)
    if author is None:
        raise NotFoundError()
    return author


async def get_series(db: AsyncSession, series_id: uuid.UUID) -> domain.Series:
    series = await catalog.get_series(db, series_id)
    if series is None:
        raise NotFoundError()
    return series


async def get_book(db: AsyncSession, book_id: uuid.UUID) -> domain.Book:
    book = await catalog.get_book(db, book_id)
    if book is None:
        raise NotFoundError()
    return book


# --------------------------------------------------------------------------- creates


async def create_author(
    db: AsyncSession,
    actor_id: uuid.UUID,
    *,
    name: str,
    sort_name: str | None = None,
    is_pen_name: bool = False,
    real_name: str | None = None,
) -> domain.Author:
    name = normalize_name(name)
    sort = normalize_name(sort_name) if sort_name else default_sort_name(name)
    real = normalize_name(real_name) if real_name else None
    return await guarded(
        db,
        lambda: catalog.create_author(
            db,
            name=name,
            sort_name=sort,
            is_pen_name=is_pen_name,
            real_name=real,
            actor_id=actor_id,
        ),
        name=name,
    )


async def create_series(db: AsyncSession, actor_id: uuid.UUID, *, name: str) -> domain.Series:
    name = normalize_name(name)
    return await guarded(
        db, lambda: catalog.create_series(db, name=name, actor_id=actor_id), name=name
    )


async def _check_references(
    db: AsyncSession, author_ids: list[uuid.UUID], series_id: uuid.UUID | None
) -> None:
    errors: list[FieldError] = []
    missing = set(author_ids) - await catalog.existing_author_ids(db, author_ids)
    if missing:
        errors.append(FieldError("author_ids", "One or more authors are not in the catalog"))
    if series_id is not None and not await catalog.series_exists(db, series_id):
        errors.append(FieldError("series_id", "That series is not in the catalog"))
    if errors:
        raise ValidationFailed(errors)


async def create_book(db: AsyncSession, actor_id: uuid.UUID, new: NewBook) -> domain.Book:
    await _check_references(db, new.author_ids, new.series_id)
    title = normalize_name(new.title)
    return await guarded(
        db,
        lambda: catalog.create_book(
            db,
            title=title,
            author_ids=new.author_ids,
            series_id=new.series_id,
            series_number=new.series_number,
            isbn_13=new.isbn_13,
            actor_id=actor_id,
        ),
        isbn_13=new.isbn_13,
        series_id=new.series_id,
        series_number=new.series_number,
    )


# --------------------------------------------------------------------------- search


def _as_isbn(q: str) -> str | None:
    try:
        return parse_isbn13(q)
    except ValueError:
        return None


async def search_books(db: AsyncSession, q: str, limit: int = 10) -> list[domain.Book]:
    return await catalog.search_books(db, q.strip(), limit, isbn_13=_as_isbn(q))


async def search_authors(db: AsyncSession, q: str, limit: int = 10) -> list[domain.Author]:
    return await catalog.search_authors(db, q.strip(), limit)


async def search_series(db: AsyncSession, q: str, limit: int = 10) -> list[domain.Series]:
    return await catalog.search_series(db, q.strip(), limit)


# --------------------------------------------------------------------------- updates


async def update_author(
    db: AsyncSession,
    actor_id: uuid.UUID,
    author_id: uuid.UUID,
    changes: dict[str, Any],
) -> domain.Author:
    current = await get_author(db, author_id)
    fields: dict[str, Any] = {}
    if changes.get("name") is not None:
        fields["name"] = normalize_name(changes["name"])
    if "sort_name" in changes:
        sort = changes["sort_name"]
        fields["sort_name"] = (
            normalize_name(sort) if sort else default_sort_name(fields.get("name", current.name))
        )
    pen = changes.get("is_pen_name", current.is_pen_name)
    if pen is None:
        pen = current.is_pen_name
    fields["is_pen_name"] = pen
    real = changes.get("real_name", current.real_name)
    if not pen:
        if changes.get("real_name"):
            raise ValidationFailed.single("real_name", PEN_NAME_FIRST)
        real = None  # unmarking a pen name drops its real name
    fields["real_name"] = normalize_name(real) if real else None
    return await guarded(
        db,
        lambda: catalog.update_author(db, author_id, actor_id, **fields),
        name=fields.get("name"),
    )


async def update_series(
    db: AsyncSession, actor_id: uuid.UUID, series_id: uuid.UUID, *, name: str
) -> domain.Series:
    await get_series(db, series_id)
    name = normalize_name(name)
    return await guarded(
        db, lambda: catalog.update_series(db, series_id, actor_id, name=name), name=name
    )


async def update_book(
    db: AsyncSession,
    actor_id: uuid.UUID,
    book_id: uuid.UUID,
    changes: dict[str, Any],
) -> domain.Book:
    current = await get_book(db, book_id)
    series_id = (
        changes["series_id"]
        if "series_id" in changes
        else (current.series.id if current.series else None)
    )
    if "series_number" in changes:
        number = changes["series_number"]
    elif "series_id" in changes and series_id is None:
        number = None  # leaving a series drops the number
    else:
        number = current.series_number
    if number is not None and series_id is None:
        raise ValidationFailed.single(
            "series_number", "Choose a series first, or leave the number blank"
        )
    author_ids = changes.get("author_ids")
    if author_ids is not None and not author_ids:
        raise ValidationFailed.single("author_ids", "A book needs at least one author")
    await _check_references(db, author_ids or [], series_id if "series_id" in changes else None)
    fields: dict[str, Any] = {"series_id": series_id, "series_number": number}
    if changes.get("title") is not None:
        fields["title"] = normalize_name(changes["title"])
    if "isbn_13" in changes:
        fields["isbn_13"] = changes["isbn_13"]
    isbn = fields.get("isbn_13")
    return await guarded(
        db,
        lambda: catalog.update_book(db, book_id, actor_id, author_ids=author_ids, **fields),
        isbn_13=isbn,
        series_id=series_id,
        series_number=number,
    )
