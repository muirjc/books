"""Per-login sign-in throttling (FR-027; research R3).

After 5 consecutive wrong passwords for a login, sign-in for that login is refused for
15 minutes, even with the correct password. Logins that match no account are treated the
same way. Attempts during a lock are refused without being counted. The table is keyed by
an HMAC of the normalized login, so attempted logins are never stored as text.
"""

from __future__ import annotations

import hashlib
import hmac
import math
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.persistence.models import LoginThrottle

MAX_FAILURES = 5
LOCK_DURATION = timedelta(minutes=15)
PRUNE_AFTER = timedelta(hours=24)


class Clock(Protocol):
    def __call__(self) -> datetime: ...


def login_key(secret: str, login: str) -> str:
    normalized = login.strip().lower()
    return hmac.new(secret.encode(), normalized.encode(), hashlib.sha256).hexdigest()


async def serialize(db: AsyncSession, key: str) -> None:
    """Hold a per-login lock for the rest of the transaction.

    Without it, parallel attempts could all pass ``check_allowed`` before any failure is
    recorded, allowing more than five guesses per lock window.
    """
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


async def check_allowed(db: AsyncSession, key: str, now: datetime) -> int | None:
    """Seconds until sign-in is allowed again, or ``None`` when it is allowed now."""
    locked_until = await db.scalar(
        select(LoginThrottle.locked_until).where(LoginThrottle.login_key == key)
    )
    if locked_until is not None and locked_until > now:
        return max(1, math.ceil((locked_until - now).total_seconds()))
    return None


async def record_failure(db: AsyncSession, key: str, now: datetime) -> None:
    upsert = insert(LoginThrottle).values(
        login_key=key, failed_count=1, locked_until=None, updated_at=now
    )
    statement = upsert.on_conflict_do_update(
        index_elements=[LoginThrottle.login_key],
        set_={"failed_count": LoginThrottle.failed_count + 1, "updated_at": now},
    ).returning(LoginThrottle.failed_count)
    count = (await db.execute(statement)).scalar_one()
    if count >= MAX_FAILURES:
        await db.execute(
            update(LoginThrottle)
            .where(LoginThrottle.login_key == key)
            .values(failed_count=0, locked_until=now + LOCK_DURATION, updated_at=now)
        )


async def record_success(db: AsyncSession, key: str) -> None:
    await db.execute(delete(LoginThrottle).where(LoginThrottle.login_key == key))


async def prune(db: AsyncSession, now: datetime) -> None:
    await db.execute(delete(LoginThrottle).where(LoginThrottle.updated_at < now - PRUNE_AFTER))
