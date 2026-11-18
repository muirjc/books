"""T062: Admin account management (FR-002 – FR-005, FR-008, FR-028); covers services/accounts.py."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, api_login, gather, signed_in


@pytest.fixture
async def parent(factory: Factory) -> TestUser:
    return await factory.user("parent", role="admin")


@pytest.fixture
async def admin_api(
    parent: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), parent)


async def create(
    admin_api: httpx.AsyncClient,
    login: str,
    password: str = "initial-pass",
    role: str = "member",
    display_name: str | None = None,
) -> httpx.Response:
    return await admin_api.post(
        "/api/v1/admin/users",
        json={
            "display_name": display_name or login.title(),
            "login": login,
            "role": role,
            "initial_password": password,
        },
    )


@pytest.mark.ac("001/AC-09")
async def test_create_child_account_without_email(
    admin_api: httpx.AsyncClient, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    response = await create(admin_api, "sam", display_name="Sam")
    assert response.status_code == 201
    account = response.json()
    assert (account["login"], account["role"], account["is_active"]) == ("sam", "member", True)
    assert account["must_change_password"] is True
    signed = await api_login(client_factory(), "sam", "initial-pass")
    assert signed.status_code == 200
    assert signed.json()["must_change_password"] is True


@pytest.mark.ac("001/AC-29")
async def test_login_unique_ignoring_case(admin_api: httpx.AsyncClient) -> None:
    assert (await create(admin_api, "Sam")).status_code == 201
    duplicate = await create(admin_api, "sam")
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "login_exists"


@pytest.mark.ac("001/AC-34")
async def test_password_length_rule(admin_api: httpx.AsyncClient) -> None:
    short = await create(admin_api, "kid", password="1234567")
    assert short.status_code == 422
    assert short.json()["errors"][0]["field"] == "initial_password"
    ok = await create(admin_api, "kid", password="abcdefgh")
    assert ok.status_code == 201
    user_id = ok.json()["id"]
    short_reset = await admin_api.post(
        f"/api/v1/admin/users/{user_id}/password-reset", json={"temporary_password": "short"}
    )
    assert short_reset.status_code == 422
    good_reset = await admin_api.post(
        f"/api/v1/admin/users/{user_id}/password-reset", json={"temporary_password": "abcdefgh"}
    )
    assert good_reset.status_code == 204


@pytest.mark.ac("001/AC-10")
async def test_deactivate_and_reactivate(
    admin_api: httpx.AsyncClient,
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
) -> None:
    ben = await factory.user("ben")
    book = await factory.book("Dune", ben)
    await factory.entry(ben, book, notes="kept")
    ben_client = await signed_in(client_factory(), ben)
    response = await admin_api.patch(f"/api/v1/admin/users/{ben.id}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert (await ben_client.get("/api/v1/me")).status_code == 401  # session ended
    assert (await api_login(client_factory(), "ben")).status_code == 401
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 1
    await admin_api.patch(f"/api/v1/admin/users/{ben.id}", json={"is_active": True})
    back = await signed_in(client_factory(), ben)
    entries = (await back.get("/api/v1/me/readings")).json()["items"]
    assert [e["notes"] for e in entries] == ["kept"]


@pytest.mark.ac("001/AC-26")
async def test_last_admin_cannot_leave(admin_api: httpx.AsyncClient, parent: TestUser) -> None:
    deactivate = await admin_api.patch(
        f"/api/v1/admin/users/{parent.id}", json={"is_active": False}
    )
    assert deactivate.status_code == 409
    assert deactivate.json()["code"] == "last_admin"
    demote = await admin_api.patch(f"/api/v1/admin/users/{parent.id}", json={"role": "member"})
    assert demote.status_code == 409
    rename = await admin_api.patch(f"/api/v1/admin/users/{parent.id}", json={"display_name": "Mum"})
    assert rename.status_code == 200
    assert rename.json()["display_name"] == "Mum"


@pytest.mark.ac("001/AC-26")
async def test_two_admins_cannot_both_demote_each_other(
    factory: Factory,
    parent: TestUser,
    admin_api: httpx.AsyncClient,
    client_factory: Callable[[], httpx.AsyncClient],
) -> None:
    other = await factory.user("other-parent", role="admin")
    other_api = await signed_in(client_factory(), other)
    results: list[Any] = await gather(
        admin_api.patch(f"/api/v1/admin/users/{other.id}", json={"role": "member"}),
        other_api.patch(f"/api/v1/admin/users/{parent.id}", json={"role": "member"}),
    )
    # The loser is refused either by the last-Admin guard (409) or, if the winner committed
    # before the loser's request was authenticated, because it is no longer an Admin (403).
    assert sorted(r.status_code for r in results) in ([200, 403], [200, 409])
    admins = await factory.scalar(
        "SELECT count(*) FROM app_user WHERE role = 'admin' AND is_active"
    )
    assert admins == 1


async def test_second_admin_can_be_demoted(admin_api: httpx.AsyncClient, factory: Factory) -> None:
    other = await factory.user("other-parent", role="admin")
    response = await admin_api.patch(f"/api/v1/admin/users/{other.id}", json={"role": "member"})
    assert response.status_code == 200
    assert response.json()["role"] == "member"


async def test_reset_requires_change_and_ends_sessions(
    admin_api: httpx.AsyncClient,
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
) -> None:
    ben = await factory.user("ben")
    ben_client = await signed_in(client_factory(), ben)
    response = await admin_api.post(
        f"/api/v1/admin/users/{ben.id}/password-reset", json={"temporary_password": "temporary-1"}
    )
    assert response.status_code == 204
    assert (await ben_client.get("/api/v1/me")).status_code == 401
    signed = await api_login(client_factory(), "ben", "temporary-1")
    assert signed.json()["must_change_password"] is True


async def test_unknown_account(admin_api: httpx.AsyncClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    patch = await admin_api.patch(f"/api/v1/admin/users/{missing}", json={"is_active": False})
    assert patch.status_code == 404
    reset = await admin_api.post(
        f"/api/v1/admin/users/{missing}/password-reset", json={"temporary_password": "abcdefgh"}
    )
    assert reset.status_code == 404


async def test_list_accounts(admin_api: httpx.AsyncClient, factory: Factory) -> None:
    await factory.user("ben", display_name="Ben")
    accounts = (await admin_api.get("/api/v1/admin/users")).json()
    assert [a["display_name"] for a in accounts] == ["Ben", "Parent"]
    assert all("password_hash" not in a for a in accounts)
