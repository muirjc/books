"""Unauthenticated ``GET /healthz`` for the container health check (spec section 10.4)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from book_tracker.main import create_app
from book_tracker.settings import Settings


async def test_healthz_ok_without_signing_in(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers


async def test_healthz_not_in_openapi(app: Any) -> None:
    assert not any(path.endswith("/healthz") for path in app.openapi()["paths"])


@pytest.fixture
async def production(settings: Settings, app: Any) -> AsyncIterator[Any]:
    prod = create_app(settings.model_copy(update={"environment": "production"}))
    yield prod
    await prod.state.db.engine.dispose()


async def test_healthz_answers_plain_http_in_production(production: Any) -> None:
    """The Docker health check calls the app directly over HTTP, not through Caddy."""
    transport = httpx.ASGITransport(app=production)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as plain:
        response = await plain.get("/healthz")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        # Every other path still redirects.
        assert (await plain.get("/sign-in")).status_code == 308


@pytest.fixture
async def broken_db(settings: Settings, app: Any) -> AsyncIterator[Any]:
    url = settings.database_url.rsplit("/", 1)[0] + "/no_such_database"
    broken = create_app(settings.model_copy(update={"database_url": url}))
    yield broken
    await broken.state.db.engine.dispose()


async def test_healthz_503_when_database_unreachable(
    broken_db: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="book_tracker")
    transport = httpx.ASGITransport(app=broken_db)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as c:
        response = await c.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "no_such_database" not in response.text
    # A failing check is logged, so the cause can be found.
    assert any(r.name == "book_tracker.request" and r.status == 503 for r in caplog.records)  # type: ignore[attr-defined]  # set via extra=


async def test_successful_healthz_not_request_logged(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A check every 30 seconds would drown the request log."""
    caplog.set_level(logging.INFO, logger="book_tracker.request")
    await client.get("/healthz")
    await client.get("/sign-in")
    routes = [r.route for r in caplog.records if r.name == "book_tracker.request"]  # type: ignore[attr-defined]  # set via extra=
    assert routes == ["/sign-in"]
