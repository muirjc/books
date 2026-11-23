"""The member's own reading list: ``/me/readings`` (FR-016 – FR-020, FR-029)."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser, now, today
from book_tracker.domain.enums import ReadingStatus
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.mappers import (
    my_series_view_out,
    reading_entry_out,
    reading_entry_page_out,
)
from book_tracker.schemas.readings import (
    MySeriesView,
    ReadingEntry,
    ReadingEntryCreate,
    ReadingEntryPage,
    ReadingEntryUpdate,
)
from book_tracker.schemas.types import drop_nul
from book_tracker.services import readings as service
from book_tracker.services.catalog import NewBook

router = APIRouter(prefix="/me", tags=["me"])

Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


Sort = Literal[
    "title", "-title", "author", "-author", "series", "-series", "finished_on", "-finished_on"
]


@router.get(
    "/readings",
    response_model=ReadingEntryPage,
    summary="My reading list (FR-021, FR-023)",
    responses=r.merge(r.READ, r.VALIDATION),
)
async def list_readings(
    request: Request,
    auth: ApiUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200)] = None,
    author_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
    status: ReadingStatus | None = None,
    sort: Sort = "title",
    page: Page = 1,
    page_size: PageSize = 50,
    upcoming: Annotated[
        bool,
        Query(description="Only books not out yet, soonest first; sort is ignored (spec 007)"),
    ] = False,
    favorite_authors: Annotated[
        bool, Query(description="Only books by one of my favorite authors (spec 011)")
    ] = False,
) -> ReadingEntryPage:
    result = await service.list_entries(
        db,
        auth.account.id,
        page=page,
        page_size=page_size,
        q=drop_nul(q),  # books-7bq
        author_id=author_id,
        series_id=series_id,
        status=status,
        sort=sort,
        upcoming_after=today(request) if upcoming else None,
        favorite_authors=favorite_authors,
    )
    return reading_entry_page_out(result)


@router.get(
    "/series/{series_id}",
    response_model=MySeriesView,
    summary="My books in one series, in series order; unnumbered last (FR-022, AC-22)",
    responses=r.READ_ONE,
)
async def my_series(series_id: uuid.UUID, auth: ApiUser, db: DbSession) -> MySeriesView:
    series, entries = await service.series_view(db, auth.account.id, series_id)
    return my_series_view_out(series, entries)


@router.post(
    "/readings",
    response_model=ReadingEntry,
    status_code=201,
    summary="Add a book to my list (FR-016, FR-017)",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND, r.CONFLICT, r.VALIDATION),
)
async def add_reading(
    body: ReadingEntryCreate, request: Request, auth: ApiUser, db: DbSession
) -> ReadingEntry:
    new_book = None
    if body.new_book is not None:
        nb = body.new_book
        new_book = NewBook(
            title=nb.title,
            author_ids=nb.author_ids,
            series_id=nb.series_id,
            series_number=nb.series_number,
            isbn_13=nb.isbn_13,
            summary=nb.summary,
            release_date=nb.release_date,
        )
    entry = await service.add_entry(
        db,
        auth.account.id,
        now=now(request),
        book_id=body.book_id,
        new_book=new_book,
        status=body.status,
        finished_on=body.finished_on,
        notes=body.notes,
        pre_ordered=body.pre_ordered,
    )
    return reading_entry_out(entry)


@router.get(
    "/readings/{entry_id}",
    response_model=ReadingEntry,
    summary="One of my entries; another member's entry returns 404",
    responses=r.READ_ONE,
)
async def get_reading(entry_id: uuid.UUID, auth: ApiUser, db: DbSession) -> ReadingEntry:
    return reading_entry_out(await service.get_entry(db, auth.account.id, entry_id))


@router.patch(
    "/readings/{entry_id}",
    response_model=ReadingEntry,
    summary="Update status, date finished, times read, notes or Pre-ordered",
    responses=r.merge(r.WRITE, r.NOT_FOUND),
)
async def update_reading(
    entry_id: uuid.UUID, body: ReadingEntryUpdate, request: Request, auth: ApiUser, db: DbSession
) -> ReadingEntry:
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    entry = await service.update_entry(db, auth.account.id, entry_id, changes, today=today(request))
    return reading_entry_out(entry)


@router.delete(
    "/readings/{entry_id}",
    status_code=204,
    summary="Remove from my list; the catalog book stays",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND),
)
async def delete_reading(entry_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Response:
    await service.remove_entry(db, auth.account.id, entry_id)
    return Response(status_code=204)


@router.post(
    "/readings/{entry_id}/read-again",
    response_model=ReadingEntry,
    summary="Start a re-read; status reading, times_read unchanged",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND),
)
async def read_again(entry_id: uuid.UUID, auth: ApiUser, db: DbSession) -> ReadingEntry:
    return reading_entry_out(await service.read_again(db, auth.account.id, entry_id))
