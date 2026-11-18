"""T109: security headers, and HTTPS only in production (Constitution Principle IX)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from book_tracker.main import create_app
from book_tracker.settings import Settings

CSP = "default-src 'self'; frame-ancestors 'none'"


async def test_html_responses_have_security_headers(client: httpx.AsyncClient) -> None:
    for path in ("/sign-in", "/no-such-page", "/static/css/app.css"):
        response = await client.get(path)
        assert response.headers["content-security-policy"] == CSP, path
        assert response.headers["x-content-type-options"] == "nosniff", path
        assert response.headers["referrer-policy"] == "same-origin", path
    api = await client.get("/api/v1/me")
    assert api.headers["x-content-type-options"] == "nosniff"
    assert "strict-transport-security" not in (await client.get("/sign-in")).headers


@pytest.fixture
async def production(settings: Settings, app: Any) -> AsyncIterator[Any]:
    prod = create_app(settings.model_copy(update={"environment": "production"}))
    yield prod
    await prod.state.db.engine.dispose()


async def test_production_redirects_http_and_sets_hsts(production: Any) -> None:
    transport = httpx.ASGITransport(app=production)
    async with httpx.AsyncClient(transport=transport, base_url="http://books.example") as plain:
        response = await plain.get("/sign-in?next=1")
        assert response.status_code == 308
        assert response.headers["location"] == "https://books.example/sign-in?next=1"
    async with httpx.AsyncClient(transport=transport, base_url="https://books.example") as tls:
        response = await tls.get("/sign-in")
        assert response.status_code == 200
        assert response.headers["strict-transport-security"] == (
            "max-age=31536000; includeSubDomains"
        )
