"""Import an author's books (spec 002 contracts/openapi.yaml).

Every operation takes the member from the session (Principle I); none accepts a user id.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser, now
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.imports import (
    AuthorCandidateList,
    AuthorKey,
    ImportRequest,
    ImportResult,
    SearchText,
    WorkList,
    WorksSort,
)
from book_tracker.schemas.mappers import (
    author_candidate_out,
    import_result_out,
    works_view_out,
)
from book_tracker.services import imports as service
from book_tracker.sources.dependencies import BookSourceDep

router = APIRouter(tags=["import"])


@router.get(
    "/import/authors",
    response_model=AuthorCandidateList,
    summary="Search Open Library for authors by name (FR-001, FR-002)",
    responses=r.merge(r.READ, r.VALIDATION, r.SOURCE_UNAVAILABLE),
)
async def search_authors(
    q: Annotated[SearchText, Query()],
    request: Request,
    auth: ApiUser,
    db: DbSession,
    source: BookSourceDep,
) -> AuthorCandidateList:
    authors = await service.search_authors(db, source, q, now(request))
    return AuthorCandidateList(authors=[author_candidate_out(a) for a in authors])


@router.get(
    "/import/authors/{author_key}/works",
    response_model=WorkList,
    summary="An author's works with their catalog and list state (FR-003 to FR-006)",
    responses=r.merge(r.READ, r.AUTHOR_NOT_FOUND, r.VALIDATION, r.SOURCE_UNAVAILABLE),
)
async def author_works(
    author_key: Annotated[AuthorKey, Path()],
    request: Request,
    auth: ApiUser,
    db: DbSession,
    source: BookSourceDep,
    sort: WorksSort = "title",
    q: Annotated[SearchText | None, Query()] = None,
) -> WorkList:
    view = await service.list_works(
        db, source, auth.account.id, author_key, now(request), sort=sort, q=q
    )
    return works_view_out(view)


@router.post(
    "/me/imports",
    response_model=ImportResult,
    status_code=201,
    tags=["me"],
    summary="Add selected works to my list, creating catalog books as needed (FR-007 to FR-014)",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.RESULTS_EXPIRED, r.VALIDATION),
)
async def import_works(
    body: ImportRequest, request: Request, auth: ApiUser, db: DbSession
) -> ImportResult:
    result = await service.confirm_import(
        db,
        auth.account.id,
        author_key=body.author_key,
        work_keys=body.work_keys,
        status=body.status,
        now=now(request),
    )
    return import_result_out(result)
