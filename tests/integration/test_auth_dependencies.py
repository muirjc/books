"""T018: authentication, CSRF, Admin and password-change guards; covers auth/dependencies.py.

Uses a separate app instance with probe routes so the guards are tested without any
feature routes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import Form
from fastapi.responses import HTMLResponse

from book_tracker.auth.dependencies import (
    ApiAdmin,
    ApiUser,
    ApiUserAnyPassword,
    UiAdmin,
    UiUser,
)
from book_tracker.main import create_app
from book_tracker.settings import Settings
from tests.conftest import Factory, make_client, signed_in, ui_csrf


@pytest.fixture(scope="module")
def probe_app(settings: Settings) -> Any:
    probe = create_app(settings)

    @probe.get("/api/v1/_probe")
    async def api_get(user: ApiUser) -> dict[str, str]:
        return {"login": user.account.login}

    @probe.post("/api/v1/_probe")
    async def api_post(user: ApiUser) -> dict[str, str]:
        return {"login": user.account.login}

    @probe.patch("/api/v1/_probe")
    async def api_patch(user: ApiUser) -> dict[str, str]:
        return {"login": user.account.login}

    @probe.delete("/api/v1/_probe")
    async def api_delete(user: ApiUser) -> dict[str, str]:
        return {"login": user.account.login}

    @probe.get("/api/v1/_probe/any-password")
    async def api_any(user: ApiUserAnyPassword) -> dict[str, str]:
        return {"login": user.account.login}

    @probe.get("/api/v1/_probe/admin")
    async def api_admin(user: ApiAdmin) -> dict[str, str]:
        return {"login": user.account.login}

    @probe.get("/_probe-page")
    async def ui_get(user: UiUser) -> HTMLResponse:
        return HTMLResponse(f"<p>{user.account.login}</p>")

    @probe.post("/_probe-page")
    async def ui_post(user: UiUser, note: str = Form("")) -> HTMLResponse:
        return HTMLResponse(f"<p>{note}</p>")

    @probe.get("/_probe-page/admin")
    async def ui_admin(user: UiAdmin) -> HTMLResponse:
        return HTMLResponse("<p>admin</p>")

    return probe


@pytest.fixture
async def probe(probe_app: Any, app: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client(probe_app) as c:
        yield c


async def test_api_requires_session(probe: httpx.AsyncClient) -> None:
    response = await probe.get("/api/v1/_probe")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "not_authenticated"


async def test_ui_redirects_to_sign_in(probe: httpx.AsyncClient) -> None:
    response = await probe.get("/_probe-page")
    assert response.status_code == 303
    assert response.headers["location"] == "/sign-in"


async def test_htmx_gets_hx_redirect(probe: httpx.AsyncClient) -> None:
    response = await probe.get("/_probe-page", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers["hx-redirect"] == "/sign-in"


async def test_bad_session_cookie_is_unauthenticated(probe: httpx.AsyncClient) -> None:
    probe.cookies.set("__Host-session", "forged", domain="testserver")
    assert (await probe.get("/api/v1/_probe")).status_code == 401


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
async def test_csrf_required_on_unsafe_methods(
    probe: httpx.AsyncClient, factory: Factory, method: str
) -> None:
    user = await factory.user()
    await signed_in(probe, user)
    good = probe.headers.pop("X-CSRF-Token")
    missing = await probe.request(method, "/api/v1/_probe")
    assert missing.status_code == 403
    assert missing.json()["code"] == "csrf_failed"
    wrong = await probe.request(method, "/api/v1/_probe", headers={"X-CSRF-Token": "nope"})
    assert wrong.status_code == 403
    right = await probe.request(method, "/api/v1/_probe", headers={"X-CSRF-Token": good})
    assert right.status_code == 200


async def test_get_is_not_csrf_checked(probe: httpx.AsyncClient, factory: Factory) -> None:
    user = await factory.user()
    await signed_in(probe, user)
    probe.headers.pop("X-CSRF-Token")
    assert (await probe.get("/api/v1/_probe")).status_code == 200


async def test_ui_form_csrf_field(probe: httpx.AsyncClient, factory: Factory) -> None:
    user = await factory.user()
    await signed_in(probe, user)
    token = probe.headers.pop("X-CSRF-Token")
    refused = await probe.post("/_probe-page", data={"note": "hi"})
    assert refused.status_code == 403
    assert "text/html" in refused.headers["content-type"]
    accepted = await probe.post("/_probe-page", data={"note": "hi", "csrf_token": token})
    assert accepted.status_code == 200
    assert "hi" in accepted.text


async def test_require_admin(probe: httpx.AsyncClient, factory: Factory) -> None:
    member = await factory.user()
    await signed_in(probe, member)
    api = await probe.get("/api/v1/_probe/admin")
    assert api.status_code == 403
    assert api.json()["code"] == "not_admin"
    page = await probe.get("/_probe-page/admin")
    assert page.status_code == 403
    assert "text/html" in page.headers["content-type"]


async def test_admin_allowed(probe: httpx.AsyncClient, factory: Factory) -> None:
    admin = await factory.user(role="admin")
    await signed_in(probe, admin)
    assert (await probe.get("/api/v1/_probe/admin")).status_code == 200
    assert (await probe.get("/_probe-page/admin")).status_code == 200


async def test_password_change_required(probe: httpx.AsyncClient, factory: Factory) -> None:
    user = await factory.user(must_change_password=True)
    await signed_in(probe, user)
    api = await probe.get("/api/v1/_probe")
    assert api.status_code == 403
    assert api.json()["code"] == "password_change_required"
    assert (await probe.get("/api/v1/_probe/any-password")).status_code == 200
    assert (await probe.get("/api/v1/me")).status_code == 200
    page = await probe.get("/_probe-page")
    assert page.status_code == 303
    assert page.headers["location"] == "/account/password"
    assert await ui_csrf(probe)
