"""Structured logging that never records secrets or personal notes (research R19)."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import Any

from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from book_tracker.web.routes.health import HEALTH_PATH

REDACTED = "[REDACTED]"
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "csrf_token",
        "notes",
        "cookie",
        "set-cookie",
        "authorization",
        "secret_key",
        "password_hash",
        "current_password",
        "new_password",
        "temporary_password",
        "initial_password",
    }
)

_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
}

request_logger = logging.getLogger("book_tracker.request")


def _is_sensitive(key: str) -> bool:
    return key.lower() in SENSITIVE_KEYS


def redact(value: Any) -> Any:
    """Return a copy of ``value`` with sensitive keys replaced, at any depth."""
    if isinstance(value, Mapping):
        return {
            k: (REDACTED if isinstance(k, str) and _is_sensitive(k) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact(v) for v in value)
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, Mapping):
            record.args = redact(record.args)
        elif isinstance(record.args, tuple):
            record.args = redact(record.args)
        for key in list(vars(record)):
            if key in _STANDARD_ATTRS:
                continue
            if _is_sensitive(key):
                setattr(record, key, REDACTED)
            else:
                setattr(record, key, redact(getattr(record, key)))
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger("book_tracker")
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(level)


def _route_template(scope: Scope) -> str:
    """The matched route's path template, e.g. ``/entries/{entry_id}``; never the raw path.

    Routing records the matched route in ``scope["route"]`` (including routes from included
    routers); for unmatched requests fall back to scanning the top-level routes.
    """
    route = scope.get("route")
    template = getattr(route, "path_format", None) or getattr(route, "path", None)
    regex = getattr(route, "path_regex", None)
    if isinstance(template, str) and template and regex is not None:
        # An included router's route doesn't carry the outer prefix (e.g. /api/v1); recover
        # it as the part of the path in front of what the route's own pattern matches.
        path = str(scope.get("path", ""))
        for start in range(len(path)):
            if path[start] == "/" and regex.fullmatch(path[start:]):
                return path[:start] + template
        return template
    app = scope.get("app")
    for candidate in getattr(getattr(app, "router", None), "routes", []):
        match, _ = candidate.matches(scope)
        if match == Match.FULL and isinstance(getattr(candidate, "path", None), str):
            return str(candidate.path)
    return "<unmatched>"


class RequestLogMiddleware:
    """Logs method, matched route template, status and duration; never the raw path."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Successful health checks arrive every 30 seconds; log only failures.
            if not (scope["path"] == HEALTH_PATH and status == 200):
                request_logger.info(
                    "request",
                    extra={
                        "method": scope["method"],
                        "route": _route_template(scope),
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    },
                )
