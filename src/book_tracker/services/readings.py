"""A member's own reading list (FR-016 – FR-020, FR-029).

Every operation goes through a ``ReadingEntryRepository`` bound to the session user.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.models import Book, BookRef, ReadingEntry, ReadingEntryPage, Series, Story
from book_tracker.domain.values import SERIES_NUMBER_MAX
from book_tracker.persistence import catalog
from book_tracker.persistence.readings import SORTS, FilterOptions, ReadingEntryRepository
from book_tracker.services import catalog as catalog_service
from book_tracker.services import summaries
from book_tracker.services.errors import (
    ConflictError,
    FieldError,
    NotFoundError,
    ValidationFailed,
)

MAX_TIMES_READ = 99


def apply_status_change(
    old_status: ReadingStatus | None,
    new_status: ReadingStatus,
    times_read: int,
    override: int | None,
) -> int:
    """Times-read rule (FR-029).

    Adding: 1 for Finished, 0 otherwise. A change *into* Finished adds one (capped at 99).
    Other changes, including "Read again" (Finished → Reading), keep the count. An explicit
    count in the same request replaces the automatic value.
    """
    if override is not None:
        return override
    if old_status is None:
        return 1 if new_status is ReadingStatus.FINISHED else 0
    if new_status is ReadingStatus.FINISHED and old_status is not ReadingStatus.FINISHED:
        return min(times_read + 1, MAX_TIMES_READ)
    return times_read


def _already_on_list(entry: ReadingEntry) -> ConflictError:
    return ConflictError(
        "already_on_list",
        "Already on your list",
        existing_id=entry.id,
        existing_label=entry.book.title,
    )


async def list_entries(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    author_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
    status: ReadingStatus | None = None,
    sort: str = "title",
    upcoming_after: date | None = None,
    favorite_authors: bool = False,
    min_rating: int | None = None,
    rated: bool | None = None,
) -> ReadingEntryPage:
    """My list, sorted, filtered and searched (FR-021, FR-023). With ``upcoming_after``
    (today), only books not out yet, soonest first (spec 007). With ``favorite_authors``,
    only books by one of my favorite authors (spec 011). ``min_rating`` and ``rated``
    filter by my rating (spec 020)."""
    return await ReadingEntryRepository(db, user_id).list(
        page=page,
        page_size=page_size,
        q=q.strip() if q and q.strip() else None,
        author_id=author_id,
        series_id=series_id,
        status=status,
        sort=sort if sort in SORTS else "title",
        upcoming_after=upcoming_after,
        favorite_authors=favorite_authors,
        min_rating=min_rating,
        rated=rated,
    )


@dataclass(frozen=True, slots=True)
class UpcomingView:
    """The Upcoming page (spec 007 R5): my books not out yet, then the family catalog's
    other books not out yet."""

    mine: tuple[ReadingEntry, ...]
    others: tuple[Book, ...]


async def upcoming_view(db: AsyncSession, user_id: uuid.UUID, today: date) -> UpcomingView:
    """Only my own entries are read (Principle I); "others" is catalog data minus my
    books."""
    repo = ReadingEntryRepository(db, user_id)
    mine = await repo.list_upcoming(today)
    books = await catalog_service.upcoming_books(db, today)
    on_my_list = await repo.book_ids_on_list([book.id for book in books])
    return UpcomingView(
        mine=mine, others=tuple(book for book in books if book.id not in on_my_list)
    )


@dataclass(frozen=True, slots=True)
class CatalogRow:
    """A Catalog page row (spec 010): a catalog book and my own entry for it, if any."""

    book: Book
    entry: ReadingEntry | None


@dataclass(frozen=True, slots=True)
class CatalogPage:
    rows: tuple[CatalogRow, ...]
    page: int  # clamped to the last page
    page_size: int
    total: int


async def catalog_view(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    q: str = "",
    sort: str = "title",
    not_mine: bool = False,
) -> CatalogPage:
    """Every catalog book, searched, sorted and paged (spec 010). My entries come only from
    the user-bound repository (Principle I): the markers and the Not on my list filter."""
    repo = ReadingEntryRepository(db, user_id)
    q = q.strip()
    books, total, page = await catalog.browse_books(
        db,
        page=page,
        page_size=page_size,
        q=q or None,
        isbn_13=catalog_service.as_isbn(q) if q else None,
        sort=sort if sort in catalog.CATALOG_SORTS else "title",
        exclude=repo.not_on_list() if not_mine else None,
    )
    mine = {entry.book.id: entry for entry in await repo.list_books([b.id for b in books])}
    return CatalogPage(
        rows=tuple(CatalogRow(book=b, entry=mine.get(b.id)) for b in books),
        page=page,
        page_size=page_size,
        total=total,
    )


@dataclass(frozen=True, slots=True)
class SeriesIndexRow:
    """A Series view row (spec 018): the series, its catalog books, and how many of those
    I've finished (mine only)."""

    series: Series
    books: int
    read: int


@dataclass(frozen=True, slots=True)
class SeriesIndex:
    rows: tuple[SeriesIndexRow, ...]
    page: int  # clamped to the last page
    page_size: int
    total: int


async def series_index(
    db: AsyncSession, user_id: uuid.UUID, *, page: int, page_size: int, q: str = ""
) -> SeriesIndex:
    """Every series by name (spec 018 R4), with my Finished counts from the user-bound
    repository (Principle I)."""
    found, total, page = await catalog.browse_series(
        db, page=page, page_size=page_size, q=q.strip()
    )
    read = await ReadingEntryRepository(db, user_id).finished_counts_by_series(
        [series.id for series, _ in found]
    )
    return SeriesIndex(
        rows=tuple(SeriesIndexRow(s, books, read.get(s.id, 0)) for s, books in found),
        page=page,
        page_size=page_size,
        total=total,
    )


async def now_out(db: AsyncSession, user_id: uuid.UUID, today: date) -> tuple[ReadingEntry, ...]:
    """My Want to read books released in the last 30 days (spec 007 R6)."""
    return await ReadingEntryRepository(db, user_id).list_now_out(today)


GAP_RUN_ROWS = 3  # a run of missing numbers longer than this is one row (spec 006)


@dataclass(frozen=True, slots=True)
class SeriesRow:
    """A series page row: a catalog book with my entry (or none); a story (spec 009) with
    the books it's in, my entry for each, and my derived status; or a gap in the numbering
    from ``first`` to ``last``."""

    book: Book | None = None
    entry: ReadingEntry | None = None
    first: int = 0
    last: int = 0
    contains: tuple[Decimal, ...] = ()  # a book's story numbers in this series (AC-14)
    story: Story | None = None
    story_books: tuple[tuple[BookRef, ReadingEntry | None], ...] = ()
    story_status: ReadingStatus | None = None
    story_finished_on: date | None = None
    story_entry: ReadingEntry | None = None  # the entry story_status comes from (spec 015)

    @property
    def number(self) -> Decimal | None:
        if self.story is not None:
            return self.story.series_number
        return self.book.series_number if self.book is not None else None


@dataclass(frozen=True, slots=True)
class SeriesView:
    rows: tuple[SeriesRow, ...]
    finished: int  # my Finished entries among the listed books
    total: int  # catalog books listed; gaps and stories don't count
    stories_finished: int = 0  # stories in a book I've finished (spec 009 AC-13)
    stories_total: int = 0
    # Spec 014 AC-12: the next whole number after the highest book or story, for "Add #n".
    next_number: int | None = None


def _gap_runs(numbers: set[Decimal], top: int) -> list[tuple[int, int]]:
    """Runs of whole numbers 1..top that no book or story has exactly; long runs as one. A
    book or story numbered between two missing numbers (say 3.5) ends a run, so it keeps
    its place."""
    missing = [n for n in range(1, top + 1) if n not in numbers]
    between = {math.floor(n) for n in numbers if n != math.floor(n)}  # 3.5 → between 3 and 4
    runs: list[list[int]] = []
    for n in missing:
        if runs and runs[-1][-1] == n - 1 and (n - 1) not in between:
            runs[-1].append(n)
        else:
            runs.append([n])
    out: list[tuple[int, int]] = []
    for run in runs:
        if len(run) > GAP_RUN_ROWS:
            out.append((run[0], run[-1]))
        else:
            out.extend((n, n) for n in run)
    return out


STATUS_RANK = {ReadingStatus.FINISHED: 0, ReadingStatus.READING: 1, ReadingStatus.WANT_TO_READ: 2}


def _story_row(story: Story, mine: dict[uuid.UUID, ReadingEntry]) -> SeriesRow:
    """My place in a story is my best entry among the books it's in (research R3): Finished
    (latest date), else Reading, else Want to read."""
    books = tuple((ref, mine.get(ref.id)) for ref in story.books)
    held = [found for _, found in books if found is not None]
    status = min((e.status for e in held), key=STATUS_RANK.__getitem__, default=None)
    dates = [e.finished_on for e in held if e.status is status and e.finished_on is not None]
    finished_on = max(dates) if status is ReadingStatus.FINISHED and dates else None
    # The entry the status came from: the badge links to it (PR #35 review).
    chosen = [e for e in held if e.status is status]
    entry = max(chosen, key=lambda e: e.finished_on or date.min) if chosen else None
    return SeriesRow(
        story=story, story_books=books, story_status=status, story_finished_on=finished_on,
        story_entry=entry,
    )  # fmt: skip


def series_rows(
    books: Sequence[Book], entries: Sequence[ReadingEntry], stories: Sequence[Story] = ()
) -> SeriesView:
    """Merge a series' catalog books (in catalog order: by number, then unnumbered) and its
    stories (by number) with my entries, adding gap rows for missing whole numbers
    (spec 006 research R2, spec 009 R4). At one number the book comes first. ``entries``
    are mine for the series' books and for every book containing one of its stories."""
    mine = {entry.book.id: entry for entry in entries}
    holds: dict[uuid.UUID, list[Decimal]] = {}
    for story in stories:
        if story.series_number is None:  # a series' own stories always have one (spec 019)
            continue
        for ref in story.books:
            holds.setdefault(ref.id, []).append(story.series_number)
    rows = [
        SeriesRow(
            book=book, entry=mine.get(book.id), contains=tuple(sorted(holds.get(book.id, ())))
        )
        for book in books
    ] + [_story_row(story, mine) for story in stories]
    numbered = sorted(
        (row for row in rows if row.number is not None),
        key=lambda row: (row.number, row.story is not None),
    )
    unnumbered = [row for row in rows if row.number is None]
    numbers = {row.number for row in numbered if row.number is not None}
    gaps = _gap_runs(numbers, math.floor(max(numbers)) if numbers else 0)
    ordered: list[SeriesRow] = []
    for row in numbered:
        while gaps and row.number is not None and row.number > gaps[0][1]:
            ordered.append(SeriesRow(first=gaps[0][0], last=gaps[0][1]))
            gaps.pop(0)
        ordered.append(row)
    ordered += unnumbered
    finished = sum(
        1
        for row in ordered
        if row.story is None
        and row.entry is not None
        and row.entry.status is ReadingStatus.FINISHED
    )
    return SeriesView(
        rows=tuple(ordered),
        finished=finished,
        total=len(books),
        stories_finished=sum(1 for row in ordered if row.story_status is ReadingStatus.FINISHED),
        stories_total=len(stories),
        next_number=next_number(numbers),
    )


def next_number(numbers: set[Decimal]) -> int | None:
    """The next whole number after the highest, or None when nothing is numbered or it
    would pass the highest number a book can have (spec 014 AC-12)."""
    if not numbers:
        return None
    following = math.floor(max(numbers)) + 1
    return following if following <= SERIES_NUMBER_MAX else None


async def series_view(
    db: AsyncSession, user_id: uuid.UUID, series_id: uuid.UUID
) -> tuple[Series, tuple[ReadingEntry, ...]]:
    """My books in one series, in reading order (FR-022; the JSON API). Unknown series →
    not found."""
    series = await catalog_service.get_series(db, series_id)
    return series, await ReadingEntryRepository(db, user_id).list_series(series_id)


async def whole_series_view(
    db: AsyncSession, user_id: uuid.UUID, series_id: uuid.UUID
) -> tuple[Series, SeriesView]:
    """Every catalog book and story in a series with my own entries, and gaps (spec 006,
    spec 009, the series page). Only my entries are read (Principle I). Unknown series →
    not found."""
    series = await catalog_service.get_series(db, series_id)
    books = await catalog_service.series_books(db, series_id)
    stories = await catalog_service.series_stories(db, series_id)
    book_ids = {book.id for book in books} | {ref.id for s in stories for ref in s.books}
    entries = await ReadingEntryRepository(db, user_id).list_books(book_ids)
    return series, series_rows(books, entries, stories)


async def filter_options(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[FilterOptions, FilterOptions]:
    return await ReadingEntryRepository(db, user_id).filter_options()


async def entry_for_book(
    db: AsyncSession, user_id: uuid.UUID, book_id: uuid.UUID
) -> ReadingEntry | None:
    """My entry for this book, if I have one (spec 014 back links; Principle I)."""
    return await ReadingEntryRepository(db, user_id).get_by_book(book_id)


async def get_entry(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> ReadingEntry:
    entry = await ReadingEntryRepository(db, user_id).get(entry_id)
    if entry is None:
        raise NotFoundError()
    return entry


async def add_entry(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    book_id: uuid.UUID | None = None,
    new_book: catalog_service.NewBook | None = None,
    status: ReadingStatus = ReadingStatus.FINISHED,
    finished_on: date | None = None,
    notes: str | None = None,
    pre_ordered: bool = False,
    rating: int | None = None,
    now: datetime | None = None,
    stories: Sequence[catalog_service.StoryForBook] = (),
) -> ReadingEntry:
    """``now`` is the app clock; a summary from an AI draft is judged by it (spec 012).

    ``stories`` go in the new book (spec 013); the caller's transaction makes the book, its
    stories and the entry all-or-nothing."""
    repo = ReadingEntryRepository(db, user_id)
    if stories and new_book is None:
        raise ValidationFailed.single("stories", "Stories can only be added with a new book")
    if new_book is not None:
        try:
            book = await catalog_service.create_book(db, user_id, new_book)
        except ValidationFailed as exc:
            raise ValidationFailed(
                [FieldError(f"new_book.{e.field}", e.message) for e in exc.errors]
            ) from None
        book_id = book.id
        if new_book.summary:
            await summaries.save_summary(
                db, user_id, book_id, new_book.summary,
                draft_id=new_book.summary_draft_id, now=now or datetime.now(UTC),
            )  # fmt: skip
        if stories:
            await catalog_service.add_book_stories(db, user_id, book, stories)
    elif book_id is None or not await catalog.book_exists(db, book_id):
        raise NotFoundError()
    existing = await repo.get_by_book(book_id)
    if existing is not None:
        raise _already_on_list(existing)
    times_read = apply_status_change(None, status, 0, None)
    try:
        async with db.begin_nested():
            return await repo.add(
                book_id=book_id,
                status=status,
                finished_on=finished_on,
                times_read=times_read,
                notes=notes,
                pre_ordered=pre_ordered,
                rating=rating,
            )
    except IntegrityError:
        # Added concurrently by another request from the same member.
        existing = await repo.get_by_book(book_id)
        if existing is None:  # pragma: no cover - any other integrity error is a bug
            raise
        raise _already_on_list(existing) from None


async def update_entry(
    db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID, changes: dict[str, Any], today: date
) -> ReadingEntry:
    repo = ReadingEntryRepository(db, user_id)
    entry = await repo.get(entry_id)
    if entry is None:
        raise NotFoundError()
    new_status: ReadingStatus = changes.get("status") or entry.status
    fields: dict[str, Any] = {
        k: v for k, v in changes.items() if k in {"finished_on", "notes", "pre_ordered", "rating"}
    }
    fields["status"] = new_status
    fields["times_read"] = apply_status_change(
        entry.status, new_status, entry.times_read, changes.get("times_read")
    )
    entering_finished = (
        new_status is ReadingStatus.FINISHED and entry.status is not ReadingStatus.FINISHED
    )
    if entering_finished and changes.get("finished_on") is None:
        fields["finished_on"] = today
    updated = await repo.update(entry_id, **fields)
    assert updated is not None  # noqa: S101 - read in this transaction
    return updated


async def read_again(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> ReadingEntry:
    """Start a re-read: status Reading, count unchanged (FR-029)."""
    updated = await ReadingEntryRepository(db, user_id).update(
        entry_id, status=ReadingStatus.READING
    )
    if updated is None:
        raise NotFoundError()
    return updated


async def remove_entry(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    """Remove from the member's list; the catalog book stays (FR-019)."""
    if not await ReadingEntryRepository(db, user_id).delete(entry_id):
        raise NotFoundError()
