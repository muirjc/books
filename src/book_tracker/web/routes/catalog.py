"""Catalog edit pages: books, authors and series. Any member may edit (FR-009, FR-014)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response

from book_tracker.auth.dependencies import Authenticated, UiUser
from book_tracker.domain import models as domain
from book_tracker.domain.imports import SourceRef
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import AuthorUpdate, SeriesWrite, SummaryCreate
from book_tracker.services import catalog as service
from book_tracker.services import imports as imports_service
from book_tracker.services import summaries
from book_tracker.services.errors import ConflictError, ValidationFailed
from book_tracker.web.forms import AddBookForm, parse_add_book, text
from book_tracker.web.rendering import render
from book_tracker.web.routes.readings import book_form, save_book_details

router = APIRouter(prefix="/catalog", include_in_schema=False)

SAVED = "Saved."
AUTHOR_MESSAGES = {
    "name": "Enter the author's name, up to 200 characters",
    "sort_name": "Keep the sort name to 200 characters or fewer",
    "real_name": "Keep the real name to 200 characters or fewer",
}


def _message(request: Request) -> str | None:
    return SAVED if request.query_params.get("msg") == "saved" else None


# --------------------------------------------------------------------------- books


def _book_page(
    request: Request,
    auth: Authenticated,
    book: domain.Book,
    form: AddBookForm,
    *,
    status_code: int = 200,
    conflict: ConflictError | None = None,
    author_conflicts: dict[int, ConflictError] | None = None,
    series_conflict: ConflictError | None = None,
    source_ref: SourceRef | None = None,
) -> Response:
    return render(
        request,
        "pages/edit_book.html",
        {
            "book": book,
            "form": form,
            "conflict": conflict,
            "author_conflicts": author_conflicts or {},
            "series_conflict": series_conflict,
            "source_ref": source_ref,
            "message": _message(request),
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
    return _book_page(request, auth, book, book_form(book), source_ref=source_ref)


@router.post("/books/{book_id}/edit")
async def edit_book(book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession) -> Response:
    book = await service.get_book(db, book_id)
    form = parse_add_book(await request.form())
    if form.errors:
        return _book_page(request, auth, book, form, status_code=422)
    problem = await save_book_details(db, auth, book, form)
    if problem is not None:
        return _book_page(
            request, auth, book, form, status_code=problem.status_code,
            conflict=problem.conflict, author_conflicts=problem.author_conflicts,
            series_conflict=problem.series_conflict,
        )  # fmt: skip
    return RedirectResponse(f"/catalog/books/{book_id}/edit?msg=saved", status_code=303)


# --------------------------------------------------------------------------- authors


def _author_page(
    request: Request,
    auth: Authenticated,
    author: domain.Author,
    values: dict[str, Any] | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
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
        {"author": author, "values": values, "errors": errors or {}, "message": _message(request)},
        auth=auth,
        status_code=status_code,
    )


@router.get("/authors/{author_id}/edit")
async def edit_author_form(
    author_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    return _author_page(request, auth, await service.get_author(db, author_id))


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
        return _author_page(request, auth, author, values, errors, status_code=422)
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    try:
        await service.update_author(db, auth.account.id, author_id, changes)
    except ValidationFailed as exc:
        errors = {e.field: e.message for e in exc.errors}
        return _author_page(request, auth, author, values, errors, status_code=422)
    except ConflictError as exc:
        errors = {"name": f"{exc.title}: “{exc.existing_label}”"}
        return _author_page(request, auth, author, values, errors, status_code=409)
    return RedirectResponse(f"/catalog/authors/{author_id}/edit?msg=saved", status_code=303)


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
) -> Response:
    return render(
        request,
        "pages/summary.html",
        {
            "book": book,
            "history": await summaries.history(db, book.id),
            "text_value": text_value,
            "errors": {"text": error} if error else {},
            "message": _message(request),
        },
        auth=auth,
        status_code=status_code,
    )


@router.get("/books/{book_id}/summary")
async def summary_form(
    book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    return await _summary_page(request, auth, db, await service.get_book(db, book_id))


@router.post("/books/{book_id}/summary")
async def save_summary(
    book_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    book = await service.get_book(db, book_id)
    value = text(await request.form(), "text")
    try:
        body = SummaryCreate.model_validate({"text": value})
    except ValidationError:
        return await _summary_page(
            request,
            auth,
            db,
            book,
            text_value=value,
            error="Write a summary of 1 to 5,000 characters",
            status_code=422,
        )
    await summaries.save_manual_summary(db, auth.account.id, book_id, body.text)
    return RedirectResponse(f"/catalog/books/{book_id}/summary?msg=saved", status_code=303)
