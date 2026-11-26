"""The Authors page (spec 018), the Author page and favorite authors (spec 011). Edit author
stays under /catalog."""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response

from book_tracker.auth.dependencies import UiUser
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.catalog import AuthorsQuery, FavoriteForm
from book_tracker.services import authors as service
from book_tracker.services import catalog as catalog_service
from book_tracker.web import favorites, quick
from book_tracker.web.rendering import is_htmx, render, render_error
from book_tracker.web.routes.readings import PAGE_SIZE

router = APIRouter(prefix="/authors", include_in_schema=False)

MESSAGES = {
    "favorited": "Added to your favorite authors.",
    "unfavorited": "Removed from your favorite authors.",
}


@router.get("")
async def authors_page(request: Request, auth: UiUser, db: DbSession) -> Response:
    """Every catalog author, searched, filtered to my favorites and paged; HTMX gets just
    the list (spec 018 R2). The query is validated by ``AuthorsQuery``; bad values fall
    back to the defaults."""
    params = request.query_params
    query = AuthorsQuery.model_validate(
        {name: params[name] for name in AuthorsQuery.model_fields if name in params}
    )
    index = await service.authors_index(
        db,
        auth.account.id,
        page=query.page,
        page_size=PAGE_SIZE,
        q=query.q,
        only_favorites=query.favorites,
    )
    kept = {"q": query.q, "favorites": "1" if query.favorites else ""}
    encoded = urlencode({k: v for k, v in kept.items() if v})
    context: dict[str, Any] = {
        "index": index,
        "filters": kept,
        "query_without_page": f"{encoded}&" if encoded else "",
        "clear_search": "/authors?favorites=1" if query.favorites else "/authors",
        "favorite_back": favorites.page_back(request),
        "favorite_notice": await favorites.notice(request, db, auth),
        "htmx": is_htmx(request),
    }
    if context["htmx"]:
        return render(request, "partials/authors_list.html", context, auth=auth)
    context["unused_authors"] = await catalog_service.unused_author_count(db)  # spec 008
    return render(request, "pages/authors.html", context, auth=auth)


@router.get("/favorites")
async def favorite_authors() -> Response:
    """Spec 018 AC-07: the old My favorite authors page is the Authors page's Favorites
    only."""
    return RedirectResponse("/authors?favorites=1", status_code=302)


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
    """Add (favorite=yes) or remove (no), then back to the page (research R5), or to an
    accepted ``back`` page (spec 017 R2)."""
    data = await request.form()
    try:
        form = FavoriteForm.model_validate(
            {"favorite": data.get("favorite"), "back": data.get("back")}
        )
    except ValidationError:
        return render_error(request, 422, "Choose whether to add or remove the favorite")
    kind: favorites.Kind
    if form.favorite == "yes":
        await service.add_favorite(db, auth.account.id, author_id)
        kind = "favorited"
    else:
        await service.remove_favorite(db, auth.account.id, author_id)
        kind = "unfavorited"
    location = await favorites.after_favorite(db, auth, author_id, form.back, kind)
    return RedirectResponse(location, status_code=303)
