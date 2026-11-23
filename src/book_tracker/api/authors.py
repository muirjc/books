"""Catalog authors (FR-009 – FR-011, FR-014)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import Author, AuthorCreate, AuthorUpdate
from book_tracker.schemas.mappers import author_out
from book_tracker.schemas.types import NoNul
from book_tracker.services import catalog as service

TypeAheadQuery = Annotated[str, NoNul, Query(min_length=1, max_length=200)]
TypeAheadLimit = Annotated[int, Query(ge=1, le=25)]

router = APIRouter(prefix="/authors", tags=["catalog"])


@router.post(
    "",
    response_model=Author,
    status_code=201,
    summary="Create an author",
    responses=r.merge(r.WRITE, r.CATALOG_CONFLICT),
)
async def create_author(body: AuthorCreate, auth: ApiUser, db: DbSession) -> Author:
    author = await service.create_author(
        db,
        auth.account.id,
        name=body.name,
        sort_name=body.sort_name,
        is_pen_name=body.is_pen_name,
        real_name=body.real_name,
    )
    return author_out(author)


@router.get("/{author_id}", response_model=Author, summary="An author", responses=r.READ_ONE)
async def get_author(author_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Author:
    return author_out(await service.get_author(db, author_id))


@router.get(
    "",
    response_model=list[Author],
    summary="Type-ahead search by name or real name",
    responses=r.READ,
)
async def search_authors(
    auth: ApiUser, db: DbSession, q: TypeAheadQuery, limit: TypeAheadLimit = 10
) -> list[Author]:
    return [author_out(a) for a in await service.search_authors(db, q, limit)]


@router.patch(
    "/{author_id}",
    response_model=Author,
    summary="Edit an author, including pen name and real name",
    responses=r.merge(r.WRITE, r.NOT_FOUND, r.CATALOG_CONFLICT),
)
async def update_author(
    author_id: uuid.UUID, body: AuthorUpdate, auth: ApiUser, db: DbSession
) -> Author:
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    return author_out(await service.update_author(db, auth.account.id, author_id, changes))


@router.delete(
    "/{author_id}",
    status_code=204,
    summary="Delete an author no book lists; any member (spec 008)",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND, r.PLAIN_CONFLICT),
)
async def delete_author(author_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Response:
    await service.delete_author(db, auth.account.id, author_id)
    return Response(status_code=204)
