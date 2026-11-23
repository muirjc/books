"""My favorite authors (spec 011): personal, the caller's only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import Author
from book_tracker.schemas.mappers import author_out
from book_tracker.services import authors as service

router = APIRouter(prefix="/me/favorite-authors", tags=["me"])


@router.get(
    "",
    response_model=list[Author],
    summary="My favorite authors, by sort name (spec 011)",
    responses=r.READ,
)
async def list_favorites(auth: ApiUser, db: DbSession) -> list[Author]:
    return [author_out(a) for a in await service.favorite_authors(db, auth.account.id)]


@router.put(
    "/{author_id}",
    status_code=204,
    summary="Add an author to my favorites; already one is fine (spec 011)",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND),
)
async def add_favorite(author_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Response:
    await service.add_favorite(db, auth.account.id, author_id)
    return Response(status_code=204)


@router.delete(
    "/{author_id}",
    status_code=204,
    summary="Remove an author from my favorites; not one is fine (spec 011)",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND),
)
async def remove_favorite(author_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Response:
    await service.remove_favorite(db, auth.account.id, author_id)
    return Response(status_code=204)
