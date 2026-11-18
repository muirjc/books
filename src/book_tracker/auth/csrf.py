"""Pre-session CSRF tokens for the sign-in form and API (research R4).

Before a session exists, the token is ``<issued-at>.<nonce>.<hmac>``, stored in a
short-lived cookie and echoed back in a header or form field.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

PRESESSION_COOKIE = "__Host-presession"
PRESESSION_MAX_AGE = 600  # seconds


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue(secret: str, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    payload = f"{issued}.{secrets.token_urlsafe(16)}"
    return f"{payload}.{_sign(secret, payload)}"


def verify(
    secret: str, cookie_token: str | None, supplied: str | None, now: float | None = None
) -> bool:
    """True when the supplied token equals the cookie and carries a fresh, valid signature."""
    if not cookie_token or not supplied or not hmac.compare_digest(cookie_token, supplied):
        return False
    try:
        issued_text, nonce, signature = supplied.split(".")
        issued = int(issued_text)
    except ValueError:
        return False
    current = now if now is not None else time.time()
    if not 0 <= current - issued <= PRESESSION_MAX_AGE:
        return False
    return hmac.compare_digest(signature, _sign(secret, f"{issued_text}.{nonce}"))
