"""The Author page and favorite authors (spec 011).

Personal data is read only through user-bound repositories (Principle I): my entries
through ``ReadingEntryRepository`` and my favorites through ``FavoriteAuthorRepository``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.models import Author, Book, BookAuthor, ReadingEntry, SeriesRef, Story
from book_tracker.persistence import catalog
from book_tracker.persistence.favorites import FavoriteAuthorRepository
from book_tracker.persistence.readings import ReadingEntryRepository
from book_tracker.services.errors import NotFoundError

logger = logging.getLogger(__name__)

NO_NUMBER = Decimal("Infinity")


@dataclass(frozen=True, slots=True)
class AuthorBookRow:
    book: Book
    entry: ReadingEntry | None  # mine only


@dataclass(frozen=True, slots=True)
class AuthorGroup:
    series: SeriesRef | None  # None: Other books
    rows: tuple[AuthorBookRow, ...]


@dataclass(frozen=True, slots=True)
class AuthorView:
    author: Author
    groups: tuple[AuthorGroup, ...]
    stories: tuple[Story, ...]
    favorite: bool  # mine


async def _author(db: AsyncSession, author_id: uuid.UUID) -> Author:
    author = await catalog.get_author(db, author_id)
    if author is None:
        raise NotFoundError()
    return author


async def author_view(db: AsyncSession, user_id: uuid.UUID, author_id: uuid.UUID) -> AuthorView:
    """The author's books by series (research R2): series by name, then Other books; in a
    series by number (unnumbered last), then title."""
    author = await _author(db, author_id)
    books = await catalog.author_books(db, author_id)  # by title
    entries = await ReadingEntryRepository(db, user_id).list_books([b.id for b in books])
    mine = {entry.book.id: entry for entry in entries}
    by_series: dict[uuid.UUID | None, list[Book]] = {}
    for book in books:
        by_series.setdefault(book.series.id if book.series else None, []).append(book)
    groups = []
    for key, members in by_series.items():
        members.sort(
            key=lambda b: (b.series_number if b.series_number is not None else NO_NUMBER,
                           b.title.lower())
        )  # fmt: skip
        groups.append(
            AuthorGroup(
                series=members[0].series if key is not None else None,
                rows=tuple(AuthorBookRow(book=b, entry=mine.get(b.id)) for b in members),
            )
        )
    groups.sort(key=lambda g: (g.series is None, g.series.name.lower() if g.series else ""))
    return AuthorView(
        author=author,
        groups=tuple(groups),
        stories=tuple(await catalog.author_stories(db, author_id)),
        favorite=await FavoriteAuthorRepository(db, user_id).has(author_id),
    )


async def favorite_authors(db: AsyncSession, user_id: uuid.UUID) -> list[Author]:
    """My favorite authors, by sort name."""
    return await FavoriteAuthorRepository(db, user_id).list()


async def add_favorite(db: AsyncSession, user_id: uuid.UUID, author_id: uuid.UUID) -> None:
    """Idempotent. Unknown author, or one deleted a moment ago (AC-17): not found."""
    await _author(db, author_id)
    if not await FavoriteAuthorRepository(db, user_id).add(author_id):
        raise NotFoundError()
    logger.info("member %s favorited author %s", user_id, author_id)


async def remove_favorite(db: AsyncSession, user_id: uuid.UUID, author_id: uuid.UUID) -> None:
    """Idempotent; unknown author: not found."""
    await _author(db, author_id)
    await FavoriteAuthorRepository(db, user_id).remove(author_id)


async def is_favorite(db: AsyncSession, user_id: uuid.UUID, author_id: uuid.UUID) -> bool:
    return await FavoriteAuthorRepository(db, user_id).has(author_id)


async def favorite_ids(
    db: AsyncSession, user_id: uuid.UUID, author_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Which of these authors are my favorites (spec 017 stars)."""
    return await FavoriteAuthorRepository(db, user_id).among(author_ids)


OFFER_MIN_FINISHED = 2  # spec 017: a second finished book by the author


async def finish_offers(
    db: AsyncSession, user_id: uuid.UUID, book_id: uuid.UUID
) -> list[tuple[BookAuthor, int]]:
    """Spec 017 R4: when my entry for this book is Finished, each of its authors who isn't
    my favorite and whose books I've finished at least twice, with that count."""
    entry = await ReadingEntryRepository(db, user_id).get_by_book(book_id)
    if entry is None or entry.status != ReadingStatus.FINISHED:
        return []
    ids = [author.id for author in entry.book.authors]
    favorites = await FavoriteAuthorRepository(db, user_id).among(ids)
    counts = await ReadingEntryRepository(db, user_id).finished_counts(ids)
    return [
        (author, counts[author.id])
        for author in entry.book.authors
        if author.id not in favorites and counts.get(author.id, 0) >= OFFER_MIN_FINISHED
    ]


@dataclass(frozen=True, slots=True)
class AuthorIndexRow:
    """An Authors page row (spec 018): the author, how many catalog books list them, how
    many of those I've finished, and whether they're my favorite (mine only)."""

    author: Author
    books: int
    read: int
    favorite: bool


@dataclass(frozen=True, slots=True)
class AuthorsIndex:
    rows: tuple[AuthorIndexRow, ...]
    page: int  # clamped to the last page
    page_size: int
    total: int


async def authors_index(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    q: str = "",
    only_favorites: bool = False,
) -> AuthorsIndex:
    """Every catalog author, my favorites first (spec 018 R2): one query for the page, then
    my favorites and my Finished counts for its authors, all user-bound (Principle I)."""
    mine = FavoriteAuthorRepository(db, user_id)
    found, total, page = await catalog.browse_authors(
        db,
        page=page,
        page_size=page_size,
        favorite=mine.author_condition(),
        only_favorites=only_favorites,
        q=q.strip(),
    )
    ids = [author.id for author, _ in found]
    favorites = await mine.among(ids)
    read = await ReadingEntryRepository(db, user_id).finished_counts(ids)
    return AuthorsIndex(
        rows=tuple(
            AuthorIndexRow(author, books, read.get(author.id, 0), author.id in favorites)
            for author, books in found
        ),
        page=page,
        page_size=page_size,
        total=total,
    )
