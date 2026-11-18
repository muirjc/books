"""Security headers on every response; HTTPS only in production (Constitution Principle IX).

The Content-Security-Policy allows only same-origin resources, so pages use no inline
scripts or styles. In production, plain-HTTP requests are redirected to HTTPS and
responses carry HSTS. Behind a TLS-terminating proxy, uvicorn's ``--proxy-headers``
sets the request scheme from ``X-Forwarded-Proto``.
"""

from __future__ import annotations

from starlette.datastructures import URL, MutableHeaders
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = "default-src 'self'; frame-ancestors 'none'"
HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, production: bool) -> None:
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self.production and scope.get("scheme") == "http":
            url = URL(scope=scope).replace(scheme="https")
            await RedirectResponse(str(url), status_code=308)(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("Content-Security-Policy", CSP)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "same-origin")
                if self.production:
                    headers.setdefault("Strict-Transport-Security", HSTS)
            await send(message)

        await self.app(scope, receive, send_with_headers)
