"""Stories in collections (spec 009): add a story to a book, edit a story, and take one
out of a book. Any member may (catalog data). Contract: specs/009-collection-stories/
contracts/ui-stories.md."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from book_tracker.auth.dependencies import Authenticated, UiUser
from book_tracker.domain import models as domain
from book_tracker.persistence.db import DbSession
from book_tracker.services import catalog as service
from book_tracker.services.errors import ConflictError, NotFoundError, ValidationFailed
from book_tracker.web.forms import AddBookForm, parse_story, story_form, story_start_form
from book_tracker.web.rendering import render
from book_tracker.web.routes.readings import (
    BOOK_FIELD_MESSAGES,
    chosen_series,
    new_name_prompts,
    resolve_authors,
    resolve_series,
)

router = APIRouter(prefix="/catalog", include_in_schema=False)


def _page(
    request: Request,
    auth: Authenticated,
    name: str,
    form: AddBookForm,
    *,
    book: domain.Book | None = None,
    story: domain.Story | None = None,
    taken: domain.Story | None = None,
    author_conflicts: dict[int, ConflictError] | None = None,
    series_conflict: ConflictError | None = None,
    status_code: int = 200,
) -> Response:
    return render(
        request,
        name,
        {
            "book": book,
            "story": story,
            "form": form,
            "taken": taken,
            "author_conflicts": author_conflicts or {},
            "series_conflict": series_conflict,
            "message": "Saved." if request.query_params.get("msg") == "saved" else None,
        },
        auth=auth,
        status_code=status_code,
    )


def _field_errors(form: AddBookForm, exc: ValidationFailed) -> None:
    """Service field names as the form knows them (author_ids → author_name_0)."""
    form.errors.update(
        {BOOK_FIELD_MESSAGES.get(e.field, (e.field,))[0]: e.message for e in exc.errors}
    )


def _to_book(book_id: uuid.UUID, msg: str, story_id: uuid.UUID | None = None) -> Response:
    query = f"msg={msg}" + (f"&story={story_id}" if story_id else "")
    return RedirectResponse(f"/catalog/books/{book_id}/edit?{query}#stories", status_code=303)


async def _picked(db: DbSession, story_id: uuid.UUID | None, title: str) -> domain.Story | None:
    """A story picked from the title suggestions, if its title still matches what was
    typed: without JavaScript, editing the text doesn't clear the id (research R5)."""
    if story_id is None:
        return None
    try:
        story = await service.get_story(db, story_id)
    except NotFoundError:
        return None
    return story if story.title.lower() == title.lower() else None


# --------------------------------------------------------------------------- add


@router.get("/books/{book_id}/stories/add")
async def add_story_form(
    book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    book = await service.get_book(db, book_id)
    return _page(request, auth, "pages/add_story.html", story_start_form(book), book=book)


@router.post("/books/{book_id}/stories/add")
async def add_story(book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession) -> Response:
    book = await service.get_book(db, book_id)
    form, story_id, use_story = parse_story(await request.form())

    def page(
        status_code: int,
        taken: domain.Story | None = None,
        author_conflicts: dict[int, ConflictError] | None = None,
        series_conflict: ConflictError | None = None,
    ) -> Response:
        return _page(
            request, auth, "pages/add_story.html", form, book=book, taken=taken,
            author_conflicts=author_conflicts, series_conflict=series_conflict,
            status_code=status_code,
        )  # fmt: skip

    existing: domain.Story | None = None
    if use_story is not None:  # "Add that story to this book"
        try:
            existing = await service.get_story(db, use_story)
        except NotFoundError:
            form.errors["title"] = service.STORY_DELETED
            return page(409)
    else:
        existing = await _picked(db, story_id, form.title)
    if existing is not None:
        try:
            _, added = await service.add_existing_story(db, auth.account.id, book.id, existing.id)
        except NotFoundError:
            form.errors["title"] = service.STORY_DELETED
            return page(409)
        return _to_book(book.id, "story_added" if added else "story_already", existing.id)

    await new_name_prompts(db, form)
    if form.field_errors:
        return page(422)
    if form.new_names:
        return page(409)
    series = await chosen_series(db, form)
    assert form.series_number is not None  # noqa: S101 - parse_story requires it
    if series is not None:
        taken = await service.story_at(db, series.id, form.series_number)
        if taken is not None:  # AC-05: offer it, before anything is created
            return page(409, taken=taken)
    author_ids, author_conflicts = await resolve_authors(db, auth, form)
    series_id, series_conflict = await resolve_series(db, auth, form)
    if author_conflicts or series_conflict:
        return page(409, author_conflicts=author_conflicts, series_conflict=series_conflict)
    assert series_id is not None  # noqa: S101 - a series name is required
    new = service.NewStory(form.title, author_ids, series_id, form.series_number)
    try:
        story = await service.add_new_story(db, auth.account.id, book.id, new)
    except ConflictError as exc:  # another member took the number a moment ago
        taken = await service.story_at(db, series_id, form.series_number)
        if taken is None or exc.code != "story_number_taken":  # pragma: no cover - defensive
            raise
        return page(409, taken=taken)
    except ValidationFailed as exc:
        _field_errors(form, exc)
        return page(422)
    return _to_book(book.id, "story_added", story.id)


# --------------------------------------------------------------------------- edit


@router.get("/stories/{story_id}/edit")
async def edit_story_form(
    story_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    story = await service.get_story(db, story_id)
    return _page(request, auth, "pages/edit_story.html", story_form(story), story=story)


@router.post("/stories/{story_id}/edit")
async def edit_story(
    story_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    story = await service.get_story(db, story_id)
    form, _, _ = parse_story(await request.form())

    def page(
        status_code: int,
        taken: domain.Story | None = None,
        author_conflicts: dict[int, ConflictError] | None = None,
        series_conflict: ConflictError | None = None,
    ) -> Response:
        return _page(
            request, auth, "pages/edit_story.html", form, story=story, taken=taken,
            author_conflicts=author_conflicts, series_conflict=series_conflict,
            status_code=status_code,
        )  # fmt: skip

    await new_name_prompts(db, form)
    if form.field_errors:
        return page(422)
    if form.new_names:
        return page(409)
    author_ids, author_conflicts = await resolve_authors(db, auth, form)
    series_id, series_conflict = await resolve_series(db, auth, form)
    if author_conflicts or series_conflict:
        return page(409, author_conflicts=author_conflicts, series_conflict=series_conflict)
    changes = {
        "title": form.title,
        "author_ids": author_ids,
        "series_id": series_id,
        "series_number": form.series_number,
    }
    try:
        await service.update_story(db, auth.account.id, story_id, changes)
    except ConflictError as exc:
        taken = await service.get_story(db, exc.existing_id) if exc.existing_id else None
        return page(409, taken=taken)
    except ValidationFailed as exc:
        _field_errors(form, exc)
        return page(422)
    return RedirectResponse(f"/catalog/stories/{story_id}/edit?msg=saved", status_code=303)


# --------------------------------------------------------------------------- remove


@router.post("/books/{book_id}/stories/{story_id}/remove")
async def remove_story(
    book_id: uuid.UUID, story_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    """Without ``confirm=yes``, ask first, saying whether the story will be deleted."""
    book = await service.get_book(db, book_id)
    story = await service.get_story(db, story_id)
    if book.id not in {ref.id for ref in story.books}:
        raise NotFoundError()
    form = await request.form()
    if form.get("confirm") != "yes":
        elsewhere = [ref for ref in story.books if ref.id != book.id]
        return render(
            request,
            "pages/confirm_remove_story.html",
            {"book": book, "story": story, "elsewhere": elsewhere},
            auth=auth,
        )
    deleted = await service.remove_story(db, auth.account.id, book.id, story.id)
    return _to_book(book.id, "story_deleted" if deleted else "story_removed")
