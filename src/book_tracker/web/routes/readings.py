"""My list, add a book, and entry pages (FR-016 – FR-020, FR-029)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response

from book_tracker.auth.dependencies import Authenticated, UiUser, today
from book_tracker.domain import models as domain
from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.values import format_series_number, normalize_name, similar_names
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import BookCreate
from book_tracker.schemas.readings import ReadingEntryCreate
from book_tracker.services import catalog as catalog_service
from book_tracker.services import imports as imports_service
from book_tracker.services import readings as service
from book_tracker.services.catalog import NewBook
from book_tracker.services.errors import ConflictError, NotFoundError, ValidationFailed
from book_tracker.web.forms import (
    AddBookForm,
    AuthorRow,
    NewName,
    book_start_form,
    carry_over_form,
    parse_add_book,
    parse_entry_update,
    series_start_form,
)
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
    upcoming = params.get("upcoming") == "1"  # spec 007 R4; anything else is off
    on = today(request)
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
        upcoming_after=on if upcoming else None,
    )
    kept = {
        "q": q,
        # Upcoming only ignores the sort, so links don't carry it (PR #23 review).
        "sort": "" if sort == "title" or upcoming else sort,
        "status": status.value if status else "",
        "author_id": str(author_id) if author_id else "",
        "series_id": str(series_id) if series_id else "",
        "upcoming": "1" if upcoming else "",
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
        "filters_open": any(kept.values()),  # spec 003 FR-007: phone fold starts open
    }
    if is_htmx(request):
        return render(request, "partials/reading_list.html", context, auth=auth)
    authors, series = await service.filter_options(db, auth.account.id)
    context.update(
        {
            # Spec 007 R6: the full page only, so filtering never repeats or drops it.
            "now_out": await service.now_out(db, auth.account.id, on),
            "sort_options": SORT_OPTIONS,
            "statuses": STATUSES,
            "author_options": authors,
            "series_options": series,
        }
    )
    return render(request, "pages/list.html", context, auth=auth)


@router.get("/upcoming")
async def upcoming_page(request: Request, auth: UiUser, db: DbSession) -> Response:
    """My books not out yet, then the family catalog's (spec 007 R5)."""
    view = await service.upcoming_view(db, auth.account.id, today(request))
    return render(request, "pages/upcoming.html", {"view": view, "active": "upcoming"}, auth=auth)


@router.get("/series/{series_id}")
async def series_page(
    series_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    """Every catalog book in the series with my own status, and gaps (spec 006). With
    ``added`` = my own just-added entry, a confirmation (another member's id: nothing)."""
    series, view = await service.whole_series_view(db, auth.account.id, series_id)
    added: domain.ReadingEntry | None = None
    entry_id = _uuid_param(request, "added")
    if entry_id is not None:
        try:
            added = await service.get_entry(db, auth.account.id, entry_id)
        except NotFoundError:
            added = None
    if added is not None and (added.book.series is None or added.book.series.id != series.id):
        added = None  # only a book in this series (PR #22 review)
    return render(
        request, "pages/series.html", {"series": series, "view": view, "added": added}, auth=auth
    )


async def _existing_series(db: DbSession, series_id: uuid.UUID | None) -> domain.Series | None:
    if series_id is None:
        return None
    try:
        return await catalog_service.get_series(db, series_id)
    except NotFoundError:
        return None


# --------------------------------------------------------------------------- add

BOOK_FIELD_MESSAGES = {
    "title": ("title", "Enter a title"),
    "author_ids": ("author_name_0", "Enter at least one author"),
    "series_number": ("series_number", "Choose a series first, or leave the number blank"),
    "series_id": ("series_name", "Choose a series"),
    "isbn_13": ("isbn_13", "Enter a valid 13-digit ISBN"),
}


def book_create_errors(exc: ValidationError) -> dict[str, str]:
    """Map BookCreate validation errors to the form's fields."""
    errors: dict[str, str] = {}
    for error in exc.errors():
        name = str(error["loc"][0]) if error["loc"] else "title"
        field, message = BOOK_FIELD_MESSAGES.get(name, ("title", "Check the book details"))
        errors.setdefault(field, message)
    return errors


def _add_form(
    request: Request,
    auth: Authenticated,
    form: AddBookForm | None = None,
    *,
    status_code: int = 200,
    conflict: ConflictError | None = None,
    author_conflicts: dict[int, ConflictError] | None = None,
    series_conflict: ConflictError | None = None,
    added: domain.ReadingEntry | None = None,
    chosen: domain.Book | None = None,
) -> Response:
    return render(
        request,
        "pages/add_book.html",
        {
            "form": form or AddBookForm(),
            "added": added,
            "chosen": chosen,
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
async def add_book_form(
    request: Request, auth: UiUser, db: DbSession, after: str | None = None
) -> Response:
    """With ``after`` = the member's own just-added entry, a form for the next book
    (spec 004). Any other entry, or a malformed id, gives the plain form (Principle I)."""
    added: domain.ReadingEntry | None = None
    try:
        entry_id = uuid.UUID(after) if after else None
    except ValueError:
        entry_id = None
    if entry_id is not None:
        try:
            added = await service.get_entry(db, auth.account.id, entry_id)
        except NotFoundError:
            added = None
    if added is not None:
        return _add_form(request, auth, carry_over_form(added), added=added)
    # Spec 006: start from a catalog book, or from a series and number, and return to a
    # series page. Unknown or malformed values are ignored (R3).
    form = AddBookForm()
    chosen = await _chosen_book(db, _uuid_param(request, "book"))
    if chosen is not None:
        form = book_start_form(chosen)
    else:
        start_series = await _existing_series(db, _uuid_param(request, "series"))
        if start_series is not None:
            form = series_start_form(start_series, request.query_params.get("number", ""))
    from_series = await _existing_series(db, _uuid_param(request, "from_series"))
    if from_series is not None:
        form.from_series = from_series.id
    return _add_form(request, auth, form, chosen=chosen)


async def _chosen_book(db: DbSession, book_id: uuid.UUID | None) -> domain.Book | None:
    """The catalog book a form starts from, shown as details rather than editable fields:
    saving adds that book as it is (spec 006, PR #22 review)."""
    if book_id is None:
        return None
    try:
        return await catalog_service.get_book(db, book_id)
    except NotFoundError:
        return None


@router.post("/books/add")
async def add_book(request: Request, auth: UiUser, db: DbSession) -> Response:
    form = parse_add_book(await request.form())
    if form.book_id is None:
        await new_name_prompts(db, form)  # spec 005: shown with any field errors
    # A chosen catalog book shows again as details, not editable fields (spec 006).
    chosen = await _chosen_book(db, form.book_id)
    if form.field_errors:
        return _add_form(request, auth, form, status_code=422, chosen=chosen)
    if form.new_names:
        return _add_form(request, auth, form, status_code=409)
    user_id = auth.account.id
    try:
        if form.book_id is not None:
            payload = ReadingEntryCreate(
                book_id=form.book_id,
                status=form.status,
                finished_on=form.finished_on,
                notes=form.notes,
                pre_ordered=form.pre_ordered,
            )
            entry = await service.add_entry(
                db,
                user_id,
                book_id=payload.book_id,
                status=payload.status,
                finished_on=payload.finished_on,
                notes=payload.notes,
                pre_ordered=payload.pre_ordered,
            )
        else:
            author_ids, author_conflicts = await resolve_authors(db, auth, form)
            series_id, series_conflict = await resolve_series(db, auth, form)
            if author_conflicts or series_conflict:
                return _add_form(
                    request,
                    auth,
                    form,
                    status_code=409,
                    author_conflicts=author_conflicts,
                    series_conflict=series_conflict,
                )
            try:
                book = BookCreate(
                    title=form.title,
                    author_ids=author_ids,
                    series_id=series_id,
                    series_number=form.series_number,
                    isbn_13=form.isbn_13,
                    release_date=form.release_date,
                )
            except ValidationError as exc:
                form.errors.update(book_create_errors(exc))
                return _add_form(request, auth, form, status_code=422)
            entry = await service.add_entry(
                db,
                user_id,
                new_book=NewBook(
                    title=book.title,
                    author_ids=book.author_ids,
                    series_id=book.series_id,
                    series_number=book.series_number,
                    isbn_13=book.isbn_13,
                    summary=form.summary,
                    release_date=book.release_date,
                ),
                status=form.status,
                finished_on=form.finished_on,
                notes=form.notes,
                pre_ordered=form.pre_ordered,
            )
    except ConflictError as exc:
        return _add_form(request, auth, form, status_code=409, conflict=exc, chosen=chosen)
    except (ValidationFailed, NotFoundError):
        form.errors["title"] = "That book is no longer in the catalog. Enter its details."
        return _add_form(request, auth, form, status_code=422)
    if form.then == "another":
        return RedirectResponse(f"/books/add?after={entry.id}", status_code=303)
    back = await _existing_series(db, form.from_series)
    if back is not None:  # spec 006: the path is built from a parsed, existing series id
        return RedirectResponse(f"/series/{back.id}?added={entry.id}", status_code=303)
    return RedirectResponse("/?msg=added", status_code=303)


NEW_NAME = "“{}” is not in the family catalog yet"


async def _chosen_author(db: DbSession, row: AuthorRow) -> domain.Author | None:
    """The catalog author a row names: a "Use …" choice, or a picked id whose name still
    matches what was typed (without JavaScript, editing the text doesn't clear the id)."""
    if row.use_id is not None:
        try:
            return await catalog_service.get_author(db, row.use_id)
        except NotFoundError:
            pass
    if row.author_id is not None:
        try:
            chosen = await catalog_service.get_author(db, row.author_id)
        except NotFoundError:
            return None
        if chosen.name.lower() == row.name.lower():
            return chosen
    return None


async def _chosen_series(db: DbSession, form: AddBookForm) -> domain.Series | None:
    """The series counterpart of ``_chosen_author``."""
    if form.use_series_id is not None:
        try:
            return await catalog_service.get_series(db, form.use_series_id)
        except NotFoundError:
            pass
    if form.series_id is not None:
        try:
            chosen = await catalog_service.get_series(db, form.series_id)
        except NotFoundError:
            return None
        if chosen.name.lower() == form.series_name.lower():
            return chosen
    return None


async def new_name_prompts(db: DbSession, form: AddBookForm) -> None:
    """Spec 005: record a prompt for every typed author or series that isn't picked,
    confirmed, or an exact catalog name (that one keeps today's "Already in the catalog"
    choice). Read-only, and runs once per form; each prompt is also a field error, so it
    is in the error summary.

    A "Use …" choice is written back as a picked record (id and catalog name), so it
    sticks when the page comes back for another reason.
    """
    if form.names_checked:
        return
    form.names_checked = True
    confirmed = {row.name for row in form.chosen_authors if row.confirmed == row.name}
    candidates: catalog_service.Candidates | None = None
    for row in form.chosen_authors:
        field = f"author_name_{row.index}"
        chosen = await _chosen_author(db, row)
        if chosen is not None:
            form.raw[f"author_id_{row.index}"] = str(chosen.id)
            form.raw[field] = chosen.name
            continue
        if row.name in confirmed or await catalog_service.author_named(db, row.name):
            continue
        if candidates is None:
            candidates = await catalog_service.author_candidates(db)
        form.new_names[field] = NewName(
            field, "author", row.name, similar_names(row.name, candidates)
        )
        form.errors.setdefault(field, NEW_NAME.format(row.name))
    name = form.series_name
    if not name:
        return
    series = await _chosen_series(db, form)
    if series is not None:
        form.raw["series_id"] = str(series.id)
        form.raw["series_name"] = series.name
        return
    if form.series_confirmed == name or await catalog_service.series_named(db, name):
        return
    similar = similar_names(name, await catalog_service.series_candidates(db))
    form.new_names["series_name"] = NewName("series_name", "series", name, similar)
    form.errors.setdefault("series_name", NEW_NAME.format(name))


async def resolve_authors(
    db: DbSession, auth: Authenticated, form: AddBookForm
) -> tuple[list[uuid.UUID], dict[int, ConflictError]]:
    """Use chosen authors; create the typed ones. Conflicts are reported per row.

    Callers run ``new_name_prompts`` first and stop on a prompt, so a name created here
    was confirmed, or exactly matches a catalog name (which raises today's conflict). A
    name typed in two rows is created once.
    """
    ids: list[uuid.UUID] = []
    conflicts: dict[int, ConflictError] = {}
    created: dict[str, uuid.UUID] = {}
    for row in form.chosen_authors:
        chosen = await _chosen_author(db, row)
        if chosen is not None:
            ids.append(chosen.id)
            continue
        if row.name.lower() in created:
            ids.append(created[row.name.lower()])
            continue
        try:
            author = await catalog_service.create_author(db, auth.account.id, name=row.name)
        except ConflictError as exc:
            conflicts[row.index] = exc
            continue
        created[row.name.lower()] = author.id
        ids.append(author.id)
    return list(dict.fromkeys(ids)), conflicts


async def resolve_series(
    db: DbSession, auth: Authenticated, form: AddBookForm
) -> tuple[uuid.UUID | None, ConflictError | None]:
    """A blank series name means no series, even if a stale id was sent (no-JS editing)."""
    if not form.series_name:
        return None, None
    chosen = await _chosen_series(db, form)
    if chosen is not None:
        return chosen.id, None
    try:
        series = await catalog_service.create_series(db, auth.account.id, name=form.series_name)
    except ConflictError as exc:
        return None, exc
    return series.id, None


# --------------------------------------------------------------------------- book details

ENTRY_FIELDS = frozenset({"status", "finished_on", "times_read", "notes", "pre_ordered"})


def book_form(book: domain.Book) -> AddBookForm:
    """The book's current details as a filled-in form."""
    raw: dict[str, str] = {
        "title": book.title,
        "isbn_13": book.isbn_13 or "",
        "release_date": book.release_date.isoformat() if book.release_date else "",
    }
    if book.series:
        raw["series_name"] = book.series.name
        raw["series_id"] = str(book.series.id)
    if book.series_number is not None:
        raw["series_number"] = format_series_number(book.series_number)
    for i, author in enumerate(book.authors):
        raw[f"author_name_{i}"] = author.name
        raw[f"author_id_{i}"] = str(author.id)
    return AddBookForm(raw=raw)


@dataclass
class BookSaveProblem:
    """Why the book's details weren't saved; field errors are added to the form."""

    status_code: int
    conflict: ConflictError | None = None
    author_conflicts: dict[int, ConflictError] = field(default_factory=dict)
    series_conflict: ConflictError | None = None


async def save_book_details(
    db: DbSession,
    auth: Authenticated,
    book: domain.Book,
    form: AddBookForm,
    *,
    only_if_changed: bool = False,
) -> BookSaveProblem | None:
    """Save the book fields of a checked form; None when saved (or nothing changed)."""
    await new_name_prompts(db, form)
    if form.new_names:
        return BookSaveProblem(409)  # spec 005: confirm or replace new names first
    author_ids, author_conflicts = await resolve_authors(db, auth, form)
    series_id, series_conflict = await resolve_series(db, auth, form)
    if not author_ids and not author_conflicts:
        form.errors["author_name_0"] = "Enter at least one author"
        return BookSaveProblem(422)
    if author_conflicts or series_conflict:
        return BookSaveProblem(
            409, author_conflicts=author_conflicts, series_conflict=series_conflict
        )
    changes: dict[str, Any] = {
        "title": form.title,
        "author_ids": author_ids,
        "series_id": series_id,
        "series_number": form.series_number,
        "isbn_13": form.isbn_13,
        "release_date": _release_date_to_save(book, form),
    }
    if only_if_changed and _unchanged(book, changes):
        return None  # don't mark the book as edited by someone who only changed their notes
    try:
        await catalog_service.update_book(db, auth.account.id, book.id, changes)
    except ConflictError as exc:
        return BookSaveProblem(409, conflict=exc)
    except ValidationFailed as exc:
        form.errors.update({e.field: e.message for e in exc.errors})
        return BookSaveProblem(422)
    return None


def _release_date_to_save(book: domain.Book, form: AddBookForm) -> date | None:
    """The book's current date when the member left the field as the page showed it, so a
    stale page never clears or reverts a date another member set meanwhile (PR #23
    review)."""
    if (
        form.release_date_was is not None
        and form.raw.get("release_date", "") == form.release_date_was
    ):
        return book.release_date
    return form.release_date


def _unchanged(book: domain.Book, changes: dict[str, Any]) -> bool:
    return (
        normalize_name(changes["title"]) == book.title
        and changes["author_ids"] == [a.id for a in book.authors]
        and changes["series_id"] == (book.series.id if book.series else None)
        and changes["series_number"] == book.series_number
        and changes["isbn_13"] == book.isbn_13
        and changes["release_date"] == book.release_date
    )


# --------------------------------------------------------------------------- entry


def _entry_page(
    request: Request,
    auth: Authenticated,
    entry: Any,
    *,
    errors: dict[str, str] | None = None,
    raw: dict[str, Any] | None = None,
    form: AddBookForm | None = None,
    problem: BookSaveProblem | None = None,
    status_code: int = 200,
    source_ref: Any = None,
) -> Response:
    form = form or book_form(entry.book)
    return render(
        request,
        "pages/entry.html",
        {
            "entry": entry,
            "source_ref": source_ref,
            "statuses": STATUSES,
            "errors": errors or {},
            "raw": raw or {},
            "book_form": form,
            "all_errors": {**form.errors, **(errors or {})},
            "conflict": problem.conflict if problem else None,
            "author_conflicts": problem.author_conflicts if problem else {},
            "series_conflict": problem.series_conflict if problem else None,
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
    source_ref = await imports_service.source_ref(db, entry.book.id)
    return _entry_page(request, auth, entry, source_ref=source_ref)


@router.post("/entries/{entry_id}")
async def update_entry(
    entry_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    """Save the member's reading details and, when the form has them, the book's details.

    Nothing is saved unless every field is valid: a refused page rolls the request back.
    """
    data = await request.form()
    current = await service.get_entry(db, auth.account.id, entry_id)  # 404 if not mine
    update, errors, raw = parse_entry_update(data)
    details = parse_add_book(data) if "title" in data else None
    if details is not None:
        for name in ENTRY_FIELDS:  # checked by parse_entry_update
            details.errors.pop(name, None)
        await new_name_prompts(db, details)  # spec 005: shown with any field errors
    if update is None or (details is not None and details.field_errors):
        return _entry_page(
            request, auth, current, errors=errors, raw=raw, form=details, status_code=422
        )
    if details is not None:
        problem = await save_book_details(db, auth, current.book, details, only_if_changed=True)
        if problem is not None:
            return _entry_page(
                request, auth, current, raw=raw, form=details, problem=problem,
                status_code=problem.status_code,
            )  # fmt: skip
    changes = {name: getattr(update, name) for name in update.model_fields_set}
    if changes.get("times_read") == current.times_read:
        # The form always sends "Times read"; only a changed value is an explicit edit, so
        # finishing a re-read still adds one (FR-029).
        del changes["times_read"]
    await service.update_entry(db, auth.account.id, entry_id, changes, today=today(request))
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
