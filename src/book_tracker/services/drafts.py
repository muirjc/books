"""AI summary drafts (spec 012 research R6, R8, R9): one use case for the pages and the API.

A draft is never stored in the catalog. Only ``services.summaries.save_summary`` with the
draft's id turns it into a summary, as ``ai`` or ``ai_edited`` (Principle III).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain import models as domain
from book_tracker.domain.drafts import (
    WORDS_MAX,
    WORDS_MIN,
    BookDescription,
    BookFacts,
    CachedDraft,
    DraftView,
    GeneratedDraft,
    copies_source,
    is_blocked,
    keep_sources,
    word_count,
)
from book_tracker.domain.values import parse_series_number
from book_tracker.persistence import drafts, source_cache
from book_tracker.persistence.draft_usage import DraftUsageRepository
from book_tracker.services.errors import (
    AiNotConfigured,
    DraftLimitReached,
    DraftRejected,
    NotEnoughInformation,
    SourceUnavailable,
)
from book_tracker.sources.base import BookSource
from book_tracker.sources.summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)


def facts_for(book: domain.Book) -> BookFacts:
    """The book data the AI may see: catalog fields only (Principle IX)."""
    return BookFacts(
        title=book.title,
        authors=tuple(a.name for a in sorted(book.authors, key=lambda a: a.position)),
        series_name=book.series.name if book.series else None,
        series_number=book.series_number,
        isbn13=book.isbn_13,
        release_year=book.release_date.year if book.release_date else None,
    )


def _view(draft: CachedDraft, *, cached: bool, left: int) -> DraftView:
    return DraftView(
        id=draft.id,
        text=draft.text,
        source_urls=draft.source_urls,
        model=draft.model,
        series_name=draft.series_name,
        series_number=draft.series_number,
        cached=cached,
        created_at=draft.created_at,
        drafts_left=left,
    )


async def get_draft(db: AsyncSession, draft_id: str) -> CachedDraft | None:
    return await drafts.get(db, draft_id)


async def drafts_left(db: AsyncSession, user_id: uuid.UUID, today: date, limit: int) -> int:
    return await DraftUsageRepository(db, user_id).left(today, limit)


async def _description(
    db: AsyncSession, source: BookSource, facts: BookFacts, now: datetime
) -> BookDescription | None:
    """Open Library's description, cached a day; Open Library down is not a failure (R3)."""
    cached = await source_cache.get_description(db, facts.key, now)
    if cached is not None:
        return cached.value
    try:
        found = await source.describe_book(facts.title, facts.authors, facts.isbn13)
    except SourceUnavailable:
        logger.info("ai draft: open library unavailable; drafting without its description")
        return None
    await source_cache.put_description(db, facts.key, found, now)
    return found


def _checked(generated: GeneratedDraft, description: BookDescription | None) -> tuple[str, ...]:
    """The sources to record, or an error when the draft fails a check (R4, R5)."""
    if generated.status == "not_enough_information":
        raise NotEnoughInformation()
    if any(is_blocked(u) for u in (*generated.source_urls, *generated.cited_urls)):
        logger.info("ai draft: rejected, cites a blocked site")
        raise DraftRejected()
    words = word_count(generated.text)
    if not WORDS_MIN <= words <= WORDS_MAX:
        logger.info("ai draft: rejected, %d words", words)
        raise DraftRejected()
    if copies_source(generated.text, description.description if description else None):
        logger.info("ai draft: rejected, copies the description")
        raise DraftRejected()
    sources = keep_sources(generated.source_urls, generated.known_urls, generated.cited_urls)
    if not sources and description is None:
        raise NotEnoughInformation()  # a draft must be based on something
    return sources


def _series_number(raw: str | None) -> Decimal | None:
    """The suggested number, or None when there is none or it can't be read (AC-19)."""
    if raw is None:
        return None
    try:
        return parse_series_number(raw.lstrip("#"))
    except ValueError:
        return None


async def request_draft(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    facts: BookFacts,
    regenerate: bool,
    source: BookSource,
    generator: SummaryGenerator,
    now: datetime,
    today: date,
    limit: int,
) -> DraftView:
    """A draft for the book: the cached one unless regenerating, else a new one (R9)."""
    usage = DraftUsageRepository(db, user_id)
    if not regenerate:
        cached = await drafts.newest(db, facts.key, now)
        if cached is not None:
            return _view(cached, cached=True, left=await usage.left(today, limit))
    if not generator.configured:
        raise AiNotConfigured()  # before the allowance: nothing was asked (AC-10)
    if await usage.reserve(today, limit) is None:
        raise DraftLimitReached(limit)
    await db.commit()  # the request counts even if the AI then fails (AC-10)
    description = await _description(db, source, facts, now)
    await db.commit()  # no transaction stays open while the AI works
    generated = await generator.draft(facts, description)
    sources = _checked(generated, description)
    stored = await drafts.add(
        db,
        draft_key=facts.key,
        text=generated.text,
        source_urls=sources,
        model=generated.model,
        series_name=generated.series_name[:200] if generated.series_name else None,
        series_number=_series_number(generated.series_number),
        now=now,
    )
    await db.commit()
    logger.info("ai draft: stored (%d sources)", len(sources))
    return _view(stored, cached=False, left=await usage.left(today, limit))
