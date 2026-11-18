"""Sign-in and sign-out, shared by the JSON API and the sign-in page (FR-001, FR-002, FR-027)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.auth import sessions, throttle
from book_tracker.auth.passwords import (
    DUMMY_HASH,
    hash_password,
    needs_rehash,
    verify_password,
)
from book_tracker.domain.models import Account
from book_tracker.persistence import accounts
from book_tracker.services.errors import InvalidCredentials, TooManyAttempts


@dataclass(frozen=True, slots=True)
class SignedIn:
    account: Account
    token: str
    csrf_token: str


async def sign_in(
    db: AsyncSession, login: str, password: str, now: datetime, idle_days: int, secret: str
) -> SignedIn:
    """Wrong login, wrong password and deactivated accounts all raise ``InvalidCredentials``.

    Five consecutive failures for a login lock it for 15 minutes (``TooManyAttempts``).
    """
    key = throttle.login_key(secret, login)
    await throttle.prune(db, now)
    retry_after = await throttle.check_allowed(db, key, now)
    if retry_after is not None:
        raise TooManyAttempts(retry_after)
    account = await accounts.get_user_by_login(db, login)
    if account is None:
        verify_password(DUMMY_HASH, password)  # equalize timing for unknown logins
        valid = False
    else:
        valid = verify_password(account.password_hash, password) and account.is_active
    if account is None or not valid:
        await throttle.record_failure(db, key, now)
        await db.commit()  # keep the count even though this request fails
        raise InvalidCredentials()
    await throttle.record_success(db, key)
    if needs_rehash(account.password_hash):
        account = await accounts.update_user(db, account.id, password_hash=hash_password(password))
    token, csrf_token = await sessions.create_session(db, account.id, now, idle_days)
    return SignedIn(account=account, token=token, csrf_token=csrf_token)


async def sign_out(db: AsyncSession, token: str) -> None:
    await sessions.revoke(db, token)
