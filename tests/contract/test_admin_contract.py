"""T067: account endpoints match contracts/openapi.yaml."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, api_login, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.mark.ac("001/AC-09")
@pytest.mark.ac("001/AC-26")
@pytest.mark.ac("001/AC-29")
async def test_admin_endpoints(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    parent = await factory.user("parent", role="admin")
    admin = await signed_in(client_factory(), parent)

    listed = await admin.get("/api/v1/admin/users")
    assert listed.status_code == 200
    assert_matches_contract(listed)

    created = await admin.post(
        "/api/v1/admin/users",
        json={"display_name": "Sam", "login": "sam", "initial_password": "abcdefgh"},
    )
    assert created.status_code == 201
    assert_matches_contract(created)
    sam = created.json()["id"]

    for response in (
        await admin.post(
            "/api/v1/admin/users",
            json={"display_name": "Sam", "login": "SAM", "initial_password": "abcdefgh"},
        ),
        await admin.patch(f"/api/v1/admin/users/{parent.id}", json={"role": "member"}),
    ):
        assert response.status_code == 409
        assert_matches_contract(response)

    invalid = await admin.post(
        "/api/v1/admin/users", json={"display_name": "", "login": "x", "initial_password": "short"}
    )
    assert invalid.status_code == 422
    assert_matches_contract(invalid)

    patched = await admin.patch(f"/api/v1/admin/users/{sam}", json={"display_name": "Samuel"})
    assert patched.status_code == 200
    assert_matches_contract(patched)

    reset = await admin.post(
        f"/api/v1/admin/users/{sam}/password-reset", json={"temporary_password": "temporary-1"}
    )
    assert reset.status_code == 204
    assert_matches_contract(reset)

    missing = await admin.patch(f"/api/v1/admin/users/{uuid.uuid4()}", json={"is_active": True})
    assert missing.status_code == 404
    assert_matches_contract(missing)

    member = await signed_in(client_factory(), await factory.user("ben"))
    forbidden = await member.get("/api/v1/admin/users")
    assert forbidden.status_code == 403
    assert_matches_contract(forbidden)


async def test_password_change(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    user = await factory.user("ben", password="temporary-1", must_change_password=True)
    api = await signed_in(client_factory(), user)
    blocked = await api.get("/api/v1/me/readings")
    assert blocked.status_code == 403
    assert_matches_contract(blocked)
    wrong = await api.post(
        "/api/v1/auth/password", json={"current_password": "nope", "new_password": "abcdefgh"}
    )
    assert wrong.status_code == 400
    assert_matches_contract(wrong)
    ok = await api.post(
        "/api/v1/auth/password",
        json={"current_password": "temporary-1", "new_password": "abcdefgh"},
    )
    assert ok.status_code == 204
    assert_matches_contract(ok)


@pytest.mark.ac("001/AC-33")
async def test_throttled_login(factory: Factory, client: httpx.AsyncClient) -> None:
    await factory.user("ben")
    for _ in range(5):
        await api_login(client, "ben", "wrong-password")
    locked = await api_login(client, "ben")
    assert locked.status_code == 429
    assert_matches_contract(locked)
    assert locked.headers["retry-after"]
