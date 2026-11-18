"""Request guards: session, CSRF, Admin and forced password change (research R1, R4, R13).

The same guards serve the JSON API and the pages; ``api/errors.py`` turns their errors into
problem responses for ``/api/`` paths and redirects or HTML pages for everything else.
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated

from fastapi import Depends, Request

from book_tracker.auth.sessions import SESSION_COOKIE, resolve_session
from book_tracker.domain.models import Account
from book_tracker.persistence.db import DbSession
from book_tracker.services.errors import (
    CsrfFailed,
    NotAdmin,
    NotAuthenticated,
    PasswordChangeRequired,
)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
FORM_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


@dataclass(frozen=True, slots=True)
class Authenticated:
    account: Account
    session_id: uuid.UUID
    csrf_token: str
    session_token: str


def now(request: Request) -> datetime:
    clock = request.app.state.clock
    value: datetime = clock()
    return value


def today(request: Request) -> date:
    """Today's date in the server's time zone, matching the "not in the future" check."""
    return now(request).astimezone().date()


async def supplied_csrf_token(request: Request) -> str | None:
    """CSRF token from the ``X-CSRF-Token`` header, or a ``csrf_token`` form field."""
    header = request.headers.get("x-csrf-token")
    if header:
        return header
    if request.headers.get("content-type", "").startswith(FORM_TYPES):
        form = await request.form()
        value = form.get("csrf_token")
        return value if isinstance(value, str) else None
    return None


async def authenticated_any_password(request: Request, db: DbSession) -> Authenticated:
    """A valid session, with CSRF checked on unsafe methods. Allows a pending password change."""
    token = request.cookies.get(SESSION_COOKIE, "")
    resolved = await resolve_session(
        db, token, now(request), request.app.state.settings.session_idle_days
    )
    if resolved is None:
        raise NotAuthenticated()
    if resolved.refreshed:
        # The server slid the expiry forward; refresh_session_cookie() resends the cookie.
        request.state.refresh_session_token = token
    if request.method not in SAFE_METHODS:
        supplied = await supplied_csrf_token(request)
        if not supplied or not hmac.compare_digest(supplied, resolved.csrf_token):
            raise CsrfFailed()
    return Authenticated(
        account=resolved.account,
        session_id=resolved.session_id,
        csrf_token=resolved.csrf_token,
        session_token=token,
    )


async def authenticated(
    auth: Annotated[Authenticated, Depends(authenticated_any_password)],
) -> Authenticated:
    if auth.account.must_change_password:
        raise PasswordChangeRequired()
    return auth


async def admin(auth: Annotated[Authenticated, Depends(authenticated)]) -> Authenticated:
    if not auth.account.is_admin:
        raise NotAdmin()
    return auth


ApiUser = Annotated[Authenticated, Depends(authenticated)]
ApiUserAnyPassword = Annotated[Authenticated, Depends(authenticated_any_password)]
ApiAdmin = Annotated[Authenticated, Depends(admin)]

# Pages use the same guards; only the error presentation differs (see api/errors.py).
UiUser = ApiUser
UiUserAnyPassword = ApiUserAnyPassword
UiAdmin = ApiAdmin
