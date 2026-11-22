"""Stories in collections (spec 009): a story has a place in a series and is contained in
one or more catalog books. Any member may add, edit or remove (catalog data)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUser
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import Story, StoryAdd, StoryUpdate
from book_tracker.schemas.mappers import story_out
from book_tracker.services import catalog as service

router = APIRouter(tags=["catalog"])


@router.get(
    "/books/{book_id}/stories",
    response_model=list[Story],
    summary="The stories a book contains, by series name then number (spec 009)",
    responses=r.READ_ONE,
)
async def book_stories(book_id: uuid.UUID, auth: ApiUser, db: DbSession) -> list[Story]:
    await service.get_book(db, book_id)  # 404 if unknown
    return [story_out(s) for s in await service.book_stories(db, book_id)]


@router.post(
    "/books/{book_id}/stories",
    response_model=Story,
    status_code=201,
    summary="Add a new or existing story to a book; any member (spec 009)",
    responses=r.merge(
        {200: {"model": Story, "description": "The book already had this story; no change"}},
        r.WRITE,
        r.NOT_FOUND,
        r.CATALOG_CONFLICT,
    ),
)
async def add_story(
    book_id: uuid.UUID, body: StoryAdd, auth: ApiUser, db: DbSession
) -> Story | JSONResponse:
    if body.story_id is not None:
        story, added = await service.add_existing_story(db, auth.account.id, book_id, body.story_id)
        if not added:
            return JSONResponse(story_out(story).model_dump(mode="json"), status_code=200)
        return story_out(story)
    # StoryAdd guarantees all four fields of a new story when story_id isn't given.
    assert body.title and body.author_ids and body.series_id and body.series_number is not None  # noqa: S101
    new = service.NewStory(body.title, body.author_ids, body.series_id, body.series_number)
    return story_out(await service.add_new_story(db, auth.account.id, book_id, new))


@router.delete(
    "/books/{book_id}/stories/{story_id}",
    status_code=204,
    summary="Take a story out of a book; it is deleted when no other book has it (spec 009)",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND, r.VALIDATION),
)
async def remove_story(
    book_id: uuid.UUID, story_id: uuid.UUID, auth: ApiUser, db: DbSession
) -> Response:
    await service.remove_story(db, auth.account.id, book_id, story_id)
    return Response(status_code=204)


@router.get(
    "/stories",
    response_model=list[Story],
    summary="The stories in a series, by number (spec 009)",
    responses=r.READ_ONE,
)
async def series_stories(series_id: uuid.UUID, auth: ApiUser, db: DbSession) -> list[Story]:
    await service.get_series(db, series_id)  # 404 if unknown
    return [story_out(s) for s in await service.series_stories(db, series_id)]


@router.get(
    "/stories/{story_id}",
    response_model=Story,
    summary="A story, with the books that contain it (spec 009)",
    responses=r.READ_ONE,
)
async def get_story(story_id: uuid.UUID, auth: ApiUser, db: DbSession) -> Story:
    return story_out(await service.get_story(db, story_id))


@router.patch(
    "/stories/{story_id}",
    response_model=Story,
    summary="Edit a story; any member (spec 009)",
    responses=r.merge(r.WRITE, r.NOT_FOUND, r.CATALOG_CONFLICT),
)
async def update_story(
    story_id: uuid.UUID, body: StoryUpdate, auth: ApiUser, db: DbSession
) -> Story:
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    return story_out(await service.update_story(db, auth.account.id, story_id, changes))
