"""T068: account management pages (FR-003 – FR-005)."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, api_login, signed_in


@pytest.fixture
async def parent(factory: Factory) -> TestUser:
    return await factory.user("parent", role="admin", display_name="Parent")


@pytest.fixture
async def admin_browser(
    parent: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), parent)


async def test_accounts_list(admin_browser: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("ben", display_name="Ben")
    await factory.user("gone", display_name="Gone", is_active=False)
    page = await admin_browser.get("/admin/users")
    assert page.status_code == 200
    text = page.text
    assert "<h1>Accounts</h1>" in text
    for name in ("Ben", "Gone", "Parent"):
        assert name in text
    assert "Deactivated" in text and "Admin" in text and "Member" in text
    assert 'href="/admin/users/new"' in text
    nav = await admin_browser.get("/")
    assert 'href="/admin/users"' in nav.text


@pytest.mark.ac("001/AC-09")
async def test_create_account_page(
    admin_browser: httpx.AsyncClient,
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
) -> None:
    form = await admin_browser.get("/admin/users/new")
    for field in ("display_name", "login", "role", "initial_password"):
        assert re.search(rf'<label for="{field}"', form.text), field
    created = await admin_browser.post(
        "/admin/users/new",
        data={
            "display_name": "Sam",
            "login": "sam",
            "role": "member",
            "initial_password": "abcdefgh",
        },
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/admin/users?msg=created"
    listed = await admin_browser.get("/admin/users?msg=created")
    assert "Account created." in listed.text and "Sam" in listed.text
    assert (await api_login(client_factory(), "sam", "abcdefgh")).status_code == 200


async def test_create_account_errors(admin_browser: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("sam")
    response = await admin_browser.post(
        "/admin/users/new",
        data={"display_name": "Sam", "login": "SAM", "role": "member", "initial_password": "short"},
    )
    assert response.status_code == 422
    text = html.unescape(response.text)
    assert "at least 8 characters" in text
    assert 'id="initial_password-error"' in response.text
    duplicate = await admin_browser.post(
        "/admin/users/new",
        data={
            "display_name": "Sam",
            "login": "SAM",
            "role": "member",
            "initial_password": "abcdefgh",
        },
    )
    assert duplicate.status_code == 409
    assert "That login is already in use" in duplicate.text
    assert 'id="login-error"' in duplicate.text


@pytest.mark.ac("001/AC-10")
async def test_deactivate_reactivate_and_role(
    admin_browser: httpx.AsyncClient,
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
) -> None:
    ben = await factory.user("ben", display_name="Ben")
    off = await admin_browser.post(
        f"/admin/users/{ben.id}", data={"action": "deactivate", "confirm": "yes"}
    )
    assert off.status_code == 303
    assert (await api_login(client_factory(), "ben")).status_code == 401
    on = await admin_browser.post(f"/admin/users/{ben.id}", data={"action": "reactivate"})
    assert on.status_code == 303
    assert (await api_login(client_factory(), "ben")).status_code == 200
    promote = await admin_browser.post(
        f"/admin/users/{ben.id}", data={"action": "make_admin", "confirm": "yes"}
    )
    assert promote.status_code == 303
    assert await factory.scalar("SELECT role FROM app_user WHERE id = :id", id=ben.id) == "admin"
    demote = await admin_browser.post(f"/admin/users/{ben.id}", data={"action": "make_member"})
    assert demote.status_code == 303
    assert await factory.scalar("SELECT role FROM app_user WHERE id = :id", id=ben.id) == "member"


async def test_reset_password_page(
    admin_browser: httpx.AsyncClient,
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
) -> None:
    ben = await factory.user("ben", display_name="Ben")
    short = await admin_browser.post(
        f"/admin/users/{ben.id}/reset-password", data={"temporary_password": "short"}
    )
    assert short.status_code == 422
    ok = await admin_browser.post(
        f"/admin/users/{ben.id}/reset-password",
        data={"temporary_password": "temporary-1", "confirm": "yes"},
    )
    assert ok.status_code == 303
    listed = await admin_browser.get(ok.headers["location"])
    assert "Password reset" in listed.text
    signed = await api_login(client_factory(), "ben", "temporary-1")
    assert signed.json()["must_change_password"] is True


@pytest.mark.ac("001/AC-26")
async def test_last_admin_refusal_is_shown(
    admin_browser: httpx.AsyncClient, parent: TestUser
) -> None:
    response = await admin_browser.post(
        f"/admin/users/{parent.id}", data={"action": "deactivate", "confirm": "yes"}
    )
    assert response.status_code == 409
    assert "last active Admin" in response.text
