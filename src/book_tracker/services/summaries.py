"""Summaries: one current per book, shared by the family (FR-024, FR-025).

A save carrying the id of the app's own, current AI draft of this book is stored as ``ai``
or ``ai_edited`` with the draft's model and sources (spec 012 research R6). Every other
save is ``manual``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.drafts import origin_for
from book_tracker.domain.enums import SummaryOrigin
from book_tracker.domain.models import Summary
from book_tracker.persistence import catalog, drafts
from book_tracker.services.drafts import facts_for
from book_tracker.services.errors import NotFoundError, ValidationFailed

MAX_LENGTH = 5000


async def save_summary(
    db: AsyncSession,
    actor_id: uuid.UUID,
    book_id: uuid.UUID,
    text: str,
    *,
    draft_id: str | None = None,
    now: datetime,
) -> Summary:
    book = await catalog.get_book(db, book_id)
    if book is None:
        raise NotFoundError()
    cleaned = text.strip()
    if not cleaned or len(cleaned) > MAX_LENGTH:
        raise ValidationFailed.single("text", "Write a summary of 1 to 5,000 characters")
    draft = await drafts.get(db, draft_id) if draft_id else None
    origin = origin_for(draft, facts_for(book).key, cleaned, now)
    if draft is None or origin == SummaryOrigin.MANUAL.value:
        return await catalog.save_summary(
            db, book_id, cleaned, SummaryOrigin.MANUAL.value, actor_id
        )
    return await catalog.save_summary(
        db, book_id, cleaned, origin, actor_id, model=draft.model, source_urls=draft.source_urls
    )


async def history(db: AsyncSession, book_id: uuid.UUID) -> list[Summary]:
    """All summaries for the book, newest first."""
    if not await catalog.book_exists(db, book_id):
        raise NotFoundError()
    return await catalog.list_summaries(db, book_id)
