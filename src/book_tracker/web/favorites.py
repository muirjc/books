"""Spec 017: favorite author shortcuts — where a favorite change may return to, the notice
the page shows afterwards, and the offer after finishing a book. See
specs/017-favorite-author-shortcuts/research.md R2 and R4."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qsl, urlencode

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from book_tracker.auth.dependencies import Authenticated
from book_tracker.domain.models import Author, BookAuthor
from book_tracker.persistence import catalog
from book_tracker.persistence.favorites import FavoriteAuthorRepository
from book_tracker.persistence.readings import ReadingEntryRepository
from book_tracker.schemas.catalog import FavoriteNoticeQuery
from book_tracker.services import authors as authors_service

Kind = Literal["favorited", "unfavorited"]
ANCHOR = "favorite-notice"
# One-time notices a page shows from its address; never carried back. ``finished`` and
# ``after`` stay: they say which offer, and which Add another page, this is.
DROPPED_KEYS = ("msg", "added", "stories", "wanted", "already", "favorited", "unfavorited")
# A warning the member may not have read yet stays (PR #42 review).
KEPT_MESSAGES = ("stories_not_added",)
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
# The author page isn't here: it reads ``msg``, so it gets the spec 011 address (the
# fallback) and its own notice (PR #42 review).
_BACK = re.compile(
    rf"/(?:(?:books|series)/{_UUID}|entries/(?P<entry>{_UUID})|books/add)?"
    r"(?:\?[A-Za-z0-9._~%&=+\-]*)?"
)


async def after_favorite(
    db: AsyncSession, auth: Authenticated, author_id: uuid.UUID, back: str | None, kind: Kind
) -> str:
    """Where a favorite change returns to: ``back`` when it's an accepted page (R2), with
    the notice, else the author page as before (spec 011)."""
    match = _BACK.fullmatch(back) if back and "//" not in back else None
    if match and match["entry"]:
        mine = await ReadingEntryRepository(db, auth.account.id).get(uuid.UUID(match["entry"]))
        if mine is None:  # another member's or unknown: alike (Principle I)
            match = None
    if back is None or match is None:
        return f"/authors/{author_id}?msg={kind}"
    path, _, query = back.partition("?")
    kept = [
        (k, v)
        for k, v in parse_qsl(query, keep_blank_values=True)
        if k not in DROPPED_KEYS or (k == "msg" and v in KEPT_MESSAGES)
    ]
    kept.append((kind, str(author_id)))
    return f"{path}?{urlencode(kept)}#{ANCHOR}"


def _keys(request: Request) -> FavoriteNoticeQuery:
    params = request.query_params
    return FavoriteNoticeQuery.model_validate(
        {k: params[k] for k in ("finished", "favorited", "unfavorited") if k in params}
    )


def page_back(request: Request) -> str:
    """This page's path and query, re-encoded so the route accepts it (a browser leaves
    characters such as ``,`` unencoded; PR #42 review). One-time keys are dropped by
    ``after_favorite``."""
    query = urlencode(request.query_params.multi_items())
    return request.url.path + (f"?{query}" if query else "")


async def notice(
    request: Request, db: AsyncSession, auth: Authenticated
) -> tuple[Kind, Author] | None:
    """``favorited=<author>`` or ``unfavorited=<author>``, for an author that exists and is
    (or isn't) my favorite now, so an old or hand-made address can't claim otherwise."""
    keys = _keys(request)
    mine = FavoriteAuthorRepository(db, auth.account.id)
    for kind, author_id, now in (("favorited", keys.favorited, True),
                                 ("unfavorited", keys.unfavorited, False)):  # fmt: skip
        if author_id is not None and await mine.has(author_id) == now:
            author = await catalog.get_author(db, author_id)
            if author is not None:
                return kind, author  # type: ignore[return-value]  # the loop's literal kinds
    return None


@dataclass(frozen=True, slots=True)
class Offer:
    authors: tuple[tuple[BookAuthor, int], ...]
    back: str  # this page, for the offer's buttons


async def offer(request: Request, db: AsyncSession, auth: Authenticated) -> Offer | None:
    """``finished=<book>``: the authors to offer, worked out now from my own entries and
    favorites (R4), or None."""
    book_id = _keys(request).finished
    if book_id is None:
        return None
    authors = await authors_service.finish_offers(db, auth.account.id, book_id)
    if not authors:
        return None
    return Offer(tuple(authors), page_back(request))
