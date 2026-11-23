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
from book_tracker.services import readings as readings_service
from book_tracker.services.errors import ConflictError, NotFoundError, ValidationFailed
from book_tracker.web.forms import AddBookForm, parse_story, story_form, story_start_form, text
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
    entry_id: uuid.UUID | None = None,
    added_label: str | None = None,
    back: tuple[str, str] | None = None,
    back_from: str = "",
    already: bool = False,
    another: bool = False,
) -> Response:
    return render(
        request,
        name,
        {
            "origin": f"entry:{entry_id}" if entry_id else "",
            "back_url": _back(book, entry_id) if book is not None else None,
            "added_label": added_label,
            "already": already,
            "another": another,
            "back": back,
            "back_from": back_from,
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


async def _origin(
    db: DbSession, auth: Authenticated, book: domain.Book, raw: str
) -> uuid.UUID | None:
    """``from=entry:<id>`` (spec 014 R1): my own entry for this book, or None. Only an id
    is taken from it, so it can never send the member elsewhere."""
    kind, _, value = raw.partition(":")
    if kind != "entry":
        return None
    try:
        entry = await readings_service.get_entry(db, auth.account.id, uuid.UUID(value))
    except (ValueError, NotFoundError):
        return None
    return entry.id if entry.book.id == book.id else None


def _back(book: domain.Book, entry_id: uuid.UUID | None) -> str:
    return f"/entries/{entry_id}" if entry_id else f"/catalog/books/{book.id}/edit#stories"


def _after_add(
    book: domain.Book, story_id: uuid.UUID, msg: str, entry_id: uuid.UUID | None, another: bool
) -> Response:
    """Spec 014 AC-03, AC-04: a fresh form, my entry page, or Edit book as before."""
    if another:
        already = "&already=1" if msg == "story_already" else ""
        origin = f"&from=entry:{entry_id}" if entry_id else ""
        url = f"/catalog/books/{book.id}/stories/add?added={story_id}{already}{origin}"
        return RedirectResponse(url, status_code=303)
    if entry_id is not None:
        return RedirectResponse(f"/entries/{entry_id}?msg={msg}", status_code=303)
    return _to_book(book.id, msg, story_id)


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
    entry_id = await _origin(db, auth, book, request.query_params.get("from", ""))
    added_label = None
    try:
        added = uuid.UUID(request.query_params.get("added", ""))
    except ValueError:
        added = None
    if added is not None:  # spec 014 AC-03: only a story in this book is named
        for story in await service.book_stories(db, book.id):
            if story.id == added:
                added_label = service.story_label(story)
    return _page(
        request, auth, "pages/add_story.html", story_start_form(book), book=book,
        entry_id=entry_id, added_label=added_label,
        already=request.query_params.get("already") == "1",
    )  # fmt: skip


@router.post("/books/{book_id}/stories/add")
async def add_story(book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession) -> Response:
    book = await service.get_book(db, book_id)
    data = await request.form()
    form, story_id, use_story = parse_story(data)
    entry_id = await _origin(db, auth, book, text(data, "from"))
    another = text(data, "then") == "another"

    def page(
        status_code: int,
        taken: domain.Story | None = None,
        author_conflicts: dict[int, ConflictError] | None = None,
        series_conflict: ConflictError | None = None,
    ) -> Response:
        return _page(
            request, auth, "pages/add_story.html", form, book=book, taken=taken,
            author_conflicts=author_conflicts, series_conflict=series_conflict,
            status_code=status_code, entry_id=entry_id, another=another,
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
        msg = "story_added" if added else "story_already"
        return _after_add(book, existing.id, msg, entry_id, another)

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
    return _after_add(book, story.id, "story_added", entry_id, another)


# --------------------------------------------------------------------------- edit


@router.get("/stories/{story_id}/edit")
async def edit_story_form(
    story_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    story = await service.get_story(db, story_id)
    came = _came_from(story, request.query_params.get("from", ""))
    return _page(
        request, auth, "pages/edit_story.html", story_form(story), story=story,
        back=_story_back(story, came), back_from=came,
    )  # fmt: skip


def _came_from(story: domain.Story, raw: str) -> str:
    """``book:<id>`` when it names one of the story's books, else "" (spec 014 AC-09)."""
    kind, _, value = raw.partition(":")
    found = kind == "book" and any(str(ref.id) == value for ref in story.books)
    return raw if found else ""


def _story_back(story: domain.Story, raw: str) -> tuple[str, str] | None:
    """Spec 014 AC-09: back to the book the member came from (``from=book:<id>``) if the
    story is in it, else its first book."""
    kind, _, value = raw.partition(":")
    came = next((ref for ref in story.books if kind == "book" and str(ref.id) == value), None)
    ref = came or (story.books[0] if story.books else None)
    return (ref.title, f"/catalog/books/{ref.id}/edit#stories") if ref else None


@router.post("/stories/{story_id}/edit")
async def edit_story(
    story_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    story = await service.get_story(db, story_id)
    data = await request.form()
    form, _, _ = parse_story(data)
    came = _came_from(story, text(data, "from"))

    def page(
        status_code: int,
        taken: domain.Story | None = None,
        author_conflicts: dict[int, ConflictError] | None = None,
        series_conflict: ConflictError | None = None,
    ) -> Response:
        return _page(
            request, auth, "pages/edit_story.html", form, story=story, taken=taken,
            author_conflicts=author_conflicts, series_conflict=series_conflict,
            status_code=status_code, back=_story_back(story, came), back_from=came,
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
    origin = f"&from={came}" if came else ""
    return RedirectResponse(f"/catalog/stories/{story_id}/edit?msg=saved{origin}", status_code=303)


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
