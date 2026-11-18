"""T020: sign-in and sign-out pages."""

from __future__ import annotations

import re

import httpx
import pytest

from tests.conftest import DEFAULT_PASSWORD, Factory


def hidden_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "page has no csrf_token field"
    return match.group(1)


async def ui_sign_in(
    client: httpx.AsyncClient, login: str, password: str = DEFAULT_PASSWORD
) -> httpx.Response:
    page = await client.get("/sign-in")
    return await client.post(
        "/sign-in",
        data={
            "login": login,
            "password": password,
            "csrf_token": hidden_csrf(page.text),
        },
    )


async def test_sign_in_form(client: httpx.AsyncClient) -> None:
    response = await client.get("/sign-in")
    assert response.status_code == 200
    html = response.text
    assert re.search(r'<label for="login">', html)
    assert re.search(r'<label for="password">', html)
    assert 'id="login"' in html and 'id="password"' in html
    assert "create account" not in html.lower()
    assert "sign up" not in html.lower()
    assert "register" not in html.lower()


@pytest.mark.ac("001/AC-01")
async def test_sign_in_sets_secure_cookie(client: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("alice")
    response = await ui_sign_in(client, "alice")
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = next(
        c for c in response.headers.get_list("set-cookie") if c.startswith("__Host-session=")
    )
    lowered = cookie.lower()
    assert "secure" in lowered
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert "path=/" in lowered
    assert "domain=" not in lowered


@pytest.mark.ac("001/AC-02")
async def test_sign_out_ends_session(client: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("alice")
    await ui_sign_in(client, "alice")
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    response = await client.post("/sign-out", data={"csrf_token": me.json()["csrf_token"]})
    assert response.status_code == 303
    assert response.headers["location"] == "/sign-in"
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_wrong_password_rerenders_with_one_message(
    client: httpx.AsyncClient, factory: Factory
) -> None:
    await factory.user("alice")
    response = await ui_sign_in(client, "alice", "wrong-password")
    assert response.status_code == 401
    assert response.text.count('class="error-summary"') == 1
    assert "Wrong login or password" in response.text
    assert 'value="alice"' in response.text


async def test_sign_in_without_csrf_is_refused(client: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("alice")
    response = await client.post("/sign-in", data={"login": "alice", "password": DEFAULT_PASSWORD})
    assert response.status_code == 403
