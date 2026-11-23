"""The AI summary draft cache (spec 012 research R6): catalog data outside the catalog
tables, never read by any summary display. Rows hold no user ids."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.drafts import DRAFT_TTL, CachedDraft
from book_tracker.persistence import models


def _to_domain(row: models.SummaryDraft) -> CachedDraft:
    return CachedDraft(
        id=str(row.id),
        draft_key=row.draft_key,
        text=row.text,
        source_urls=tuple(str(u) for u in row.source_urls),
        model=row.model,
        series_name=row.series_name,
        series_number=row.series_number,
        created_at=row.created_at,
    )


async def add(
    db: AsyncSession,
    *,
    draft_key: str,
    text: str,
    source_urls: Sequence[str],
    model: str,
    series_name: str | None,
    series_number: Decimal | None,
    now: datetime,
) -> CachedDraft:
    """Store a new draft; older drafts for the key stay usable until they expire (R6)."""
    await prune(db, now)
    row = (
        await db.execute(
            insert(models.SummaryDraft)
            .values(
                id=uuid.uuid4(),
                draft_key=draft_key,
                text=text,
                source_urls=list(source_urls),
                model=model,
                series_name=series_name,
                series_number=series_number,
                created_at=now,
            )
            .returning(models.SummaryDraft)
        )
    ).scalar_one()
    return _to_domain(row)


async def newest(db: AsyncSession, draft_key: str, now: datetime) -> CachedDraft | None:
    row = await db.scalar(
        select(models.SummaryDraft)
        .where(
            models.SummaryDraft.draft_key == draft_key,
            models.SummaryDraft.created_at > now - DRAFT_TTL,
        )
        .order_by(models.SummaryDraft.created_at.desc())
        .limit(1)
    )
    return _to_domain(row) if row is not None else None


async def get(db: AsyncSession, draft_id: str) -> CachedDraft | None:
    try:
        key = uuid.UUID(draft_id)
    except ValueError:
        return None
    row = await db.get(models.SummaryDraft, key)
    return _to_domain(row) if row is not None else None


async def prune(db: AsyncSession, now: datetime) -> None:
    await db.execute(
        delete(models.SummaryDraft).where(models.SummaryDraft.created_at <= now - DRAFT_TTL)
    )
