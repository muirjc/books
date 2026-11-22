"""A member's own reading list (FR-016 – FR-020, FR-029).

Every operation goes through a ``ReadingEntryRepository`` bound to the session user.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.models import Book, ReadingEntry, ReadingEntryPage, Series
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
) -> ReadingEntryPage:
    """My list, sorted, filtered and searched (FR-021, FR-023). With ``upcoming_after``
    (today), only books not out yet, soonest first (spec 007)."""
    return await ReadingEntryRepository(db, user_id).list(
        page=page,
        page_size=page_size,
        q=q.strip() if q and q.strip() else None,
        author_id=author_id,
        series_id=series_id,
        status=status,
        sort=sort if sort in SORTS else "title",
        upcoming_after=upcoming_after,
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


async def now_out(db: AsyncSession, user_id: uuid.UUID, today: date) -> tuple[ReadingEntry, ...]:
    """My Want to read books released in the last 30 days (spec 007 R6)."""
    return await ReadingEntryRepository(db, user_id).list_now_out(today)


GAP_RUN_ROWS = 3  # a run of missing numbers longer than this is one row (spec 006)


@dataclass(frozen=True, slots=True)
class SeriesRow:
    """A series page row: a catalog book with my entry (or none), or a gap in the
    numbering from ``first`` to ``last``."""

    book: Book | None = None
    entry: ReadingEntry | None = None
    first: int = 0
    last: int = 0


@dataclass(frozen=True, slots=True)
class SeriesView:
    rows: tuple[SeriesRow, ...]
    finished: int  # my Finished entries among the listed books
    total: int  # catalog books listed; gaps don't count


def _gap_runs(numbers: set[Decimal], top: int) -> list[tuple[int, int]]:
    """Runs of whole numbers 1..top that no book has exactly; long runs as one. A book
    numbered between two missing numbers (say 3.5) ends a run, so it keeps its place."""
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


def series_rows(books: Sequence[Book], entries: Sequence[ReadingEntry]) -> SeriesView:
    """Merge a series' catalog books (in catalog order: by number, then unnumbered) with
    my entries, adding gap rows for missing whole numbers (spec 006, research R2)."""
    mine = {entry.book.id: entry for entry in entries}
    numbers = {book.series_number for book in books if book.series_number is not None}
    top = math.floor(max(numbers)) if numbers else 0
    gaps = _gap_runs(numbers, top)
    rows: list[SeriesRow] = []
    for book in books:
        while gaps and book.series_number is not None and book.series_number > gaps[0][1]:
            rows.append(SeriesRow(first=gaps[0][0], last=gaps[0][1]))
            gaps.pop(0)
        rows.append(SeriesRow(book=book, entry=mine.get(book.id)))
    finished = sum(
        1 for row in rows if row.entry is not None and row.entry.status is ReadingStatus.FINISHED
    )
    return SeriesView(rows=tuple(rows), finished=finished, total=len(books))


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
    """Every catalog book in a series with my own entries, and gaps (spec 006, the series
    page). Only my entries are read (Principle I). Unknown series → not found."""
    series, entries = await series_view(db, user_id, series_id)
    books = await catalog_service.series_books(db, series_id)
    return series, series_rows(books, entries)


async def filter_options(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[FilterOptions, FilterOptions]:
    return await ReadingEntryRepository(db, user_id).filter_options()


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
) -> ReadingEntry:
    repo = ReadingEntryRepository(db, user_id)
    if new_book is not None:
        try:
            book = await catalog_service.create_book(db, user_id, new_book)
        except ValidationFailed as exc:
            raise ValidationFailed(
                [FieldError(f"new_book.{e.field}", e.message) for e in exc.errors]
            ) from None
        book_id = book.id
        if new_book.summary:
            await summaries.save_manual_summary(db, user_id, book_id, new_book.summary)
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
        k: v for k, v in changes.items() if k in {"finished_on", "notes", "pre_ordered"}
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
