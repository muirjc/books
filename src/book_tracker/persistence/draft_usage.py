"""Each member's daily allowance of AI draft requests (spec 012 research R8), always
filtered by the bound user (Constitution Principle I).

As with ``ReadingEntryRepository``, the repository is created with the session user's id.
Every statement adds ``ai_draft_usage.user_id = <bound user>``, and no method takes a user
id from its caller.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.persistence import models

KEEP_DAYS = 30


class DraftUsageRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._db = session
        self._user_id = user_id

    def _mine(self) -> ColumnElement[bool]:
        return models.AiDraftUsage.user_id == self._user_id

    async def reserve(self, day: date, limit: int) -> int | None:
        """Count one request on ``day``; the new count, or None when the limit is reached.

        One statement, so concurrent requests can't pass the limit together.
        """
        await self._db.execute(
            delete(models.AiDraftUsage).where(
                self._mine(), models.AiDraftUsage.day < day - timedelta(days=KEEP_DAYS)
            )
        )
        usage = models.AiDraftUsage
        statement = pg_insert(usage).values(user_id=self._user_id, day=day, count=1)
        count: int | None = await self._db.scalar(
            statement.on_conflict_do_update(
                constraint="ai_draft_usage_pkey",
                set_={"count": usage.count + 1},
                where=(usage.count < limit) & self._mine(),
            ).returning(usage.count)
        )
        return count

    async def left(self, day: date, limit: int) -> int:
        used = await self._db.scalar(
            select(models.AiDraftUsage.count).where(self._mine(), models.AiDraftUsage.day == day)
        )
        return max(limit - (used or 0), 0)
