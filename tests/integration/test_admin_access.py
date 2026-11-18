"""T065: Admin rights cover accounts only; no self-registration (AC-12 – AC-14)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in

ADMIN_API = [
    ("GET", "/api/v1/admin/users", None),
    (
        "POST",
        "/api/v1/admin/users",
        {"display_name": "X", "login": "xyz", "initial_password": "abcdefgh"},
    ),
    ("PATCH", "/api/v1/admin/users/{id}", {"is_active": False}),
    ("POST", "/api/v1/admin/users/{id}/password-reset", {"temporary_password": "abcdefgh"}),
]
ADMIN_PAGES = [
    ("GET", "/admin/users", None),
    ("GET", "/admin/users/new", None),
    (
        "POST",
        "/admin/users/new",
        {"display_name": "X", "login": "xyz", "initial_password": "abcdefgh"},
    ),
    ("POST", "/admin/users/{id}", {"action": "deactivate"}),
    ("POST", "/admin/users/{id}/reset-password", {"temporary_password": "abcdefgh"}),
]


@pytest.mark.ac("001/AC-13")
@pytest.mark.parametrize("method,path,body", ADMIN_API)
async def test_member_refused_on_admin_api(
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
    method: str,
    path: str,
    body: object,
) -> None:
    member = await factory.user("ben")
    api = await signed_in(client_factory(), member)
    response = await api.request(method, path.format(id=member.id), json=body)
    assert response.status_code == 403
    assert response.json()["code"] == "not_admin"


@pytest.mark.ac("001/AC-13")
@pytest.mark.parametrize("method,path,form", ADMIN_PAGES)
async def test_member_refused_on_admin_pages(
    factory: Factory,
    client_factory: Callable[[], httpx.AsyncClient],
    method: str,
    path: str,
    form: object,
) -> None:
    member = await factory.user("ben")
    browser = await signed_in(client_factory(), member)
    response = await browser.request(method, path.format(id=member.id), data=form)
    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    assert await factory.scalar("SELECT count(*) FROM app_user") == 1


@pytest.mark.ac("001/AC-14")
async def test_admin_cannot_see_members_entries(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    parent = await factory.user("parent", role="admin")
    ben = await factory.user("ben")
    book = await factory.book("Diary", ben)
    ben_entry = await factory.entry(ben, book, notes="ben's private thoughts")
    admin = await signed_in(client_factory(), parent)
    own = await admin.get("/api/v1/me/readings")
    assert own.json()["items"] == []
    assert (await admin.get(f"/api/v1/me/readings/{ben_entry}")).status_code == 404
    assert (await admin.get(f"/entries/{ben_entry}")).status_code == 404
    for path in ("/api/v1/admin/users", "/admin/users"):
        response = await admin.get(path)
        assert response.status_code == 200
        assert "private thoughts" not in response.text
        assert "Diary" not in response.text
        assert "notes" not in response.text.lower()


@pytest.mark.ac("001/AC-12")
async def test_no_self_registration(client: httpx.AsyncClient) -> None:
    for path in ("/register", "/sign-up", "/signup", "/admin/users/new"):
        response = await client.get(path)
        assert response.status_code in (303, 404), path
        if response.status_code == 303:
            assert response.headers["location"] == "/sign-in"
    api = await client.post(
        "/api/v1/admin/users",
        json={"display_name": "Me", "login": "me", "initial_password": "abcdefgh"},
    )
    assert api.status_code == 401
    page = (await client.get("/sign-in")).text.lower()
    for phrase in ("create an account", "create account", "sign up", "register"):
        assert phrase not in page
