"""Catalog series (FR-009 – FR-011)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import Series, SeriesWrite
from book_tracker.schemas.mappers import series_out
from book_tracker.schemas.types import NoNul
from book_tracker.services import catalog as service

TypeAheadQuery = Annotated[str, NoNul, Query(min_length=1, max_length=200)]
TypeAheadLimit = Annotated[int, Query(ge=1, le=25)]

router = APIRouter(prefix="/series", tags=["catalog"])


@router.post(
    "",
    response_model=Series,
    status_code=201,
    summary="Create a series",
    responses=r.merge(r.WRITE, r.CATALOG_CONFLICT),
)
async def create_series(body: SeriesWrite, auth: ApiUser, db: DbSession) -> Series:
    return series_out(await service.create_series(db, auth.account.id, name=body.name))


@router.get("/{series_id}", response_model=Series, summary="A series", responses=r.READ_ONE)
async def get_series(series_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Series:
    return series_out(await service.get_series(db, series_id))


@router.get("", response_model=list[Series], summary="Type-ahead search", responses=r.READ)
async def search_series(
    auth: ApiUser, db: DbSession, q: TypeAheadQuery, limit: TypeAheadLimit = 10
) -> list[Series]:
    return [series_out(s) for s in await service.search_series(db, q, limit)]


@router.patch(
    "/{series_id}",
    response_model=Series,
    summary="Rename a series",
    responses=r.merge(r.WRITE, r.NOT_FOUND, r.CATALOG_CONFLICT),
)
async def update_series(
    series_id: uuid.UUID, body: SeriesWrite, auth: ApiUser, db: DbSession
) -> Series:
    return series_out(await service.update_series(db, auth.account.id, series_id, name=body.name))
