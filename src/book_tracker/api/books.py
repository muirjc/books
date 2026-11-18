"""Catalog books (FR-009, FR-012)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import Book, BookUpdate, Summary, SummaryCreate
from book_tracker.schemas.mappers import book_out, summary_out
from book_tracker.services import catalog as service
from book_tracker.services import summaries

TypeAheadQuery = Annotated[str, Query(min_length=1, max_length=200)]
TypeAheadLimit = Annotated[int, Query(ge=1, le=25)]

router = APIRouter(prefix="/books", tags=["catalog"])


@router.get(
    "/{book_id}",
    response_model=Book,
    summary="A catalog book, with its current summary",
    responses=r.READ_ONE,
)
async def get_book(book_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Book:
    return book_out(await service.get_book(db, book_id))


@router.get(
    "",
    response_model=list[Book],
    summary="Type-ahead search of catalog books by title, author name, real name or exact ISBN",
    responses=r.READ,
)
async def search_books(
    auth: ApiUser, db: DbSession, q: TypeAheadQuery, limit: TypeAheadLimit = 10
) -> list[Book]:
    return [book_out(b) for b in await service.search_books(db, q, limit)]


@router.patch(
    "/{book_id}",
    response_model=Book,
    summary="Edit a catalog book; any member (FR-009, AC-32)",
    responses=r.merge(r.WRITE, r.NOT_FOUND, r.CATALOG_CONFLICT),
)
async def update_book(book_id: uuid.UUID, body: BookUpdate, auth: ApiUser, db: DbSession) -> Book:
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    return book_out(await service.update_book(db, auth.account.id, book_id, changes))


@router.get(
    "/{book_id}/summaries",
    response_model=list[Summary],
    summary="Summary history, newest first (FR-024)",
    responses=r.READ_ONE,
)
async def list_summaries(book_id: uuid.UUID, auth: ApiUser, db: DbSession) -> list[Summary]:
    return [summary_out(s) for s in await summaries.history(db, book_id)]


@router.post(
    "/{book_id}/summaries",
    response_model=Summary,
    status_code=201,
    summary="Save a hand-written summary as the current one (FR-024, FR-025)",
    responses=r.merge(r.WRITE, r.NOT_FOUND),
)
async def save_summary(
    book_id: uuid.UUID, body: SummaryCreate, auth: ApiUser, db: DbSession
) -> Summary:
    return summary_out(await summaries.save_manual_summary(db, auth.account.id, book_id, body.text))
