"""T064: temporary passwords must be changed before anything else (FR-004, FR-028)."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, api_login, signed_in


async def page_sign_in(client: httpx.AsyncClient, login: str, password: str) -> httpx.Response:
    page = await client.get("/sign-in")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert token
    return await client.post(
        "/sign-in", data={"login": login, "password": password, "csrf_token": token.group(1)}
    )


@pytest.mark.ac("001/AC-09")
@pytest.mark.ac("001/AC-11")
async def test_initial_password_forces_change(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    admin = await signed_in(client_factory(), await factory.user("parent", role="admin"))
    created = await admin.post(
        "/api/v1/admin/users",
        json={"display_name": "Sam", "login": "sam", "initial_password": "initial-pass"},
    )
    assert created.status_code == 201
    browser = client_factory()
    response = await page_sign_in(browser, "sam", "initial-pass")
    assert response.status_code == 303
    assert response.headers["location"] == "/account/password"
    for path in ("/", "/books/add"):
        redirected = await browser.get(path)
        assert redirected.status_code == 303
        assert redirected.headers["location"] == "/account/password"
    page = await browser.get("/account/password")
    assert page.status_code == 200
    assert "Choose a new password" in page.text


@pytest.mark.ac("001/AC-11")
async def test_api_blocked_until_changed(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    user = await factory.user("ben", must_change_password=True, password="temporary-1")
    api = await signed_in(client_factory(), user)
    blocked = await api.get("/api/v1/me/readings")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_change_required"
    assert (await api.get("/api/v1/me")).status_code == 200
    wrong = await api.post(
        "/api/v1/auth/password",
        json={"current_password": "not-it", "new_password": "my-own-password"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "wrong_current_password"
    short = await api.post(
        "/api/v1/auth/password", json={"current_password": "temporary-1", "new_password": "short"}
    )
    assert short.status_code == 422
    other_session = await signed_in(client_factory(), user)
    changed = await api.post(
        "/api/v1/auth/password",
        json={"current_password": "temporary-1", "new_password": "my-own-password"},
    )
    assert changed.status_code == 204
    assert (await api.get("/api/v1/me/readings")).status_code == 200
    assert (await other_session.get("/api/v1/me")).status_code == 401  # other sessions ended
    assert (await api_login(client_factory(), "ben", "my-own-password")).status_code == 200


async def test_change_password_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    await factory.user("ben", must_change_password=True, password="temporary-1")
    browser = client_factory()
    await page_sign_in(browser, "ben", "temporary-1")
    csrf = (await browser.get("/api/v1/me")).json()["csrf_token"]
    mismatch = await browser.post(
        "/account/password",
        data={
            "csrf_token": csrf,
            "current_password": "temporary-1",
            "new_password": "my-own-password",
            "repeat_password": "different-one",
        },
    )
    assert mismatch.status_code == 422
    assert "don" in mismatch.text and "match" in mismatch.text
    wrong = await browser.post(
        "/account/password",
        data={
            "csrf_token": csrf,
            "current_password": "nope",
            "new_password": "my-own-password",
            "repeat_password": "my-own-password",
        },
    )
    assert wrong.status_code == 400
    ok = await browser.post(
        "/account/password",
        data={
            "csrf_token": csrf,
            "current_password": "temporary-1",
            "new_password": "my-own-password",
            "repeat_password": "my-own-password",
        },
    )
    assert ok.status_code == 303
    assert ok.headers["location"] == "/?msg=password"
    home = await browser.get("/?msg=password")
    assert home.status_code == 200
    assert "Your password has been changed." in home.text
