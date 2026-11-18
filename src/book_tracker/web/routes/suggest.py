"""Type-ahead suggestion fragments for the ARIA comboboxes (FR-010, FR-030)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Request
from starlette.responses import Response

from book_tracker.auth.dependencies import UiUser
from book_tracker.persistence.db import DbSession
from book_tracker.services import catalog as service
from book_tracker.web.rendering import render

router = APIRouter(prefix="/suggest", include_in_schema=False)

FIELD = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
LIMIT = 10


@dataclass(frozen=True, slots=True)
class Suggestion:
    id: str
    value: str
    detail: str


def _query(request: Request) -> tuple[str, str]:
    """The field the input belongs to, and its current text.

    HTMX sends the input's own value under its name, plus ``field`` naming it.
    """
    field = request.query_params.get("field", "q")
    if not FIELD.match(field):
        field = "q"
    q = request.query_params.get(field) or request.query_params.get("q") or ""
    return field, q.strip()[:200]


@router.get("/{kind}")
async def suggest(
    kind: Literal["books", "authors", "series"], request: Request, auth: UiUser, db: DbSession
) -> Response:
    field, q = _query(request)
    items: list[Suggestion] = []
    if q:
        if kind == "books":
            items = [
                Suggestion(str(b.id), b.title, ", ".join(a.name for a in b.authors))
                for b in await service.search_books(db, q, LIMIT)
            ]
        elif kind == "authors":
            items = [
                Suggestion(str(a.id), a.name, f"pen name of {a.real_name}" if a.real_name else "")
                for a in await service.search_authors(db, q, LIMIT)
            ]
        else:
            items = [
                Suggestion(str(s.id), s.name, "") for s in await service.search_series(db, q, LIMIT)
            ]
    return render(
        request,
        "partials/suggestions.html",
        {"field": field, "items": items, "q": q, "kind": kind},
        auth=auth,
    )
