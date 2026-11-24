"""The Author page and favorite authors (spec 011). Edit author stays under /catalog."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response

from book_tracker.auth.dependencies import UiUser
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import FavoriteForm
from book_tracker.services import authors as service
from book_tracker.web import quick
from book_tracker.web.rendering import render, render_error

router = APIRouter(prefix="/authors", include_in_schema=False)

MESSAGES = {
    "favorited": "Added to your favorite authors.",
    "unfavorited": "Removed from your favorite authors.",
}


@router.get("/favorites")
async def favorite_authors(request: Request, auth: UiUser, db: DbSession) -> Response:
    """My favorite authors, by sort name (AC-12)."""
    authors = await service.favorite_authors(db, auth.account.id)
    return render(request, "pages/favorite_authors.html", {"authors": authors}, auth=auth)


@router.get("/{author_id}")
async def author_page(
    author_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    view = await service.author_view(db, auth.account.id, author_id)  # 404 if unknown
    return render(
        request,
        "pages/author.html",
        {
            "view": view,
            "message": MESSAGES.get(request.query_params.get("msg", "")),
            "quick": await quick.notice(request, db, auth),  # spec 015
        },
        auth=auth,
    )


@router.post("/{author_id}/favorite")
async def set_favorite(
    author_id: uuid.UUID, request: Request, auth: UiUser, db: DbSession
) -> Response:
    """Add (favorite=yes) or remove (no), then back to the page (research R5)."""
    try:
        form = FavoriteForm.model_validate({"favorite": (await request.form()).get("favorite")})
    except ValidationError:
        return render_error(request, 422, "Choose whether to add or remove the favorite")
    if form.favorite == "yes":
        await service.add_favorite(db, auth.account.id, author_id)
        msg = "favorited"
    else:
        await service.remove_favorite(db, auth.account.id, author_id)
        msg = "unfavorited"
    return RedirectResponse(f"/authors/{author_id}?msg={msg}", status_code=303)
