"""Template rendering for the server-rendered pages."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    return request.headers.get("hx-request") == "true"


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
    if status_code >= 400:
        # The request failed: get_db rolls back instead of committing partial writes.
        request.state.db_rollback = True
    return templates.TemplateResponse(request, name, ctx, status_code=status_code, headers=headers)


def render_error(request: Request, status_code: int, title: str) -> Response:
    return render(
        request,
        "pages/error.html",
        {"status_code": status_code, "title": title},
        status_code=status_code,
    )
