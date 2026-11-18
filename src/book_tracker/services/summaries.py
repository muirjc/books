"""Hand-written summaries: one current per book, shared by the family (FR-024, FR-025).

AI-drafted summaries (spec 002) will add ``origin`` values ``ai`` / ``ai_edited`` with a
model and sources; this feature only writes ``manual``.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.enums import SummaryOrigin
from book_tracker.domain.models import Summary
from book_tracker.persistence import catalog
from book_tracker.services.errors import NotFoundError, ValidationFailed

MAX_LENGTH = 5000


async def save_manual_summary(
    db: AsyncSession, actor_id: uuid.UUID, book_id: uuid.UUID, text: str
) -> Summary:
    if not await catalog.book_exists(db, book_id):
        raise NotFoundError()
    cleaned = text.strip()
    if not cleaned or len(cleaned) > MAX_LENGTH:
        raise ValidationFailed.single("text", "Write a summary of 1 to 5,000 characters")
    return await catalog.save_summary(db, book_id, cleaned, SummaryOrigin.MANUAL.value, actor_id)


async def history(db: AsyncSession, book_id: uuid.UUID) -> list[Summary]:
    """All summaries for the book, newest first."""
    if not await catalog.book_exists(db, book_id):
        raise NotFoundError()
    return await catalog.list_summaries(db, book_id)
