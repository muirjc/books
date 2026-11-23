"""Shared catalog use cases. Any member may add or edit entries (FR-009).

Uniqueness is left to the database; a violation is turned into a ``ConflictError`` that
names the existing row, so the caller can offer it instead (research R9).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain import models as domain
from book_tracker.domain.values import (
    PEN_NAME_FIRST,
    default_sort_name,
    format_series_number,
    normalize_name,
    parse_isbn13,
    similar_names,
)
from book_tracker.persistence import catalog
from book_tracker.services.errors import (
    ConflictError,
    FieldError,
    NotFoundError,
    StoryNumberTaken,
    ValidationFailed,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

CONFLICT_TITLES = {
    "author_exists": "An author with this name is already in the catalog",
    "series_exists": "A series with this name is already in the catalog",
    "isbn_exists": "A book with this ISBN is already in the catalog",
    "series_number_taken": "Another book already has this number in the series",
    "story_number_taken": "Another story already has this number in the series",
}


@dataclass(frozen=True, slots=True)
class NewBook:
    title: str
    author_ids: list[uuid.UUID]
    series_id: uuid.UUID | None = None
    series_number: Decimal | None = None
    isbn_13: str | None = None
    summary: str | None = None
    release_date: date | None = None  # spec 007
    summary_draft_id: str | None = None  # spec 012: the AI draft the summary came from


@dataclass(frozen=True, slots=True)
class NewStory:
    """A story to add to a book (spec 009)."""

    title: str
    author_ids: list[uuid.UUID]
    series_id: uuid.UUID
    series_number: Decimal


@dataclass(frozen=True, slots=True)
class StoryForBook:
    """A story for a new book (spec 013): an existing one by ``story_id``, or a new one
    whose missing series and authors are the book's."""

    story_id: uuid.UUID | None = None
    title: str = ""
    series_number: Decimal | None = None
    series_id: uuid.UUID | None = None
    author_ids: list[uuid.UUID] | None = None


NO_STORY_SERIES = "Choose a series for this story, or give the book a series"
AUTHOR_DELETED = "An author you chose was just deleted from the catalog. Choose the author again."
STORY_DELETED = "That story was just deleted from the catalog."


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
    elif (
        constraint == "story_series_number_uq"
        and series_id is not None
        and series_number is not None
    ):
        story = await catalog.find_story_by_series_number(db, series_id, series_number)
        if story is not None:
            return story_conflict(story)
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
        if conflict is not None:
            raise conflict from None
        if _constraint(exc) in ("book_author_author_id_fkey", "story_author_author_id_fkey"):
            # A chosen author was deleted after the check (spec 008, PR #24 review).
            raise ValidationFailed.single("author_ids", AUTHOR_DELETED) from None
        raise


def story_label(story: domain.Story) -> str:
    """ "#2.5 Publicity and Advertising" """
    return f"#{format_series_number(story.series_number)} {story.title}"


def story_conflict(story: domain.Story) -> ConflictError:
    return ConflictError(
        "story_number_taken",
        CONFLICT_TITLES["story_number_taken"],
        existing_id=story.id,
        existing_label=story_label(story),
    )


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


async def author_named(db: AsyncSession, name: str) -> bool:
    """Whether a catalog author has exactly this name, ignoring capitals."""
    return await catalog.find_author_by_name(db, name) is not None


async def series_named(db: AsyncSession, name: str) -> bool:
    """Whether a catalog series has exactly this name, ignoring capitals."""
    return await catalog.find_series_by_name(db, name) is not None


Candidates = list[tuple[uuid.UUID, str, tuple[str, ...]]]


async def author_id_named(db: AsyncSession, name: str) -> uuid.UUID | None:
    """The catalog author with exactly this name (any case), if any (spec 013)."""
    found = await catalog.find_author_by_name(db, name)
    return found[0] if found else None


async def series_id_named(db: AsyncSession, name: str) -> uuid.UUID | None:
    """The catalog series with exactly this name (any case), if any (spec 013)."""
    found = await catalog.find_series_by_name(db, name)
    return found[0] if found else None


async def author_candidates(db: AsyncSession) -> Candidates:
    """Every catalog author as (id, name, names to compare: name and real name)."""
    return [
        (author_id, label, (label, real) if real else (label,))
        for author_id, label, real in await catalog.author_names(db)
    ]


async def series_candidates(db: AsyncSession) -> Candidates:
    """Every catalog series as (id, name, (name,))."""
    return [(sid, label, (label,)) for sid, label in await catalog.series_names(db)]


async def similar_authors(db: AsyncSession, name: str) -> list[tuple[uuid.UUID, str]]:
    """Up to three catalog authors whose name or real name looks like ``name``
    (spec 005 R3), best first."""
    return similar_names(name, await author_candidates(db))


async def similar_series(db: AsyncSession, name: str) -> list[tuple[uuid.UUID, str]]:
    """Up to three catalog series whose name looks like ``name`` (spec 005 R3)."""
    return similar_names(name, await series_candidates(db))


async def author_books(db: AsyncSession, author_id: uuid.UUID) -> list[domain.Book]:
    return await catalog.author_books(db, author_id)


async def unused_authors(db: AsyncSession) -> list[domain.Author]:
    return await catalog.unused_authors(db)


async def author_favorited(db: AsyncSession, author_id: uuid.UUID) -> bool:
    """Whether any member favorites the author (spec 011's delete rule only)."""
    return await catalog.author_favorited(db, author_id)


async def unused_author_count(db: AsyncSession) -> int:
    return await catalog.unused_author_count(db)


async def _try_delete(db: AsyncSession, author_id: uuid.UUID) -> bool:
    try:
        async with db.begin_nested():
            return await catalog.delete_unused_author(db, author_id)
    except IntegrityError:  # the foreign keys backstop the NOT EXISTS checks
        return False


async def delete_author(db: AsyncSession, actor_id: uuid.UUID, author_id: uuid.UUID) -> None:
    """Delete an author no book lists; any member may (spec 008). Unknown → not found; with
    books (even one linked a moment ago) → conflict, and nothing is deleted. Favorited by any
    member (spec 011) → conflict ``author_is_favorite``, naming nobody. If whatever blocked
    the delete has gone by the time it is classified, the delete is tried once more (PR #30
    review)."""
    for _ in range(2):
        if await _try_delete(db, author_id):
            logger.info("author %s deleted by member %s", author_id, actor_id)
            return
        if await catalog.get_author(db, author_id) is None:
            raise NotFoundError()  # unknown, or deleted by someone else meanwhile
        if await catalog.author_has_works(db, author_id):
            raise ConflictError("author_has_books", "This author has books")
        if await catalog.author_favorited(db, author_id):
            raise ConflictError(
                "author_is_favorite", "A family member has this author as a favorite"
            )
    raise ConflictError("author_has_books", "This author has books")  # changing under us


async def upcoming_books(db: AsyncSession, today: date) -> list[domain.Book]:
    """Catalog books not out yet, soonest first (spec 007)."""
    return await catalog.upcoming_books(db, today)


async def series_books(db: AsyncSession, series_id: uuid.UUID) -> list[domain.Book]:
    """The shared catalog's books in a series, so one held by nobody's list can still be
    reached and renumbered (books-cay)."""
    return await catalog.list_series_books(db, series_id)


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
            release_date=new.release_date,
            actor_id=actor_id,
        ),
        isbn_13=new.isbn_13,
        series_id=new.series_id,
        series_number=new.series_number,
    )


# --------------------------------------------------------------------------- search


def as_isbn(q: str) -> str | None:
    try:
        return parse_isbn13(q)
    except ValueError:
        return None


async def search_books(db: AsyncSession, q: str, limit: int = 10) -> list[domain.Book]:
    return await catalog.search_books(db, q.strip(), limit, isbn_13=as_isbn(q))


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
    author = await guarded(
        db,
        lambda: catalog.update_author(db, author_id, actor_id, **fields),
        name=fields.get("name"),
    )
    if author is None:
        raise NotFoundError()  # deleted by another member meanwhile (spec 008)
    return author


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
    if "release_date" in changes:
        fields["release_date"] = changes["release_date"]
    isbn = fields.get("isbn_13")
    return await guarded(
        db,
        lambda: catalog.update_book(db, book_id, actor_id, author_ids=author_ids, **fields),
        isbn_13=isbn,
        series_id=series_id,
        series_number=number,
    )


# --------------------------------------------------------------------------- stories (spec 009)


async def get_story(db: AsyncSession, story_id: uuid.UUID) -> domain.Story:
    story = await catalog.get_story(db, story_id)
    if story is None:
        raise NotFoundError()
    return story


async def book_stories(db: AsyncSession, book_id: uuid.UUID) -> list[domain.Story]:
    return await catalog.book_stories(db, book_id)


async def series_stories(db: AsyncSession, series_id: uuid.UUID) -> list[domain.Story]:
    return await catalog.series_stories(db, series_id)


async def author_stories(db: AsyncSession, author_id: uuid.UUID) -> list[domain.Story]:
    return await catalog.author_stories(db, author_id)


async def story_at(db: AsyncSession, series_id: uuid.UUID, number: Decimal) -> domain.Story | None:
    """The story holding this number in the series, if any (AC-05: offered, not doubled)."""
    return await catalog.find_story_by_series_number(db, series_id, number)


async def search_stories(db: AsyncSession, q: str, limit: int = 10) -> list[domain.Story]:
    return await catalog.search_stories(db, q.strip(), limit)


async def story_matches(
    db: AsyncSession, book_ids: list[uuid.UUID], q: str
) -> dict[uuid.UUID, str]:
    return await catalog.story_matches(db, book_ids, q.strip())


def _story_deleted(exc: IntegrityError) -> bool:
    return _constraint(exc) == "book_story_story_id_fkey"


async def add_new_story(
    db: AsyncSession, actor_id: uuid.UUID, book_id: uuid.UUID, new: NewStory
) -> domain.Story:
    """Create a story and put it in the book, in one savepoint. A number another story
    holds is a ``story_number_taken`` conflict naming it."""
    if not await catalog.book_exists(db, book_id):
        raise NotFoundError()
    await _check_references(db, new.author_ids, new.series_id)
    title = normalize_name(new.title)

    async def create() -> uuid.UUID:
        story_id = await catalog.create_story(
            db,
            title=title,
            author_ids=new.author_ids,
            series_id=new.series_id,
            series_number=new.series_number,
            actor_id=actor_id,
        )
        await catalog.link_story(db, book_id, story_id)
        return story_id

    story_id = await guarded(db, create, series_id=new.series_id, series_number=new.series_number)
    logger.info("story %s added to book %s by member %s", story_id, book_id, actor_id)
    return await get_story(db, story_id)


async def add_existing_story(
    db: AsyncSession, actor_id: uuid.UUID, book_id: uuid.UUID, story_id: uuid.UUID
) -> tuple[domain.Story, bool]:
    """Put an existing story in the book as well (AC-17). Returns (story, added); added is
    False when the book already had it."""
    if not await catalog.book_exists(db, book_id):
        raise NotFoundError()
    await get_story(db, story_id)
    try:
        async with db.begin_nested():
            added = await catalog.link_story(db, book_id, story_id)
    except IntegrityError as exc:
        if _story_deleted(exc):  # its last link was removed meanwhile (research R2)
            raise NotFoundError() from None
        raise
    if added:
        logger.info("story %s added to book %s by member %s", story_id, book_id, actor_id)
    return await get_story(db, story_id), added


async def stories_at(
    db: AsyncSession, pairs: list[tuple[uuid.UUID, Decimal]]
) -> dict[tuple[uuid.UUID, Decimal], domain.Story]:
    """The stories holding any of these (series, number) pairs (spec 013, one query)."""
    return await catalog.stories_at(db, pairs)


async def add_book_stories(
    db: AsyncSession, actor_id: uuid.UUID, book: domain.Book, stories: Sequence[StoryForBook]
) -> None:
    """Put each story in a just-created book, in order (spec 013). The caller's transaction
    makes it all-or-nothing; errors name the item as ``stories.<i>.<field>``.

    Up to 50 items, so lookups are batched: references are checked once, and numbers
    already taken are found in one query before anything is inserted."""
    new: list[tuple[int, NewStory]] = []
    book_authors = [author.id for author in book.authors]
    for i, item in enumerate(stories):
        if item.story_id is not None:
            continue
        series_id = item.series_id or (book.series.id if book.series else None)
        if series_id is None:
            raise ValidationFailed.single(f"stories.{i}.series_id", NO_STORY_SERIES)
        assert item.series_number is not None  # noqa: S101 - callers validate it
        title = normalize_name(item.title)
        new.append(
            (i, NewStory(title, item.author_ids or book_authors, series_id, item.series_number))
        )
    seen: dict[tuple[uuid.UUID, Decimal], int] = {}
    for i, n in new:  # e.g. two rows that a "Use …" name choice made one series (PR #33)
        first = seen.setdefault((n.series_id, n.series_number), i)
        if first != i:
            raise ValidationFailed.single(
                f"stories.{i}.series_number",
                "Has the same series and number as another story in this save",
            )
    await _check_story_references(db, new)
    taken = await stories_at(db, [(n.series_id, n.series_number) for _, n in new])
    for i, n in new:
        if (n.series_id, n.series_number) in taken:
            story = taken[(n.series_id, n.series_number)]
            raise StoryNumberTaken(i, story, story_label(story))
    created = {i: n for i, n in new}
    for i, item in enumerate(stories):
        if item.story_id is not None:
            try:
                await add_existing_story(db, actor_id, book.id, item.story_id)
            except NotFoundError:
                raise ValidationFailed.single(f"stories.{i}.story_id", STORY_DELETED) from None
            continue
        await _create_book_story(db, actor_id, book.id, i, created[i])
    logger.info("%d stories added to new book %s by member %s", len(stories), book.id, actor_id)


async def _check_story_references(db: AsyncSession, new: list[tuple[int, NewStory]]) -> None:
    """Every author and series named exists; else the first item naming a missing one."""
    author_ids = list({a for _, n in new for a in n.author_ids})
    known_authors = await catalog.existing_author_ids(db, author_ids)
    missing_series = {
        series_id
        for series_id in {n.series_id for _, n in new}
        if not await catalog.series_exists(db, series_id)
    }
    for i, n in new:
        errors = []
        if set(n.author_ids) - known_authors:
            errors.append(
                FieldError(f"stories.{i}.author_ids", "One or more authors are not in the catalog")
            )
        if n.series_id in missing_series:
            errors.append(FieldError(f"stories.{i}.series_id", "That series is not in the catalog"))
        if errors:
            raise ValidationFailed(errors)


async def _create_book_story(
    db: AsyncSession, actor_id: uuid.UUID, book_id: uuid.UUID, index: int, new: NewStory
) -> None:
    async def create() -> None:
        story_id = await catalog.create_story(
            db, title=new.title, author_ids=new.author_ids, series_id=new.series_id,
            series_number=new.series_number, actor_id=actor_id,
        )  # fmt: skip
        await catalog.link_story(db, book_id, story_id)

    try:
        await guarded(db, create, series_id=new.series_id, series_number=new.series_number)
    except ValidationFailed as exc:  # e.g. an author deleted meanwhile (spec 008)
        raise ValidationFailed(
            [FieldError(f"stories.{index}.{e.field}", e.message) for e in exc.errors]
        ) from None
    except ConflictError as exc:  # another member took the number a moment ago (AC-16)
        story = await story_at(db, new.series_id, new.series_number)
        if story is None or exc.code != "story_number_taken":  # pragma: no cover - defensive
            raise
        raise StoryNumberTaken(index, story, story_label(story)) from None


async def update_story(
    db: AsyncSession, actor_id: uuid.UUID, story_id: uuid.UUID, changes: dict[str, Any]
) -> domain.Story:
    current = await get_story(db, story_id)
    author_ids = changes.get("author_ids")
    if author_ids is not None and not author_ids:
        raise ValidationFailed.single("author_ids", "A story needs at least one author")
    series_id = changes.get("series_id") or current.series.id
    number = changes.get("series_number")
    if number is None:
        number = current.series_number
    await _check_references(
        db, author_ids or [], series_id if series_id != current.series.id else None
    )
    fields: dict[str, Any] = {"series_id": series_id, "series_number": number}
    if changes.get("title") is not None:
        fields["title"] = normalize_name(changes["title"])
    updated = await guarded(
        db,
        lambda: catalog.update_story(db, story_id, actor_id, author_ids=author_ids, **fields),
        series_id=series_id,
        series_number=number,
    )
    if not updated:
        raise NotFoundError()  # deleted by another member meanwhile
    return await get_story(db, story_id)


async def remove_story(
    db: AsyncSession, actor_id: uuid.UUID, book_id: uuid.UUID, story_id: uuid.UUID
) -> bool:
    """Take the story out of the book; True when that deleted it from the catalog (it was
    in no other book). Not in this book → not found."""
    removed, deleted = await catalog.unlink_story(db, book_id, story_id)
    if not removed:
        raise NotFoundError()
    logger.info(
        "story %s removed from book %s by member %s%s",
        story_id, book_id, actor_id, " (deleted)" if deleted else "",
    )  # fmt: skip
    return deleted
