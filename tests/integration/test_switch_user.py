"""T066: "Switch user" on a shared device (FR-007, AC-28)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser
from tests.integration.test_password_change import page_sign_in

COOKIE = "recent_profiles"


def recent_ids(client: httpx.AsyncClient) -> list[str]:
    value = client.cookies.get(COOKIE) or ""
    return [v for v in value.strip('"').split(".") if v]


async def sign_in_as(client: httpx.AsyncClient, user: TestUser) -> httpx.Response:
    response = await page_sign_in(client, user.login, user.password)
    assert response.status_code == 303
    return response


@pytest.mark.ac("001/AC-28")
async def test_cookie_lists_recent_profiles(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    device = client_factory()
    users = [await factory.user(f"kid{i}", display_name=f"Kid {i}") for i in range(6)]
    first = await sign_in_as(device, users[0])
    cookie = next(c for c in first.headers.get_list("set-cookie") if c.startswith(COOKIE))
    lowered = cookie.lower()
    assert "httponly" in lowered and "secure" in lowered and "samesite=lax" in lowered
    assert "max-age=7776000" in lowered  # 90 days
    for user in users[1:]:
        await device.post("/switch-user", data={"csrf_token": await csrf(device)})
        await sign_in_as(device, user)
    ids = recent_ids(device)
    assert ids == [str(u.id) for u in reversed(users[1:])]  # most recent first, at most 5
    await device.post("/switch-user", data={"csrf_token": await csrf(device)})
    await sign_in_as(device, users[3])
    assert recent_ids(device)[0] == str(users[3].id)
    assert len(recent_ids(device)) == 5


async def csrf(client: httpx.AsyncClient) -> str:
    return str((await client.get("/api/v1/me")).json()["csrf_token"])


@pytest.mark.ac("001/AC-28")
async def test_switch_user_signs_out_and_lists_profiles(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    device = client_factory()
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    await sign_in_as(device, ben)
    await device.post("/switch-user", data={"csrf_token": await csrf(device)})
    await sign_in_as(device, alice)
    response = await device.post("/switch-user", data={"csrf_token": await csrf(device)})
    assert response.status_code == 303
    assert response.headers["location"] == "/sign-in"
    assert (await device.get("/api/v1/me")).status_code == 401
    assert recent_ids(device) == [str(alice.id), str(ben.id)]
    page = (await device.get("/sign-in")).text
    buttons = re.findall(r'data-fill-login="([^"]+)"', page)
    assert buttons == ["alice", "ben"]
    assert "Alice" in page and "Ben" in page
    assert 'type="password"' in page  # the password is still required


@pytest.mark.ac("001/AC-28")
async def test_deactivated_and_bogus_profiles_are_omitted(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    device = client_factory()
    alice = await factory.user("alice", display_name="Alice")
    gone = await factory.user("gone", display_name="Gone")
    await sign_in_as(device, gone)
    await device.post("/switch-user", data={"csrf_token": await csrf(device)})
    await sign_in_as(device, alice)
    await factory.execute("UPDATE app_user SET is_active = false WHERE id = :id", id=gone.id)
    device.cookies.set(
        COOKIE, f"{alice.id}.{gone.id}.not-a-uuid.{uuid.uuid4()}", domain="testserver"
    )
    page = (await device.get("/sign-in")).text
    assert re.findall(r'data-fill-login="([^"]+)"', page) == ["alice"]
