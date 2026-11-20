"""Import pages (spec 002 contracts/ui-routes.md; research R12).

The same services as the JSON API; the member always comes from the session. No custom
JavaScript: HTMX re-renders the works table, and every form also works without it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from pydantic import TypeAdapter, ValidationError
from starlette.responses import Response

from book_tracker.api.errors import ui_redirect
from book_tracker.auth.dependencies import Authenticated, UiUser, now
from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.imports import MAX_WORKS_PER_IMPORT, WorkState, WorksView
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.imports import ImportPageForm, WorkKey, WorksViewForm
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

# Used with fullmatch: Python's "$" also matches before a final newline (second review, 2).
_AUTHOR_KEY = re.compile(r"OL[0-9]+A")
_WORK_KEY = re.compile(r"OL[0-9]+W")
BAD_STATUS = "Choose how to add the books: Finished, Reading or Want to read"
EXPIRED_NOTICE = (
    "The list had expired, so it was fetched again from Open Library. Tick your books again."
)
STALE_NOTICE = (
    "Open Library couldn't be reached, so this is the list fetched earlier. It expires "
    "within the hour: confirm soon, or come back later for a fresh list."
)
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


_WORK_KEY_RULE: TypeAdapter[str] = TypeAdapter(WorkKey)


def _valid_work_key(value: str) -> bool:
    try:
        _WORK_KEY_RULE.validate_python(value)
    except ValidationError:
        return False
    return True


def _page_form(data: Any) -> tuple[ImportPageForm, str | None]:
    """The posted status and ticks, validated; on a bad value, the defaults and a message."""
    raw = {"status": data.get("status") or ReadingStatus.FINISHED.value,
           "work": [str(v) for v in data.getlist("work")]}  # fmt: skip
    try:
        return ImportPageForm.model_validate(raw), None
    except ValidationError as exc:
        bad_status = any(e["loc"][:1] == ("status",) for e in exc.errors())
        keys = [k for k in raw["work"] if _valid_work_key(k)]  # same rule (third review, 1)
        message = BAD_STATUS if bad_status else service.NOT_IN_LIST
        return ImportPageForm(work=keys), message


def _check_author_key(key: str) -> None:
    if not _AUTHOR_KEY.fullmatch(key):
        raise SourceNotFound()


def _ticks(view: WorksView, keys: Iterable[str]) -> set[str]:
    """The posted ticks that are in this list, as each work's own id (second review, 1).

    An id that has left the list is dropped, so it can't come back as a hidden field the
    member can neither see nor untick; a merged id becomes the work it was merged into.
    """
    return {view.lead_ids[k] for k in keys if k in view.lead_ids}


def _works_url(key: str, form: WorksViewForm) -> str:
    query = {k: v for k, v in (("sort", form.sort), ("q", form.q)) if v and v != "title"}
    return f"/import/authors/{key}" + (f"?{urlencode(query)}" if query else "")


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
    notice: str | None = None,
) -> dict[str, Any]:
    checked = _ticks(view, checked)
    shown = {w.work.source_id for w in view.works}
    return {
        "key": key,
        "view": view,
        "form": form,
        "checked": checked,
        "status": status.value,
        "error": error,
        "note": note,
        "notice": notice or (STALE_NOTICE if view.refresh_failed else None),
        "hidden_ticks": sorted(k for k in checked if k not in shown),  # filtered out (finding 2)
        "selectable": [w for w in view.works if w.state is not WorkState.ON_MY_LIST],
        "max_import": MAX_WORKS_PER_IMPORT,
        "active": "import",
    }


async def _load(
    request: Request, auth: Authenticated, db: Any, source: Any, key: str, form: WorksViewForm
) -> WorksView:
    _check_author_key(key)
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
    try:
        authors = await service.search_authors(db, source, query, now(request))
    except ValidationFailed:
        return render(
            request,
            "pages/import_search.html",
            {"q": q, "error": service.NAME_REQUIRED, "active": "import"},
            auth=auth,
            status_code=422,
        )
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
    expired: str = "",
) -> Response:
    form = _view_form(sort, q)
    try:
        view = await _load(request, auth, db, source, author_key, form)
    except SourceUnavailable:
        return _unreachable(request, auth)
    notice = EXPIRED_NOTICE if expired else None
    context = _works_context(
        author_key, view, form, checked=set(), status=ReadingStatus.FINISHED, notice=notice
    )
    return render(request, "pages/import_works.html", context, auth=auth)


@router.post("/import/authors/{author_key}/view")
async def import_works_view(
    author_key: str, request: Request, auth: UiUser, db: DbSession, source: BookSourceDep
) -> Response:
    """Re-render the table for sort, filter and "Select all shown"; read-only (R12)."""
    data = await request.form()
    form = _view_form(data.get("sort"), data.get("q"))
    posted, error = _page_form(data)
    if is_htmx(request) and error:
        # HTMX drops 4xx/5xx responses, so send the browser to the page (second review, 5).
        return ui_redirect(request, _works_url(author_key, form))
    try:
        view = await _load(request, auth, db, source, author_key, form)
    except SourceUnavailable:
        if is_htmx(request):
            return ui_redirect(request, _works_url(author_key, form))
        return _unreachable(request, auth)
    checked = _ticks(view, posted.work)
    if error:
        context = _works_context(
            author_key, view, form, checked=checked, status=posted.status, error=error
        )
        return render(request, "pages/import_works.html", context, auth=auth, status_code=422)
    note = None
    if data.get("select") == "shown":
        shown = [w.work.source_id for w in view.works if w.state is not WorkState.ON_MY_LIST]
        room = MAX_WORKS_PER_IMPORT - len(checked)
        additions = [k for k in shown if k not in checked]
        if len(additions) > room:
            note = SELECT_LIMIT_NOTE
        checked |= set(additions[: max(room, 0)])
    context = _works_context(
        author_key, view, form, checked=checked, status=posted.status, note=note
    )
    template = "partials/import_works.html" if is_htmx(request) else "pages/import_works.html"
    return render(request, template, context, auth=auth)


@router.post("/import/authors/{author_key}")
async def import_confirm(
    author_key: str, request: Request, auth: UiUser, db: DbSession
) -> Response:
    _check_author_key(author_key)  # before the import lock (second review, finding 6)
    data = await request.form()
    form = _view_form(data.get("sort"), data.get("q"))
    posted, error = _page_form(data)
    expired = ui_redirect(request, f"/import/authors/{author_key}?expired=1")
    if error is None:
        try:
            result = await service.confirm_import(
                db, auth.account.id, author_key=author_key, work_keys=posted.work,
                status=posted.status, now=now(request),
            )  # fmt: skip
        except ConflictError:  # results_expired: reload outside the lock (review finding 1)
            return expired
        except ValidationFailed as exc:
            error = exc.errors[0].message
    if error is not None:
        # Redisplay from the cache only: this request may hold the import lock (finding 1).
        view = await service.cached_works(
            db, auth.account.id, author_key, now(request), sort=form.sort, q=form.q
        )
        if view is None:
            return expired
        context = _works_context(
            author_key, view, form, checked=set(posted.work), status=posted.status, error=error
        )
        return render(request, "pages/import_works.html", context, auth=auth, status_code=422)
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
