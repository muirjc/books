"""T017: server-side sessions (research R1); covers all of auth/sessions.py."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from book_tracker.auth import sessions
from book_tracker.persistence import models
from tests.conftest import Factory

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


async def test_create_stores_only_hash(app: Any, factory: Factory) -> None:
    user = await factory.user()
    async with app.state.db.sessionmaker() as db:
        token, csrf = await sessions.create_session(db, user.id, NOW)
        await db.commit()
        row = (await db.execute(select(models.UserSession))).scalar_one()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.token_hash
    assert row.csrf_token == csrf
    assert row.expires_at == NOW + timedelta(days=14)


async def test_resolve_valid_and_unknown(app: Any, factory: Factory) -> None:
    user = await factory.user()
    async with app.state.db.sessionmaker() as db:
        token, csrf = await sessions.create_session(db, user.id, NOW)
        resolved = await sessions.resolve_session(db, token, NOW + timedelta(hours=1))
        assert resolved is not None
        assert resolved.account.id == user.id
        assert resolved.csrf_token == csrf
        assert await sessions.resolve_session(db, "unknown-token", NOW) is None
        assert await sessions.resolve_session(db, "", NOW) is None


async def test_expires_after_14_idle_days(app: Any, factory: Factory) -> None:
    user = await factory.user()
    async with app.state.db.sessionmaker() as db:
        token, _ = await sessions.create_session(db, user.id, NOW)
        assert await sessions.resolve_session(db, token, NOW + timedelta(days=13)) is not None
        # Use on day 13 slid the expiry forward, so day 26 is still valid ...
        assert await sessions.resolve_session(db, token, NOW + timedelta(days=26)) is not None
        # ... but 15 idle days after the last use is not.
        assert (
            await sessions.resolve_session(db, token, NOW + timedelta(days=41, minutes=1)) is None
        )


async def test_last_seen_written_at_most_once_a_minute(app: Any, factory: Factory) -> None:
    user = await factory.user()
    async with app.state.db.sessionmaker() as db:
        token, _ = await sessions.create_session(db, user.id, NOW)
        await sessions.resolve_session(db, token, NOW + timedelta(seconds=30))
        row = (await db.execute(select(models.UserSession))).scalar_one()
        assert row.last_seen_at == NOW
        await sessions.resolve_session(db, token, NOW + timedelta(seconds=61))
        await db.refresh(row)
        assert row.last_seen_at == NOW + timedelta(seconds=61)


async def test_revoke_one_and_all(app: Any, factory: Factory) -> None:
    user = await factory.user()
    async with app.state.db.sessionmaker() as db:
        first, _ = await sessions.create_session(db, user.id, NOW)
        second, _ = await sessions.create_session(db, user.id, NOW)
        third, _ = await sessions.create_session(db, user.id, NOW)
        await sessions.revoke(db, first)
        assert await sessions.resolve_session(db, first, NOW) is None
        kept = await sessions.resolve_session(db, second, NOW)
        assert kept is not None
        await sessions.revoke_all(db, user.id, keep_session_id=kept.session_id)
        assert await sessions.resolve_session(db, second, NOW) is not None
        assert await sessions.resolve_session(db, third, NOW) is None
        await sessions.revoke_all(db, user.id)
        assert await sessions.resolve_session(db, second, NOW) is None


@pytest.mark.ac("001/AC-10")
async def test_deactivated_user_session_rejected(app: Any, factory: Factory) -> None:
    user = await factory.user(is_active=False)
    async with app.state.db.sessionmaker() as db:
        token, _ = await sessions.create_session(db, user.id, NOW)
        assert await sessions.resolve_session(db, token, NOW) is None


def test_hash_token_is_sha256_hex() -> None:
    assert sessions.hash_token("abc") == hashlib.sha256(b"abc").hexdigest()
    assert len(sessions.new_token()) >= 43
