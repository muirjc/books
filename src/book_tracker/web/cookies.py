"""Cookie helpers. Every cookie is Secure, HttpOnly and SameSite=Lax (Principle IX)."""

from __future__ import annotations

import uuid
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from book_tracker.auth.csrf import PRESESSION_COOKIE, PRESESSION_MAX_AGE
from book_tracker.auth.sessions import SESSION_COOKIE


def set_session_cookie(response: Response, token: str, idle_days: int) -> None:
    # __Host- prefix: Secure, Path=/, no Domain.
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=idle_days * 86400,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


def set_presession_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        PRESESSION_COOKIE,
        token,
        max_age=PRESESSION_MAX_AGE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


RECENT_PROFILES_COOKIE = "recent_profiles"
RECENT_PROFILES_MAX = 5
RECENT_PROFILES_MAX_AGE = 90 * 86400


def recent_profile_ids(request: Request) -> list[uuid.UUID]:
    """User ids remembered on this device, most recent first; junk values are ignored."""
    ids: list[uuid.UUID] = []
    for part in request.cookies.get(RECENT_PROFILES_COOKIE, "").strip('"').split("."):
        try:
            value = uuid.UUID(part)
        except ValueError:
            continue
        if value not in ids:
            ids.append(value)
    return ids[:RECENT_PROFILES_MAX]


def remember_profile(request: Request, response: Response, user_id: uuid.UUID) -> None:
    """Put ``user_id`` first in the device's recent-profiles cookie (FR-007, research R11)."""
    ids = [user_id] + [i for i in recent_profile_ids(request) if i != user_id]
    response.set_cookie(
        RECENT_PROFILES_COOKIE,
        ".".join(str(i) for i in ids[:RECENT_PROFILES_MAX]),
        max_age=RECENT_PROFILES_MAX_AGE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


async def refresh_session_cookie(request: Request, call_next: Any) -> Response:
    """Resend the session cookie when the server slid the session's expiry forward.

    Without this, the browser drops the cookie 14 days after sign-in even for daily users.
    Responses that already set or clear the cookie (sign-in, sign-out) are left alone.
    """
    response: Response = await call_next(request)
    token = getattr(request.state, "refresh_session_token", None)
    already = any(
        value.startswith(f"{SESSION_COOKIE}=".encode())
        for name, value in response.raw_headers
        if name == b"set-cookie"
    )
    if token and not already:
        set_session_cookie(response, token, request.app.state.settings.session_idle_days)
    return response
