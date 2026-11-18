"""My list, add a book, and entry pages (FR-016 – FR-020, FR-029)."""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from book_tracker.auth.dependencies import Authenticated, UiUser, now
from book_tracker.domain.enums import ReadingStatus
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import BookCreate
from book_tracker.schemas.readings import ReadingEntryCreate
from book_tracker.services import catalog as catalog_service
from book_tracker.services import readings as service
from book_tracker.services.catalog import NewBook
from book_tracker.services.errors import ConflictError, NotFoundError, ValidationFailed
from book_tracker.web.forms import AddBookForm, parse_add_book, parse_entry_update
from book_tracker.web.rendering import is_htmx, render

router = APIRouter(include_in_schema=False)

PAGE_SIZE = 50
MESSAGES = {
    "added": "Added to your list.",
    "removed": "Removed from your list.",
    "saved": "Saved.",
    "reread": "Started a re-read.",
    "password": "Your password has been changed.",
}
STATUSES = [
    (s.value, label)
    for s, label in (
        (ReadingStatus.FINISHED, "Finished"),
        (ReadingStatus.READING, "Reading"),
        (ReadingStatus.WANT_TO_READ, "Want to read"),
    )
]


def message(request: Request) -> str | None:
    return MESSAGES.get(request.query_params.get("msg", ""))


def page_number(request: Request) -> int:
    raw = request.query_params.get("page", "1")
    return int(raw) if raw.isdigit() and int(raw) >= 1 else 1


# --------------------------------------------------------------------------- list


SORT_OPTIONS = [
    ("title", "Title (A–Z)"),
    ("-title", "Title (Z–A)"),
    ("author", "Author"),
    ("series", "Series"),
    ("-finished_on", "Recently finished"),
    ("finished_on", "Finished longest ago"),
]


def _uuid_param(request: Request, name: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(request.query_params.get(name, ""))
    except ValueError:
        return None


@router.get("/")
async def my_list(request: Request, auth: UiUser, db: DbSession) -> Response:
    """My list with search, sort and filters; HTMX gets just the list (FR-021, FR-023)."""
    params = request.query_params
    q = params.get("q", "").strip()[:200]
    sort = params.get("sort", "title")
    sort = sort if sort in {value for value, _ in SORT_OPTIONS} else "title"
    status_text = params.get("status", "")
    status = ReadingStatus(status_text) if status_text in ReadingStatus._value2member_map_ else None
    author_id = _uuid_param(request, "author_id")
    series_id = _uuid_param(request, "series_id")
    page = await service.list_entries(
        db,
        auth.account.id,
        page=page_number(request),
        page_size=PAGE_SIZE,
        q=q,
        author_id=author_id,
        series_id=series_id,
        status=status,
        sort=sort,
    )
    kept = {
        "q": q,
        "sort": "" if sort == "title" else sort,
        "status": status.value if status else "",
        "author_id": str(author_id) if author_id else "",
        "series_id": str(series_id) if series_id else "",
    }
    query = urlencode({k: v for k, v in kept.items() if v})
    context: dict[str, Any] = {
        "page": page,
        "message": message(request),
        "active": "list",
        "filters": kept,
        "sort": sort,
        "query_without_page": f"{query}&" if query else "",
        "filtered": any(v for k, v in kept.items() if k != "sort"),
    }
    if is_htmx(request):
        return render(request, "partials/reading_list.html", context, auth=auth)
    authors, series = await service.filter_options(db, auth.account.id)
    context.update(
        {
            "sort_options": SORT_OPTIONS,
            "statuses": STATUSES,
            "author_options": authors,
            "series_options": series,
        }
    )
    return render(request, "pages/list.html", context, auth=auth)


@router.get("/series/{series_id}")
async def series_page(
    series_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    """My books in one series, in reading order (FR-022)."""
    series, entries = await service.series_view(db, auth.account.id, series_id)
    return render(request, "pages/series.html", {"series": series, "entries": entries}, auth=auth)


# --------------------------------------------------------------------------- add


def _add_form(
    request: Request,
    auth: Authenticated,
    form: AddBookForm | None = None,
    *,
    status_code: int = 200,
    conflict: ConflictError | None = None,
    author_conflicts: dict[int, ConflictError] | None = None,
    series_conflict: ConflictError | None = None,
) -> Response:
    return render(
        request,
        "pages/add_book.html",
        {
            "form": form or AddBookForm(),
            "statuses": STATUSES,
            "conflict": conflict,
            "author_conflicts": author_conflicts or {},
            "series_conflict": series_conflict,
            "active": "add",
        },
        auth=auth,
        status_code=status_code,
    )


@router.get("/books/add")
async def add_book_form(request: Request, auth: UiUser) -> Response:
    return _add_form(request, auth)


@router.post("/books/add")
async def add_book(request: Request, auth: UiUser, db: DbSession) -> Response:
    form = parse_add_book(await request.form())
    if form.errors:
        return _add_form(request, auth, form, status_code=422)
    user_id = auth.account.id
    try:
        if form.book_id is not None:
            payload = ReadingEntryCreate(
                book_id=form.book_id,
                status=form.status,
                finished_on=form.finished_on,
                notes=form.notes,
            )
            await service.add_entry(
                db,
                user_id,
                book_id=payload.book_id,
                status=payload.status,
                finished_on=payload.finished_on,
                notes=payload.notes,
            )
        else:
            author_ids, author_conflicts = await resolve_authors(db, auth, form)
            series_id, series_conflict = await resolve_series(db, auth, form)
            if author_conflicts or series_conflict:
                await db.rollback()
                return _add_form(
                    request,
                    auth,
                    form,
                    status_code=409,
                    author_conflicts=author_conflicts,
                    series_conflict=series_conflict,
                )
            book = BookCreate(
                title=form.title,
                author_ids=author_ids,
                series_id=series_id,
                series_number=form.series_number,
                isbn_13=form.isbn_13,
            )
            await service.add_entry(
                db,
                user_id,
                new_book=NewBook(
                    title=book.title,
                    author_ids=book.author_ids,
                    series_id=book.series_id,
                    series_number=book.series_number,
                    isbn_13=book.isbn_13,
                    summary=form.summary,
                ),
                status=form.status,
                finished_on=form.finished_on,
                notes=form.notes,
            )
    except ConflictError as exc:
        await db.rollback()
        return _add_form(request, auth, form, status_code=409, conflict=exc)
    except (ValidationFailed, NotFoundError):
        await db.rollback()
        form.errors["title"] = "That book is no longer in the catalog. Enter its details."
        return _add_form(request, auth, form, status_code=422)
    return RedirectResponse("/?msg=added", status_code=303)


async def resolve_authors(
    db: DbSession, auth: Authenticated, form: AddBookForm
) -> tuple[list[uuid.UUID], dict[int, ConflictError]]:
    """Use chosen authors; create typed new ones. Conflicts are reported per row.

    A chosen id only counts if its name still matches what was typed (without JavaScript,
    editing the text doesn't clear the hidden id).
    """
    ids: list[uuid.UUID] = []
    conflicts: dict[int, ConflictError] = {}
    for row in form.chosen_authors:
        if row.author_id is not None:
            try:
                chosen = await catalog_service.get_author(db, row.author_id)
            except NotFoundError:
                chosen = None
            if chosen is not None and (not row.name or chosen.name.lower() == row.name.lower()):
                ids.append(chosen.id)
                continue
        if not row.name:
            continue
        try:
            author = await catalog_service.create_author(db, auth.account.id, name=row.name)
        except ConflictError as exc:
            conflicts[row.index] = exc
            continue
        ids.append(author.id)
    return list(dict.fromkeys(ids)), conflicts


async def resolve_series(
    db: DbSession, auth: Authenticated, form: AddBookForm
) -> tuple[uuid.UUID | None, ConflictError | None]:
    if form.series_id is not None:
        try:
            chosen = await catalog_service.get_series(db, form.series_id)
        except NotFoundError:
            chosen = None
        if chosen is not None and (
            not form.series_name or chosen.name.lower() == form.series_name.lower()
        ):
            return chosen.id, None
    if not form.series_name:
        return None, None
    try:
        series = await catalog_service.create_series(db, auth.account.id, name=form.series_name)
    except ConflictError as exc:
        return None, exc
    return series.id, None


# --------------------------------------------------------------------------- entry


def _entry_page(
    request: Request,
    auth: Authenticated,
    entry: Any,
    *,
    errors: dict[str, str] | None = None,
    raw: dict[str, Any] | None = None,
    status_code: int = 200,
) -> Response:
    return render(
        request,
        "pages/entry.html",
        {
            "entry": entry,
            "statuses": STATUSES,
            "errors": errors or {},
            "raw": raw or {},
            "message": message(request),
        },
        auth=auth,
        status_code=status_code,
    )


@router.get("/entries/{entry_id}")
async def entry_page(
    entry_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    entry = await service.get_entry(db, auth.account.id, entry_id)
    return _entry_page(request, auth, entry)


@router.post("/entries/{entry_id}")
async def update_entry(
    entry_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    update, errors, raw = parse_entry_update(await request.form())
    if update is None:
        entry = await service.get_entry(db, auth.account.id, entry_id)
        return _entry_page(request, auth, entry, errors=errors, raw=raw, status_code=422)
    changes = {name: getattr(update, name) for name in update.model_fields_set}
    current = await service.get_entry(db, auth.account.id, entry_id)
    if changes.get("times_read") == current.times_read:
        # The form always sends "Times read"; only a changed value is an explicit edit, so
        # finishing a re-read still adds one (FR-029).
        del changes["times_read"]
    await service.update_entry(db, auth.account.id, entry_id, changes, today=now(request).date())
    return RedirectResponse(f"/entries/{entry_id}?msg=saved", status_code=303)


@router.post("/entries/{entry_id}/read-again")
async def read_again(entry_id: uuid.UUID, auth: UiUser, db: DbSession) -> Response:
    await service.read_again(db, auth.account.id, entry_id)
    return RedirectResponse(f"/entries/{entry_id}?msg=reread", status_code=303)


@router.post("/entries/{entry_id}/remove")
async def remove_entry(
    entry_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    form = await request.form()
    if form.get("confirm") != "yes":
        entry = await service.get_entry(db, auth.account.id, entry_id)
        return render(request, "pages/confirm_remove.html", {"entry": entry}, auth=auth)
    await service.remove_entry(db, auth.account.id, entry_id)
    return RedirectResponse("/?msg=removed", status_code=303)
