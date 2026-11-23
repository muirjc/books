"""Spec 014 User Story 4: Change password for everyone; admins confirm account changes."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, api_login, signed_in
from tests.integration.test_flow_fixes import link, text_of


@pytest.fixture(name="parent")
async def parent_fixture(factory: Factory) -> TestUser:
    return await factory.user("parent", role="admin", display_name="Parent")


@pytest.fixture(name="admin")
async def admin_fixture(
    parent: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), parent)


@pytest.fixture(name="ben")
async def ben_fixture(factory: Factory) -> TestUser:
    return await factory.user("ben", display_name="Ben")


async def role_and_active(factory: Factory, user: TestUser) -> tuple[str, bool]:
    row = await factory.row("SELECT role, is_active FROM app_user WHERE id = :id", id=user.id)
    return str(row["role"]), bool(row["is_active"])


@pytest.mark.ac("014/AC-15")
async def test_change_password_link_for_everyone(
    admin: httpx.AsyncClient, ben: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    member = await signed_in(client_factory(), ben)
    for client in (member, admin):
        page = (await client.get("/")).text
        assert link(page, "Change password") == "/account/password"


@pytest.mark.ac("014/AC-16")
@pytest.mark.parametrize(
    ("action", "wording", "after"),
    [
        ("deactivate", "Deactivate Ben? Ben won't be able to sign in until reactivated.",
         ("member", False)),
        ("make_admin", "Make Ben an Admin? Ben will be able to manage every account.",
         ("admin", True)),
    ],
)  # fmt: skip
async def test_actions_ask_first(
    admin: httpx.AsyncClient, factory: Factory, ben: TestUser,
    action: str, wording: str, after: tuple[str, bool],
) -> None:  # fmt: skip
    asked = await admin.post(f"/admin/users/{ben.id}", data={"action": action})
    assert asked.status_code == 200
    assert await role_and_active(factory, ben) == ("member", True)  # nothing changed
    assert wording in text_of(asked.text)
    assert re.search(rf'name="action" value="{action}"', asked.text)
    assert re.search(r'name="confirm" value="yes"', asked.text)
    assert link(asked.text, "Cancel") == "/admin/users"
    done = await admin.post(f"/admin/users/{ben.id}", data={"action": action, "confirm": "yes"})
    assert done.status_code == 303 and done.headers["location"] == "/admin/users?msg=updated"
    assert await role_and_active(factory, ben) == after


@pytest.mark.ac("014/AC-16")
async def test_undoing_actions_stay_one_step(
    admin: httpx.AsyncClient, factory: Factory, ben: TestUser
) -> None:
    await factory.execute("UPDATE app_user SET is_active = false, role = 'admin' WHERE id = :id",
                          id=ben.id)  # fmt: skip
    for action in ("reactivate", "make_member"):
        response = await admin.post(f"/admin/users/{ben.id}", data={"action": action})
        assert response.status_code == 303, action
    assert await role_and_active(factory, ben) == ("member", True)


@pytest.mark.ac("014/AC-16")
async def test_a_refused_action_still_shows_todays_error(
    admin: httpx.AsyncClient, parent: TestUser
) -> None:
    asked = await admin.post(f"/admin/users/{parent.id}", data={"action": "deactivate"})
    assert asked.status_code == 200
    refused = await admin.post(f"/admin/users/{parent.id}",
                               data={"action": "deactivate", "confirm": "yes"})  # fmt: skip
    assert refused.status_code == 409 and "last active Admin" in refused.text


@pytest.mark.ac("014/AC-17")
async def test_reset_password_asks_first_without_showing_it(
    admin: httpx.AsyncClient, ben: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    url = f"/admin/users/{ben.id}/reset-password"
    short = await admin.post(url, data={"temporary_password": "short"})
    assert short.status_code == 422  # refused before any confirmation
    asked = await admin.post(url, data={"temporary_password": "temporary-1"})
    assert asked.status_code == 200
    assert "Reset Ben's password?" in text_of(asked.text)
    assert "temporary-1" not in text_of(asked.text)  # not on the page, only in the form
    assert re.search(
        r'<input type="hidden" name="temporary_password" value="temporary-1">', asked.text
    )
    assert (await api_login(client_factory(), "ben", "temporary-1")).status_code == 401
    done = await admin.post(url, data={"temporary_password": "temporary-1", "confirm": "yes"})
    assert done.status_code == 303
    assert (await api_login(client_factory(), "ben", "temporary-1")).status_code == 200


async def test_confirming_an_unknown_account_is_not_found(admin: httpx.AsyncClient) -> None:
    import uuid

    missing = uuid.uuid4()
    assert (
        await admin.post(f"/admin/users/{missing}", data={"action": "deactivate"})
    ).status_code == 404
    reset = await admin.post(f"/admin/users/{missing}/reset-password",
                             data={"temporary_password": "temporary-1"})  # fmt: skip
    assert reset.status_code == 404
