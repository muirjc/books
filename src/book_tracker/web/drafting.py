"""Drafting from a page (spec 012): the Summary page and Add a book share this."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.auth.dependencies import Authenticated, now, today
from book_tracker.domain.drafts import BookFacts, DraftView
from book_tracker.services import drafts as drafts_service
from book_tracker.services.errors import (
    AiDeclined,
    AiNotConfigured,
    AiUnavailable,
    DraftLimitReached,
    DraftRejected,
    NotEnoughInformation,
)
from book_tracker.sources.base import BookSource
from book_tracker.sources.summary_generator import SummaryGenerator

DRAFT_FAILURES = (
    AiNotConfigured,
    AiUnavailable,
    AiDeclined,
    NotEnoughInformation,
    DraftRejected,
    DraftLimitReached,
)


async def draft_for_page(
    request: Request,
    auth: Authenticated,
    db: AsyncSession,
    facts: BookFacts,
    *,
    regenerate: bool,
    source: BookSource,
    generator: SummaryGenerator,
) -> tuple[DraftView | None, str | None, int]:
    """A draft, or the message saying why there is none (AC-09); and the drafts left today."""
    limit: int = request.app.state.settings.ai_daily_draft_limit
    try:
        view = await drafts_service.request_draft(
            db,
            user_id=auth.account.id,
            facts=facts,
            regenerate=regenerate,
            source=source,
            generator=generator,
            now=now(request),
            today=today(request),
            limit=limit,
            timeout_seconds=request.app.state.settings.ai_timeout_seconds,
        )
    except DRAFT_FAILURES as exc:
        left = await drafts_service.drafts_left(db, auth.account.id, today(request), limit)
        return None, exc.title, left
    return view, None, view.drafts_left
