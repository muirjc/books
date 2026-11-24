"""The Catalog page (spec 010), and the catalog edit pages: books, authors and series. Any
member may edit (FR-009, FR-014)."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response

from book_tracker.auth.dependencies import Authenticated, UiUser, now
from book_tracker.domain import models as domain
from book_tracker.domain.drafts import CachedDraft, DraftView
from book_tracker.domain.imports import SourceRef
from book_tracker.domain.values import format_series_number
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import (
    AuthorUpdate,
    CatalogQuery,
    DraftForm,
    SeriesSuggestion,
    SeriesWrite,
    SummaryCreate,
    SummaryForm,
)
from book_tracker.services import authors as authors_service
from book_tracker.services import catalog as service
from book_tracker.services import drafts as drafts_service
from book_tracker.services import imports as imports_service
from book_tracker.services import readings as readings_service
from book_tracker.services import summaries
from book_tracker.services.errors import ConflictError, ValidationFailed
from book_tracker.sources.dependencies import BookSourceDep
from book_tracker.sources.summary_generator import SummaryGeneratorDep
from book_tracker.web import quick
from book_tracker.web.drafting import draft_for_page
from book_tracker.web.forms import AddBookForm, parse_add_book, text
from book_tracker.web.rendering import is_htmx, render
from book_tracker.web.routes.readings import (
    MERGED,
    PAGE_SIZE,
    book_form,
    keep_unedited,
    new_name_prompts,
    save_book_details,
)

router = APIRouter(prefix="/catalog", include_in_schema=False)

SAVED = "Saved."
AUTHOR_MESSAGES = {
    "name": "Enter the author's name, up to 200 characters",
    "sort_name": "Keep the sort name to 200 characters or fewer",
    "real_name": "Keep the real name to 200 characters or fewer",
}


def _message(request: Request) -> str | None:
    msg = request.query_params.get("msg")
    return SAVED if msg == "saved" else MERGED if msg == "merged" else None


# --------------------------------------------------------------------------- the catalog

CATALOG_SORT_OPTIONS = [
    ("title", "Title (A–Z)"),
    ("-title", "Title (Z–A)"),
    ("author", "Author"),
    ("series", "Series"),
    ("-added", "Newest in the catalog"),
]


@router.get("")
async def catalog_page(request: Request, auth: UiUser, db: DbSession) -> Response:
    """Every catalog book, searched, sorted, filtered and paged; HTMX gets just the list
    (spec 010). The query is validated by ``CatalogQuery``; bad values fall back to the
    defaults."""
    params = request.query_params
    query = CatalogQuery.model_validate(
        {name: params[name] for name in CatalogQuery.model_fields if name in params}
    )
    view = await readings_service.catalog_view(
        db,
        auth.account.id,
        page=query.page,
        page_size=PAGE_SIZE,
        q=query.q,
        sort=query.sort,
        not_mine=query.not_mine,
    )
    kept = {
        "q": query.q,
        "sort": "" if query.sort == "title" else query.sort,
        "not_mine": "1" if query.not_mine else "",
    }
    encoded = urlencode({k: v for k, v in kept.items() if v})
    context: dict[str, Any] = {
        "view": view,
        "active": "catalog",
        "filters": kept,
        "sort": query.sort,
        "sort_options": CATALOG_SORT_OPTIONS,
        "query_without_page": f"{encoded}&" if encoded else "",
        "filtered": bool(query.q or query.not_mine),
        "filters_open": any(kept.values()),
        "htmx": is_htmx(request),
        "quick": await quick.notice(request, db, auth),  # spec 015
    }
    template = "partials/catalog_list.html" if context["htmx"] else "pages/catalog.html"
    return render(request, template, context, auth=auth)


# --------------------------------------------------------------------------- books


STORY_MESSAGES = {
    "story_already": "That story is already in this book.",
    "story_removed": "Story removed from this book.",
    "story_deleted": "Story deleted from the catalog.",
}


def _story_message(request: Request, stories: list[domain.Story]) -> str | None:
    """Spec 009 R6: "Added the story …" names a story only if it is in this book, looked
    up by id, so a crafted link can't show made-up text."""
    msg = request.query_params.get("msg", "")
    if msg == "story_added":
        added = request.query_params.get("story", "")
        for story in stories:
            if str(story.id) == added:
                return f"Added the story “{story.title}”."
        return None
    return STORY_MESSAGES.get(msg)


async def _book_page(
    request: Request,
    auth: Authenticated,
    db: DbSession,
    book: domain.Book,
    form: AddBookForm,
    *,
    status_code: int = 200,
    conflict: ConflictError | None = None,
    author_conflicts: dict[int, ConflictError] | None = None,
    series_conflict: ConflictError | None = None,
    source_ref: SourceRef | None = None,
    suggested: bool = False,
) -> Response:
    stories = await service.book_stories(db, book.id)
    return render(
        request,
        "pages/edit_book.html",
        {
            "book": book,
            "stories": stories,
            "story_message": _story_message(request, stories),
            "form": form,
            "conflict": conflict,
            "author_conflicts": author_conflicts or {},
            "series_conflict": series_conflict,
            "source_ref": source_ref,
            "message": _message(request),
            "suggested": suggested,
            "my_entry": await readings_service.entry_for_book(db, auth.account.id, book.id),
        },
        auth=auth,
        status_code=status_code,
    )


@router.get("/books/{book_id}/edit")
async def edit_book_form(
    book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    book = await service.get_book(db, book_id)
    source_ref = await imports_service.source_ref(db, book_id)
    form = book_form(book)
    # Spec 012 AC-20: the series suggestion of this book's own current AI draft, filled in
    # but not saved. It is read from the stored draft, never from the request.
    query = SeriesSuggestion.model_validate(dict(request.query_params))
    draft = await drafts_service.draft_for_book(db, query.suggest_draft, book, now(request))
    suggested = draft is not None and bool(draft.series_name)
    if draft is not None and draft.series_name:
        form.raw["series_name"] = draft.series_name
        form.raw.pop("series_id", None)
        number = draft.series_number
        form.raw["series_number"] = format_series_number(number) if number is not None else ""
    return await _book_page(
        request, auth, db, book, form, source_ref=source_ref, suggested=suggested
    )


@router.post("/books/{book_id}/edit")
async def edit_book(book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession) -> Response:
    book = await service.get_book(db, book_id)
    form = parse_add_book(await request.form())
    keep_unedited(book, form)  # books-mbx, before any name checks
    await new_name_prompts(db, form)  # spec 005: shown with any field errors
    if form.field_errors:
        return await _book_page(request, auth, db, book, form, status_code=422)
    problem = await save_book_details(db, auth, book, form)
    if problem is not None:
        return await _book_page(
            request, auth, db, book, form, status_code=problem.status_code,
            conflict=problem.conflict, author_conflicts=problem.author_conflicts,
            series_conflict=problem.series_conflict,
        )  # fmt: skip
    msg = "merged" if form.others_kept else "saved"
    return RedirectResponse(f"/catalog/books/{book_id}/edit?msg={msg}", status_code=303)


# --------------------------------------------------------------------------- authors


FAVORITE_MINE = (
    "This author is one of your favorite authors. Remove them from your favorites to delete them."
)
FAVORITE_OTHER = "A family member has this author as a favorite, so they can't be deleted."


async def _favorite_block(db: DbSession, auth: Authenticated, author: domain.Author) -> str | None:
    """Why an author no book lists can't be deleted: my own favorite, or some member's
    (spec 011; the refusal names nobody, constitution 2.0.0)."""
    if await authors_service.is_favorite(db, auth.account.id, author.id):
        return FAVORITE_MINE
    if await service.author_favorited(db, author.id):
        return FAVORITE_OTHER
    return None


async def _author_page(
    request: Request,
    auth: Authenticated,
    db: DbSession,
    author: domain.Author,
    values: dict[str, Any] | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
    delete_problem: str | None = None,
) -> Response:
    books = await service.author_books(db, author.id)
    stories = await service.author_stories(db, author.id)
    # Spec 011: only an author with no works can be blocked by a favorite.
    favorite_block = None if books or stories else await _favorite_block(db, auth, author)
    if values is None:
        values = {
            "name": author.name,
            "sort_name": author.sort_name,
            "is_pen_name": author.is_pen_name,
            "real_name": author.real_name or "",
        }
    return render(
        request,
        "pages/edit_author.html",
        {
            "author": author,
            "favorite_block": favorite_block,
            "books": books,
            "stories": stories,  # spec 009
            "values": values,
            "errors": errors or {},
            "message": _message(request),
            "delete_problem": delete_problem,
        },
        auth=auth,
        status_code=status_code,
    )


@router.get("/authors/{author_id}/edit")
async def edit_author_form(
    author_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    author = await service.get_author(db, author_id)
    return await _author_page(request, auth, db, author)


@router.post("/authors/{author_id}/edit")
async def edit_author(
    author_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    author = await service.get_author(db, author_id)
    form = await request.form()
    values: dict[str, Any] = {
        "name": text(form, "name"),
        "sort_name": text(form, "sort_name"),
        "is_pen_name": form.get("is_pen_name") in ("on", "true", "1"),
        "real_name": text(form, "real_name"),
    }
    try:
        body = AuthorUpdate.model_validate(
            {
                **values,
                "sort_name": values["sort_name"] or None,
                "real_name": values["real_name"] or None,
            }
        )
    except ValidationError as exc:
        errors: dict[str, str] = {}
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "name"
            errors.setdefault(field, AUTHOR_MESSAGES.get(field, "Check this field"))
        return await _author_page(
            request,
            auth,
            db,
            author,
            values,
            errors,
            status_code=422,
        )
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    try:
        await service.update_author(db, auth.account.id, author_id, changes)
    except ValidationFailed as exc:
        errors = {e.field: e.message for e in exc.errors}
        return await _author_page(
            request,
            auth,
            db,
            author,
            values,
            errors,
            status_code=422,
        )
    except ConflictError as exc:
        errors = {"name": f"{exc.title}: “{exc.existing_label}”"}
        return await _author_page(
            request,
            auth,
            db,
            author,
            values,
            errors,
            status_code=409,
        )
    return RedirectResponse(f"/catalog/authors/{author_id}/edit?msg=saved", status_code=303)


def _deleted_sig(request: Request, name: str) -> str:
    """Signs the deleted author's name in the redirect, so a crafted link can't show a
    false "Deleted" message (PR #24 review)."""
    key = request.app.state.settings.secret_key.get_secret_value().encode()
    return hmac.new(key, b"deleted-author\0" + name.encode(), hashlib.sha256).hexdigest()


@router.get("/authors/unused")
async def unused_authors(request: Request, auth: UiUser, db: DbSession) -> Response:
    """Authors no book lists, so they can be found and deleted (spec 008)."""
    params = request.query_params
    name, sig = params.get("author", ""), params.get("sig", "")
    deleted = (
        name
        if params.get("msg") == "deleted"
        and name
        and hmac.compare_digest(sig, _deleted_sig(request, name))
        else None
    )
    return render(
        request,
        "pages/unused_authors.html",
        {"authors": await service.unused_authors(db), "deleted": deleted},
        auth=auth,
    )


async def _has_works(db: DbSession, author: domain.Author, outcome: str) -> str | None:
    """Why the author can't be deleted after all: a book (spec 008) or a story (spec 009)
    lists them now."""
    if await service.author_books(db, author.id):
        return f"“{author.name}” now has a book, so it {outcome}."
    if await service.author_stories(db, author.id):
        return f"“{author.name}” now has a story, so it {outcome}."
    return None


@router.post("/authors/{author_id}/delete")
async def delete_author(
    author_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    """Without ``confirm=yes``, ask first; then delete if no book lists the author."""
    author = await service.get_author(db, author_id)  # 404 if unknown
    form = await request.form()
    if form.get("confirm") != "yes":
        problem = await _has_works(db, author, "can't be deleted")
        if problem:  # linked since Edit author was shown: don't claim it has none
            return await _author_page(
                request, auth, db, author, delete_problem=problem, status_code=409
            )
        if await _favorite_block(db, auth, author):  # spec 011: Edit author says why
            return await _author_page(request, auth, db, author, status_code=409)
        return render(request, "pages/confirm_delete_author.html", {"author": author}, auth=auth)
    try:
        await service.delete_author(db, auth.account.id, author_id)
    except ConflictError as exc:
        if exc.code == "author_is_favorite":  # spec 011: favorited meanwhile
            # Say why even if the favorite is gone again by now (PR #30 review).
            reason = None if await _favorite_block(db, auth, author) else FAVORITE_OTHER
            return await _author_page(
                request, auth, db, author, delete_problem=reason, status_code=409
            )
        # The foreign key caught a link made in the same instant (spec 008).
        problem = await _has_works(db, author, "wasn't deleted") or (
            f"“{author.name}” now has a book, so it wasn't deleted."
        )
        return await _author_page(
            request, auth, db, author, delete_problem=problem, status_code=409
        )
    query = urlencode(
        {"msg": "deleted", "author": author.name, "sig": _deleted_sig(request, author.name)}
    )
    return RedirectResponse(f"/catalog/authors/unused?{query}", status_code=303)


# --------------------------------------------------------------------------- series


async def _series_page(
    request: Request,
    auth: Authenticated,
    db: DbSession,
    series: domain.Series,
    name: str | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    return render(
        request,
        "pages/edit_series.html",
        {
            "series": series,
            "books": await service.series_books(db, series.id),
            "name": series.name if name is None else name,
            "errors": errors or {},
            "message": _message(request),
        },
        auth=auth,
        status_code=status_code,
    )


@router.get("/series/{series_id}/edit")
async def edit_series_form(
    series_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    return await _series_page(request, auth, db, await service.get_series(db, series_id))


@router.post("/series/{series_id}/edit")
async def edit_series(
    series_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    series = await service.get_series(db, series_id)
    name = text(await request.form(), "name")
    try:
        body = SeriesWrite.model_validate({"name": name})
    except ValidationError:
        return await _series_page(
            request, auth, db, series, name, {"name": "Enter a series name"}, 422
        )
    try:
        await service.update_series(db, auth.account.id, series_id, name=body.name)
    except ConflictError as exc:
        errors = {"name": f"{exc.title}: “{exc.existing_label}”"}
        return await _series_page(request, auth, db, series, name, errors, 409)
    return RedirectResponse(f"/catalog/series/{series_id}/edit?msg=saved", status_code=303)


# --------------------------------------------------------------------------- summaries


async def _summary_page(
    request: Request,
    auth: Authenticated,
    db: DbSession,
    book: domain.Book,
    *,
    text_value: str = "",
    error: str | None = None,
    status_code: int = 200,
    draft: DraftView | None = None,
    draft_error: str | None = None,
    drafts_left: int | None = None,
    draft_id: str | None = None,
    before_text: str | None = None,
) -> Response:
    """The Summary page. ``draft_id`` keeps a shown draft's id through a failed Regenerate
    or a rejected save, so AI text never saves as hand-written (PR #32 review)."""
    context = {
        "book": book,
        "history": await summaries.history(db, book.id),
        "text_value": text_value,
        "errors": {"text": error} if error else {},
        "message": _message(request),
        "draft": draft,
        "draft_error": draft_error,
        "drafts_left": drafts_left,
        "draft_id": draft.id if draft else draft_id,
        "before_text": before_text,
        "my_entry": await readings_service.entry_for_book(db, auth.account.id, book.id),
    }
    template = "partials/summary_draft.html" if is_htmx(request) else "pages/summary.html"
    return render(request, template, context, auth=auth, status_code=status_code)


@router.get("/books/{book_id}/summary")
async def summary_form(
    book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    return await _summary_page(request, auth, db, await service.get_book(db, book_id))


@router.post("/books/{book_id}/summary/draft")
async def draft_summary(
    book_id: uuid.UUID,
    request: Request,
    auth: UiUser,
    db: DbSession,
    source: BookSourceDep,
    generator: SummaryGeneratorDep,
) -> Response:
    """Draft with AI / Regenerate (spec 012 AC-02, AC-09, AC-16): never saves a summary."""
    book = await service.get_book(db, book_id)
    data = await request.form()
    form = DraftForm.model_validate({
        "text": text(data, "text")[:5000],
        "regenerate": data.get("regenerate", ""),
        "draft_id": data.get("draft_id"),
        "before_text": _optional_text(data.get("before_text")),
    })  # fmt: skip
    before = form.before_text if form.before_text is not None else form.text
    view, problem, left = await draft_for_page(
        request, auth, db, drafts_service.facts_for(book),
        regenerate=form.regenerate, source=source, generator=generator,
    )  # fmt: skip
    if view is not None:
        return await _summary_page(
            request, auth, db, book, text_value=view.text, draft=view, drafts_left=left,
            before_text=before,
        )  # fmt: skip
    return await _summary_page(
        request, auth, db, book, text_value=form.text, draft_error=problem, drafts_left=left,
        draft_id=form.draft_id, before_text=before if form.draft_id else None,
    )  # fmt: skip


def _optional_text(value: object) -> str | None:
    return value[:5000] if isinstance(value, str) else None


@router.post("/books/{book_id}/summary/discard")
async def discard_draft(
    book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    """Discard draft: the box as it was before the first draft (spec 012 AC-06)."""
    book = await service.get_book(db, book_id)
    data = await request.form()
    form = SummaryForm.model_validate({"before_text": _optional_text(data.get("before_text"))})
    return await _summary_page(request, auth, db, book, text_value=form.before_text or "")


@router.post("/books/{book_id}/summary")
async def save_summary(
    book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    book = await service.get_book(db, book_id)
    data = await request.form()
    form = SummaryForm.model_validate({
        "text": text(data, "text"),
        "draft_id": data.get("draft_id"),
        "then": data.get("then"),
        "before_text": _optional_text(data.get("before_text")),
    })  # fmt: skip
    try:
        body = SummaryCreate.model_validate({"text": form.text})
    except ValidationError:
        return await _summary_page(
            request, auth, db, book, text_value=form.text,
            error="Write a summary of 1 to 5,000 characters", status_code=422,
            draft_id=form.draft_id, before_text=form.before_text,
        )  # fmt: skip
    await summaries.save_summary(
        db, auth.account.id, book_id, body.text, draft_id=form.draft_id, now=now(request)
    )
    if form.then == "series":
        draft = await drafts_service.draft_for_book(db, form.draft_id, book, now(request))
        if draft is not None and draft.series_name:
            return RedirectResponse(_suggestion_url(book_id, draft), status_code=303)
    return RedirectResponse(f"/catalog/books/{book_id}/summary?msg=saved", status_code=303)


def _suggestion_url(book_id: uuid.UUID, draft: CachedDraft) -> str:
    return f"/catalog/books/{book_id}/edit?{urlencode({'suggest_draft': draft.id})}"


@router.post("/books/{book_id}/summary/use-series")
async def use_series(book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession) -> Response:
    """Use this series with an unsaved draft: offer to save it first (spec 012 AC-21)."""
    book = await service.get_book(db, book_id)
    data = await request.form()
    form = SummaryForm.model_validate(
        {"text": text(data, "text"), "draft_id": data.get("draft_id")}
    )
    draft = await drafts_service.draft_for_book(db, form.draft_id, book, now(request))
    if draft is None or not draft.series_name:
        return RedirectResponse(f"/catalog/books/{book_id}/summary", status_code=303)
    return render(
        request,
        "pages/use_series.html",
        {
            "book": book,
            "draft": draft,
            "text_value": form.text,
            "edit_url": _suggestion_url(book_id, draft),
        },
        auth=auth,
    )
