"""Server-side sessions (research R1).

The browser holds an opaque random token; the database stores only its SHA-256 hash.
A session is valid while it hasn't expired and its user is active. Each use slides the
expiry forward, written at most once a minute.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.models import Account
from book_tracker.persistence import accounts

SESSION_COOKIE = "__Host-session"
DEFAULT_IDLE_DAYS = 14
TOUCH_INTERVAL = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class ResolvedSession:
    session_id: uuid.UUID
    account: Account
    csrf_token: str


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession, user_id: uuid.UUID, now: datetime, idle_days: int = DEFAULT_IDLE_DAYS
) -> tuple[str, str]:
    """Return ``(token, csrf_token)``; only the token's hash is stored."""
    token = new_token()
    csrf_token = secrets.token_urlsafe(32)
    await accounts.insert_session(
        db,
        user_id=user_id,
        token_hash=hash_token(token),
        csrf_token=csrf_token,
        now=now,
        expires_at=now + timedelta(days=idle_days),
    )
    return token, csrf_token


async def resolve_session(
    db: AsyncSession, token: str, now: datetime, idle_days: int = DEFAULT_IDLE_DAYS
) -> ResolvedSession | None:
    if not token:
        return None
    found = await accounts.find_session(db, hash_token(token))
    if found is None:
        return None
    row, account = found
    if row.expires_at <= now or not account.is_active:
        return None
    if now - row.last_seen_at >= TOUCH_INTERVAL:
        await accounts.touch_session(db, row.id, now, now + timedelta(days=idle_days))
    return ResolvedSession(session_id=row.id, account=account, csrf_token=row.csrf_token)


async def revoke(db: AsyncSession, token: str) -> None:
    await accounts.delete_session(db, hash_token(token))


async def revoke_all(
    db: AsyncSession, user_id: uuid.UUID, keep_session_id: uuid.UUID | None = None
) -> None:
    await accounts.delete_user_sessions(db, user_id, keep_session_id)
