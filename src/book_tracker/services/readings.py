"""A member's own reading list (FR-016 – FR-020, FR-029).

Every operation goes through a ``ReadingEntryRepository`` bound to the session user.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.models import ReadingEntry, ReadingEntryPage, Series
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
) -> ReadingEntryPage:
    """My list, sorted, filtered and searched (FR-021, FR-023)."""
    return await ReadingEntryRepository(db, user_id).list(
        page=page,
        page_size=page_size,
        q=q.strip() if q and q.strip() else None,
        author_id=author_id,
        series_id=series_id,
        status=status,
        sort=sort if sort in SORTS else "title",
    )


async def series_view(
    db: AsyncSession, user_id: uuid.UUID, series_id: uuid.UUID
) -> tuple[Series, tuple[ReadingEntry, ...]]:
    """My books in one series, in reading order (FR-022). Unknown series → not found."""
    series = await catalog_service.get_series(db, series_id)
    return series, await ReadingEntryRepository(db, user_id).list_series(series_id)


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
    fields: dict[str, Any] = {k: v for k, v in changes.items() if k in {"finished_on", "notes"}}
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
