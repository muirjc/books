"""T019: sign-in endpoints match contracts/openapi.yaml."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import DEFAULT_PASSWORD, Factory, api_login, presession_token
from tests.contract.conftest import assert_matches_contract


async def test_csrf_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    assert_matches_contract(response)


@pytest.mark.ac("001/AC-01")
async def test_login_success(client: httpx.AsyncClient, factory: Factory) -> None:
    user = await factory.user("alice")
    response = await api_login(client, "alice")
    assert response.status_code == 200
    assert_matches_contract(response)
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["login"] == "alice"
    assert body["csrf_token"]


@pytest.mark.ac("001/AC-01")
async def test_login_failures_share_one_body(client: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("alice")
    await factory.user("gone", is_active=False)
    wrong = await api_login(client, "alice", "not-the-password")
    unknown = await api_login(client, "nobody", DEFAULT_PASSWORD)
    deactivated = await api_login(client, "gone", DEFAULT_PASSWORD)
    for response in (wrong, unknown, deactivated):
        assert response.status_code == 401
        assert_matches_contract(response)
    assert wrong.json() == unknown.json() == deactivated.json()


async def test_login_requires_csrf(client: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("alice")
    missing = await client.post(
        "/api/v1/auth/login", json={"login": "alice", "password": DEFAULT_PASSWORD}
    )
    assert missing.status_code == 403
    assert_matches_contract(missing)
    await presession_token(client)
    forged = await client.post(
        "/api/v1/auth/login",
        json={"login": "alice", "password": DEFAULT_PASSWORD},
        headers={"X-CSRF-Token": "forged.value"},
    )
    assert forged.status_code == 403


async def test_login_validation_error(client: httpx.AsyncClient) -> None:
    token = await presession_token(client)
    response = await client.post(
        "/api/v1/auth/login", json={"login": "alice"}, headers={"X-CSRF-Token": token}
    )
    assert response.status_code == 422
    assert_matches_contract(response)
    assert response.json()["errors"][0]["field"] == "password"


@pytest.mark.ac("001/AC-02")
async def test_logout_and_me(client: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("alice")
    login = await api_login(client, "alice")
    csrf = login.json()["csrf_token"]
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert_matches_contract(me)
    logout = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 204
    assert_matches_contract(logout)
    after = await client.get("/api/v1/me")
    assert after.status_code == 401
    assert_matches_contract(after)
