"""Spec 015: the one-tap "Want to read" on catalog rows: where it may return to, and the
notice the page shows afterwards. See specs/015-rows-quick-add/research.md R2, R3."""

from __future__ import annotations

import re
import uuid
from urllib.parse import parse_qsl, urlencode

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from book_tracker.auth.dependencies import Authenticated
from book_tracker.domain.models import ReadingEntry
from book_tracker.services import readings as readings_service

NOTICE_KEYS = ("wanted", "already")
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_BACK = re.compile(
    rf"/(?:catalog|upcoming|authors/{_UUID}|series/{_UUID})(?:\?[A-Za-z0-9._~%&=+\-]*)?"
)


def after_quick_add(back: str, kind: str, book_id: uuid.UUID) -> str:
    """Where the quick add returns to: ``back`` if it's one of the four pages (R2), else
    the Catalog, with the notice and the row's anchor."""
    if not _BACK.fullmatch(back) or "//" in back:
        back = "/catalog"
    path, _, query = back.partition("?")
    kept = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k not in NOTICE_KEYS]
    kept.append((kind, str(book_id)))
    return f"{path}?{urlencode(kept)}#book-{book_id}"


async def notice(
    request: Request, db: AsyncSession, auth: Authenticated
) -> tuple[str, ReadingEntry] | None:
    """``wanted=<book>`` or ``already=<book>``, when that book is on my list (R3)."""
    for kind in NOTICE_KEYS:
        try:
            book_id = uuid.UUID(request.query_params.get(kind, ""))
        except ValueError:
            continue
        entry = await readings_service.entry_for_book(db, auth.account.id, book_id)
        if entry is not None:
            return kind, entry
    return None
