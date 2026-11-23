"""Shared catalog: authors, series, books and summaries. Returns domain objects only."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, delete, exists, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain import models as domain
from book_tracker.persistence import models
from book_tracker.persistence.mappers import to_author, to_book, to_series, to_story, to_summary

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
    """No book and no story lists the author (spec 008, spec 009 R8)."""
    return ~exists().where(models.BookAuthor.author_id == models.Author.id) & ~exists().where(
        models.StoryAuthor.author_id == models.Author.id
    )


def _not_favorited() -> Any:
    """No member keeps the author as a favorite (spec 011, constitution 2.0.0)."""
    return ~exists().where(models.FavoriteAuthor.author_id == models.Author.id)


def _deletable() -> Any:
    """Spec 008's "unused", plus no favorite (spec 011)."""
    return _has_no_books() & _not_favorited()


async def author_has_works(db: AsyncSession, author_id: uuid.UUID) -> bool:
    """Whether any book or story lists the author: an EXISTS, not the lists themselves."""
    found = await db.scalar(
        select(
            exists().where(models.BookAuthor.author_id == author_id)
            | exists().where(models.StoryAuthor.author_id == author_id)
        )
    )
    return bool(found)


async def author_favorited(db: AsyncSession, author_id: uuid.UUID) -> bool:
    """Whether *any* member favorites the author: the one fact the delete refusal may show
    (constitution 2.0.0). It never says who, or how many."""
    found = await db.scalar(select(exists().where(models.FavoriteAuthor.author_id == author_id)))
    return bool(found)


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
    """Authors no book lists and no member favorites, by sort name (spec 008, 011)."""
    rows = (
        (
            await db.execute(
                select(models.Author)
                .where(_deletable())
                .order_by(func.lower(models.Author.sort_name), models.Author.id)
            )
        )
        .scalars()
        .all()
    )
    return [to_author(row) for row in rows]


async def unused_author_count(db: AsyncSession) -> int:
    count = await db.scalar(select(func.count()).select_from(models.Author).where(_deletable()))
    return int(count or 0)


async def delete_unused_author(db: AsyncSession, author_id: uuid.UUID) -> bool:
    """Delete the author only if no book or story lists it and no member favorites it, in one
    statement, so a link or favorite made meanwhile keeps it (spec 008 FR-003, spec 011).
    False when it wasn't deleted."""
    deleted = await db.execute(
        delete(models.Author)
        .where(models.Author.id == author_id, _deletable())
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


def first_author_key() -> Any:
    """The book's first author's sort name, lower-cased: the Author sort (My books and the
    Catalog page)."""
    return (
        select(func.lower(models.Author.sort_name))
        .join(models.BookAuthor, models.BookAuthor.author_id == models.Author.id)
        .where(models.BookAuthor.book_id == models.Book.id)
        .order_by(models.BookAuthor.position)
        .limit(1)
        .scalar_subquery()
    )


def _book_matches(q: str, *, series: bool) -> list[ColumnElement[bool]]:
    """Title, author name, real name or a story's title (spec 009), and with ``series`` the
    series name (spec 010 R2; the query must join ``Series``)."""
    contains = like_patterns(q)[0]
    by_author = exists().where(
        models.BookAuthor.book_id == models.Book.id,
        models.BookAuthor.author_id == models.Author.id,
        or_(
            models.Author.name.ilike(contains, escape="\\"),
            models.Author.real_name.ilike(contains, escape="\\"),
        ),
    )
    by_story = exists().where(  # spec 009: a collection found by one of its stories
        models.BookStory.book_id == models.Book.id,
        models.BookStory.story_id == models.Story.id,
        models.Story.title.ilike(contains, escape="\\"),
    )
    conditions = [models.Book.title.ilike(contains, escape="\\"), by_author, by_story]
    if series:
        conditions.append(models.Series.name.ilike(contains, escape="\\"))
    return conditions


def _isbn_first(isbn_13: str) -> Any:
    return func.coalesce(models.Book.isbn_13 == isbn_13, False).desc()


async def search_books(
    db: AsyncSession, q: str, limit: int, isbn_13: str | None = None
) -> list[domain.Book]:
    """Type-ahead: title, author name, real name or a story's title (spec 009); an exact
    ISBN match ranks first (research R7)."""
    conditions = _book_matches(q, series=False)
    order: list[Any] = []
    if isbn_13 is not None:
        conditions.append(models.Book.isbn_13 == isbn_13)
        order.append(_isbn_first(isbn_13))
    prefix = like_patterns(q)[1]
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


CATALOG_SORTS = ("title", "-title", "author", "series", "-added")


def _catalog_order(sort: str) -> list[Any]:
    """Spec 010 R4. Ties end on title, then id, so pages are stable."""
    title = func.lower(models.Book.title)
    primary: list[Any]
    if sort == "-title":
        return [title.desc(), models.Book.id.asc()]
    if sort == "author":
        primary = [first_author_key().asc().nulls_last()]
    elif sort == "series":
        primary = [
            func.lower(models.Series.name).asc().nulls_last(),
            models.Book.series_number.asc().nulls_last(),
        ]
    elif sort == "-added":
        primary = [models.Book.created_at.desc()]
    else:
        primary = []
    return [*primary, title.asc(), models.Book.id.asc()]


async def browse_books(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    isbn_13: str | None = None,
    sort: str = "title",
    exclude: ColumnElement[bool] | None = None,
) -> tuple[list[domain.Book], int, int]:
    """The Catalog page (spec 010 R1): (books, total, page), the page clamped to the last
    one. ``exclude`` is a condition from the user-bound reading repository (R3)."""
    filtered = select(models.Book).outerjoin(
        models.Series, models.Series.id == models.Book.series_id
    )
    order: list[Any] = []
    if q:
        conditions = _book_matches(q, series=True)
        if isbn_13 is not None:
            conditions.append(models.Book.isbn_13 == isbn_13)
            order.append(_isbn_first(isbn_13))
        filtered = filtered.where(or_(*conditions))
    if exclude is not None:
        filtered = filtered.where(exclude)
    total = int(await db.scalar(select(func.count()).select_from(filtered.subquery())) or 0)
    page = max(1, min(page, (total + page_size - 1) // page_size))
    rows = (
        (
            await db.execute(
                filtered.order_by(*order, *_catalog_order(sort))
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return [to_book(row) for row in rows], total, page


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


# --------------------------------------------------------------------------- stories (spec 009)


def _stories() -> Select[models.Story]:
    return select(models.Story).execution_options(populate_existing=True)


async def _story_list(db: AsyncSession, query: Select[models.Story]) -> list[domain.Story]:
    rows = (await db.execute(query)).scalars().unique().all()
    return [to_story(row) for row in rows]


async def get_story(db: AsyncSession, story_id: uuid.UUID) -> domain.Story | None:
    row = (await db.execute(_stories().where(models.Story.id == story_id))).scalar_one_or_none()
    return to_story(row) if row else None


async def book_stories(db: AsyncSession, book_id: uuid.UUID) -> list[domain.Story]:
    """The stories a book contains, by series name, then number."""
    return await _story_list(
        db,
        _stories()
        .join(models.BookStory, models.BookStory.story_id == models.Story.id)
        .join(models.Series, models.Series.id == models.Story.series_id)
        .where(models.BookStory.book_id == book_id)
        .order_by(func.lower(models.Series.name), models.Story.series_number),
    )


async def series_stories(db: AsyncSession, series_id: uuid.UUID) -> list[domain.Story]:
    """Every story in a series, by number."""
    return await _story_list(
        db,
        _stories().where(models.Story.series_id == series_id).order_by(models.Story.series_number),
    )


async def author_stories(db: AsyncSession, author_id: uuid.UUID) -> list[domain.Story]:
    """The stories that list this author, by title."""
    return await _story_list(
        db,
        _stories()
        .join(models.StoryAuthor, models.StoryAuthor.story_id == models.Story.id)
        .where(models.StoryAuthor.author_id == author_id)
        .order_by(func.lower(models.Story.title), models.Story.id),
    )


async def find_story_by_series_number(
    db: AsyncSession, series_id: uuid.UUID, number: Decimal
) -> domain.Story | None:
    row = (
        await db.execute(
            _stories().where(
                models.Story.series_id == series_id, models.Story.series_number == number
            )
        )
    ).scalar_one_or_none()
    return to_story(row) if row else None


async def search_stories(db: AsyncSession, q: str, limit: int) -> list[domain.Story]:
    contains, prefix = like_patterns(q)
    return await _story_list(
        db,
        _stories()
        .where(models.Story.title.ilike(contains, escape="\\"))
        .order_by(
            models.Story.title.ilike(prefix, escape="\\").desc(),
            func.lower(models.Story.title),
            models.Story.id,
        )
        .limit(limit),
    )


async def story_matches(
    db: AsyncSession, book_ids: list[uuid.UUID], q: str
) -> dict[uuid.UUID, str]:
    """For each of these books, the first of its story titles that matches ``q`` (R7)."""
    if not book_ids:
        return {}
    contains = like_patterns(q)[0]
    rows = await db.execute(
        select(models.BookStory.book_id, models.Story.title)
        .join(models.Story, models.Story.id == models.BookStory.story_id)
        .where(
            models.BookStory.book_id.in_(book_ids),
            models.Story.title.ilike(contains, escape="\\"),
        )
        .order_by(models.BookStory.book_id, models.Story.series_number, models.Story.id)
    )
    found: dict[uuid.UUID, str] = {}
    for book_id, title in rows:
        found.setdefault(book_id, title)
    return found


async def create_story(
    db: AsyncSession,
    *,
    title: str,
    author_ids: list[uuid.UUID],
    series_id: uuid.UUID,
    series_number: Decimal,
    actor_id: uuid.UUID,
) -> uuid.UUID:
    story_id = uuid.uuid4()
    await db.execute(
        insert(models.Story).values(
            id=story_id,
            title=title,
            series_id=series_id,
            series_number=series_number,
            created_by=actor_id,
            updated_by=actor_id,
        )
    )
    await _set_story_authors(db, story_id, author_ids)
    return story_id


async def _set_story_authors(
    db: AsyncSession, story_id: uuid.UUID, author_ids: list[uuid.UUID]
) -> None:
    await db.execute(delete(models.StoryAuthor).where(models.StoryAuthor.story_id == story_id))
    await db.execute(
        insert(models.StoryAuthor),
        [
            {"story_id": story_id, "author_id": author_id, "position": position}
            for position, author_id in enumerate(author_ids, start=1)
        ],
    )


async def link_story(db: AsyncSession, book_id: uuid.UUID, story_id: uuid.UUID) -> bool:
    """Put the story in the book; False when it already was."""
    linked = await db.execute(
        pg_insert(models.BookStory)
        .values(book_id=book_id, story_id=story_id)
        .on_conflict_do_nothing()
        .returning(models.BookStory.story_id)
    )
    return linked.scalar_one_or_none() is not None


async def unlink_story(
    db: AsyncSession, book_id: uuid.UUID, story_id: uuid.UUID
) -> tuple[bool, bool]:
    """Take the story out of the book, then delete it if no book holds it any more, so a
    story is never in no book (research R2). Returns (removed, deleted)."""
    removed = await db.execute(
        delete(models.BookStory)
        .where(models.BookStory.book_id == book_id, models.BookStory.story_id == story_id)
        .returning(models.BookStory.story_id)
    )
    if removed.scalar_one_or_none() is None:
        return False, False
    try:
        async with db.begin_nested():
            deleted = await db.execute(
                delete(models.Story)
                .where(
                    models.Story.id == story_id,
                    ~exists().where(models.BookStory.story_id == models.Story.id),
                )
                .returning(models.Story.id)
            )
            return True, deleted.scalar_one_or_none() is not None
    except IntegrityError:
        # Another member put the story in a book while this delete waited on their lock:
        # the NOT EXISTS above didn't see it, and the RESTRICT foreign key did (PR #28
        # review). The story stays, in that book.
        return True, False


async def update_story(
    db: AsyncSession,
    story_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    author_ids: list[uuid.UUID] | None = None,
    **fields: object,
) -> bool:
    """False when the story no longer exists."""
    updated = await db.execute(
        update(models.Story)
        .where(models.Story.id == story_id)
        .values(**fields, updated_by=actor_id, updated_at=func.now())
        .returning(models.Story.id)
    )
    if updated.scalar_one_or_none() is None:
        return False
    if author_ids is not None:
        await _set_story_authors(db, story_id, author_ids)
    return True


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
