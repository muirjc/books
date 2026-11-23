"""Catalog books (FR-009, FR-012)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser, now, today
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import (
    Book,
    BookUpdate,
    Summary,
    SummaryCreate,
    SummaryDraft,
    SummaryDraftRequest,
)
from book_tracker.schemas.mappers import book_out, summary_draft_out, summary_out
from book_tracker.schemas.types import TypeAheadText
from book_tracker.services import catalog as service
from book_tracker.services import drafts, summaries
from book_tracker.sources.dependencies import BookSourceDep
from book_tracker.sources.summary_generator import SummaryGeneratorDep

TypeAheadQuery = Annotated[str, TypeAheadText, Query(min_length=1, max_length=200)]
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
    summary="Type-ahead search of catalog books by title, author, real name, story title or ISBN",
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
    book_id: uuid.UUID, body: SummaryCreate, request: Request, auth: ApiUser, db: DbSession
) -> Summary:
    draft_id = str(body.draft_id) if body.draft_id else None
    return summary_out(
        await summaries.save_summary(
            db, auth.account.id, book_id, body.text, draft_id=draft_id, now=now(request)
        )
    )


@router.post(
    "/{book_id}/summary-drafts",
    response_model=SummaryDraft,
    summary="An AI draft of the book's summary; nothing is saved (spec 012)",
    responses=r.merge(r.WRITE, r.NOT_FOUND, r.DRAFT_FAILED, r.DRAFT_LIMIT, r.AI_UNAVAILABLE),
)
async def request_summary_draft(
    book_id: uuid.UUID,
    body: SummaryDraftRequest,
    request: Request,
    auth: ApiUser,
    db: DbSession,
    source: BookSourceDep,
    generator: SummaryGeneratorDep,
) -> SummaryDraft:
    book = await service.get_book(db, book_id)
    view = await drafts.request_draft(
        db,
        user_id=auth.account.id,
        facts=drafts.facts_for(book),
        regenerate=body.regenerate,
        source=source,
        generator=generator,
        now=now(request),
        today=today(request),
        limit=request.app.state.settings.ai_daily_draft_limit,
    )
    return summary_draft_out(view)
