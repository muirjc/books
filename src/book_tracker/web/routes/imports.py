"""Import pages (spec 002 contracts/ui-routes.md; research R12).

The same services as the JSON API; the member always comes from the session. No custom
JavaScript: HTMX re-renders the works table, and every form also works without it.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.responses import Response

from book_tracker.api.errors import ui_redirect
from book_tracker.auth.dependencies import Authenticated, UiUser, now
from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.imports import MAX_WORKS_PER_IMPORT, WorkState, WorksView
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.imports import WorksViewForm
from book_tracker.services import imports as service
from book_tracker.services.errors import (
    ConflictError,
    SourceNotFound,
    SourceUnavailable,
    ValidationFailed,
)
from book_tracker.sources.dependencies import BookSourceDep
from book_tracker.web.rendering import is_htmx, render

router = APIRouter()

_AUTHOR_KEY = re.compile(r"^OL[0-9]+A$")
SELECT_LIMIT_NOTE = (
    f"Only the first {MAX_WORKS_PER_IMPORT} shown were ticked: you can add up to "
    f"{MAX_WORKS_PER_IMPORT} books at a time."
)


def _unreachable(request: Request, auth: Authenticated, q: str = "") -> Response:
    return render(
        request,
        "pages/import_search.html",
        {"q": q, "unreachable": SourceUnavailable.title, "active": "import"},
        auth=auth,
        status_code=503,
    )


def _status(value: object) -> ReadingStatus:
    try:
        return ReadingStatus(str(value))
    except ValueError:
        return ReadingStatus.FINISHED


def _view_form(sort: object, q: object) -> WorksViewForm:
    try:
        return WorksViewForm.model_validate({"sort": sort or "title", "q": q or None})
    except ValidationError:
        return WorksViewForm()


def _works_context(
    key: str,
    view: WorksView,
    form: WorksViewForm,
    *,
    checked: set[str],
    status: ReadingStatus,
    error: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "view": view,
        "form": form,
        "checked": checked,
        "status": status.value,
        "error": error,
        "note": note,
        "selectable": [w for w in view.works if w.state is not WorkState.ON_MY_LIST],
        "max_import": MAX_WORKS_PER_IMPORT,
        "active": "import",
    }


async def _load(
    request: Request, auth: Authenticated, db: Any, source: Any, key: str, form: WorksViewForm
) -> WorksView:
    if not _AUTHOR_KEY.match(key):
        raise SourceNotFound()
    return await service.list_works(
        db, source, auth.account.id, key, now(request), sort=form.sort, q=form.q
    )


@router.get("/import")
async def import_search(request: Request, auth: UiUser) -> Response:
    return render(request, "pages/import_search.html", {"q": "", "active": "import"}, auth=auth)


@router.get("/import/authors")
async def import_authors(
    request: Request, auth: UiUser, db: DbSession, source: BookSourceDep, q: str = ""
) -> Response:
    query = q.strip()
    if not query or len(query) > 200:
        return render(
            request,
            "pages/import_search.html",
            {"q": q, "error": "Enter an author's name", "active": "import"},
            auth=auth,
            status_code=422,
        )
    try:
        authors = await service.search_authors(db, source, query, now(request))
    except SourceUnavailable:
        return _unreachable(request, auth, query)
    if len(authors) == 1:
        return ui_redirect(request, f"/import/authors/{authors[0].source_id}")
    return render(
        request,
        "pages/import_authors.html",
        {"q": query, "authors": authors, "active": "import"},
        auth=auth,
    )


@router.get("/import/authors/{author_key}")
async def import_works(
    author_key: str,
    request: Request,
    auth: UiUser,
    db: DbSession,
    source: BookSourceDep,
    sort: str = "",
    q: str = "",
) -> Response:
    form = _view_form(sort, q)
    try:
        view = await _load(request, auth, db, source, author_key, form)
    except SourceUnavailable:
        return _unreachable(request, auth)
    context = _works_context(author_key, view, form, checked=set(), status=ReadingStatus.FINISHED)
    return render(request, "pages/import_works.html", context, auth=auth)


@router.post("/import/authors/{author_key}/view")
async def import_works_view(
    author_key: str, request: Request, auth: UiUser, db: DbSession, source: BookSourceDep
) -> Response:
    """Re-render the table for sort, filter and "Select all shown"; read-only (R12)."""
    data = await request.form()
    form = _view_form(data.get("sort"), data.get("q"))
    try:
        view = await _load(request, auth, db, source, author_key, form)
    except SourceUnavailable:
        return _unreachable(request, auth)
    checked = {str(v) for v in data.getlist("work")}
    note = None
    if data.get("select") == "shown":
        shown = [w.work.source_id for w in view.works if w.state is not WorkState.ON_MY_LIST]
        room = MAX_WORKS_PER_IMPORT - len(checked)
        additions = [k for k in shown if k not in checked]
        if len(additions) > room:
            note = SELECT_LIMIT_NOTE
        checked |= set(additions[: max(room, 0)])
    context = _works_context(
        author_key, view, form, checked=checked, status=_status(data.get("status")), note=note
    )
    template = "partials/import_works.html" if is_htmx(request) else "pages/import_works.html"
    return render(request, template, context, auth=auth)


@router.post("/import/authors/{author_key}")
async def import_confirm(
    author_key: str, request: Request, auth: UiUser, db: DbSession, source: BookSourceDep
) -> Response:
    data = await request.form()
    keys = [str(v) for v in data.getlist("work")]
    status = _status(data.get("status"))
    form = _view_form(data.get("sort"), data.get("q"))
    try:
        result = await service.confirm_import(
            db, auth.account.id, author_key=author_key, work_keys=keys,
            status=status, now=now(request),
        )  # fmt: skip
    except (ValidationFailed, ConflictError) as exc:
        message = exc.errors[0].message if isinstance(exc, ValidationFailed) else exc.title
        code = 422 if isinstance(exc, ValidationFailed) else 409
        try:
            view = await _load(request, auth, db, source, author_key, form)
        except SourceUnavailable:
            return _unreachable(request, auth)
        context = _works_context(
            author_key, view, form, checked=set(keys), status=status, error=message
        )
        return render(request, "pages/import_works.html", context, auth=auth, status_code=code)
    return render(
        request,
        "pages/import_summary.html",
        {
            "result": result,
            "new_count": sum(1 for b in result.added if b.new_to_catalog),
            "key": author_key,
            "active": "import",
        },
        auth=auth,
    )
