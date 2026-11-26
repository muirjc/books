"""Type-ahead suggestion fragments for the ARIA comboboxes (FR-010, FR-030)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Request
from starlette.responses import Response

from book_tracker.auth.dependencies import UiUser
from book_tracker.domain.values import format_series_number
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import SearchQuery
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
    return field, SearchQuery.model_validate({"q": q}).q


@router.get("/{kind}")
async def suggest(
    kind: Literal["books", "authors", "series", "stories"],
    request: Request,
    auth: UiUser,
    db: DbSession,
) -> Response:
    field, q = _query(request)
    items: list[Suggestion] = []
    if q:
        if kind == "books":
            books = await service.search_books(db, q, LIMIT)
            lowered = q.lower()
            # Spec 009 R7: a book found only by a story's title says which story.
            stories = await service.story_matches(
                db,
                [
                    b.id
                    for b in books
                    if lowered not in b.title.lower()
                    and not any(
                        lowered in a.name.lower() or lowered in (a.real_name or "").lower()
                        for a in b.authors
                    )
                ],
                q,
            )
            items = [
                Suggestion(
                    str(b.id),
                    b.title,
                    f"contains “{stories[b.id]}”"
                    if b.id in stories
                    else ", ".join(a.name for a in b.authors),
                )
                for b in books
            ]
        elif kind == "authors":
            items = [
                Suggestion(str(a.id), a.name, f"pen name of {a.real_name}" if a.real_name else "")
                for a in await service.search_authors(db, q, LIMIT)
            ]
        elif kind == "stories":  # spec 009: a story already in another book
            items = [
                Suggestion(
                    str(s.id),
                    s.title,
                    (
                        f"#{format_series_number(s.series_number)} {s.series.name} · in "
                        if s.series and s.series_number is not None
                        else "in "  # spec 019: no series
                    )
                    + ", ".join(ref.title for ref in s.books),
                )
                for s in await service.search_stories(db, q, LIMIT)
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
