"""Template rendering for the server-rendered pages."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from book_tracker.auth.dependencies import today
from book_tracker.domain.values import format_series_number, is_now_out, is_upcoming
from book_tracker.web.forms import SHOWN_FIELDS

if TYPE_CHECKING:
    from book_tracker.auth.dependencies import Authenticated

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STATUS_LABELS = {"want_to_read": "Want to read", "reading": "Reading", "finished": "Finished"}


def _series_number(value: Decimal | None) -> str:
    return format_series_number(value) if value is not None else ""


def _date(value: date | datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%-d %b %Y")


templates.env.filters["series_number"] = _series_number
templates.env.filters["nice_date"] = _date
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["is_upcoming"] = is_upcoming  # spec 007
templates.env.globals["is_now_out"] = is_now_out
templates.env.globals["SHOWN_FIELDS"] = SHOWN_FIELDS  # books-mbx


def is_htmx(request: Request) -> bool:
    """An htmx request wanting a fragment. A history restore (a cache miss on Back) needs
    the whole page, so it isn't one (PR #29 review)."""
    return (
        request.headers.get("hx-request") == "true"
        and request.headers.get("hx-history-restore-request") != "true"
    )


def render(
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
    *,
    auth: Authenticated | None = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> Response:
    ctx: dict[str, Any] = {
        "current_user": auth.account if auth else None,
        "csrf_token": auth.csrf_token if auth else "",
        "today": today(request),  # spec 007: "Coming" and "Now out" use the app clock
    }
    ctx.update(context or {})
    ctx.setdefault("active", ACTIVE_TABS.get(name))  # spec 014 AC-10
    ctx.setdefault("here", here(request))  # spec 015: rows' return address
    if status_code >= 400:
        # The request failed: get_db rolls back instead of committing partial writes.
        request.state.db_rollback = True
    # A URL may answer with a page or an htmx fragment, so caches must key on the header.
    headers = {"Vary": "HX-Request", **(headers or {})}
    return templates.TemplateResponse(request, name, ctx, status_code=status_code, headers=headers)


# Spec 014 AC-10: the main navigation tab each page belongs to, unless the route says.
ACTIVE_TABS = {
    "pages/entry.html": "list",
    "pages/favorite_authors.html": "list",
    "pages/confirm_remove.html": "list",
    "pages/change_password.html": "password",
    **{
        f"pages/{page}.html": "catalog"
        for page in (
            "edit_book", "edit_series", "edit_author", "edit_story", "add_story", "summary",
            "use_series", "unused_authors", "confirm_delete_author", "confirm_remove_story",
            "series", "author",
        )
    },
    **{
        f"pages/{page}.html": "import"
        for page in ("import_search", "import_authors", "import_works", "import_summary")
    },
}  # fmt: skip


def here(request: Request) -> str:
    """This page's path and query, without an earlier quick-add notice (spec 015)."""
    query = [
        (k, v) for k, v in request.query_params.multi_items() if k not in ("wanted", "already")
    ]
    return request.url.path + (f"?{urlencode(query)}" if query else "")


def render_error(request: Request, status_code: int, title: str) -> Response:
    return render(
        request,
        "pages/error.html",
        {"status_code": status_code, "title": title},
        status_code=status_code,
    )
