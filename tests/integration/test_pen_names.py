"""T078: pen names with an optional real name (FR-014, AC-17, AC-18)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in

PEN_NAME_FIRST = "Mark the author as a pen name first"


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def api(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.mark.ac("001/AC-17")
async def test_pen_name_with_real_name_added_later(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    created = await api.post(
        "/api/v1/authors", json={"name": "Robert Galbraith", "is_pen_name": True}
    )
    assert created.status_code == 201
    author = created.json()
    assert (author["is_pen_name"], author["real_name"]) == (True, None)
    await factory.book("The Cuckoo's Calling", alice, author_ids=[author["id"]])
    assert (await api.get("/api/v1/authors?q=Rowling")).json() == []
    patched = await api.patch(f"/api/v1/authors/{author['id']}", json={"real_name": "J.K. Rowling"})
    assert patched.status_code == 200
    assert patched.json()["real_name"] == "J.K. Rowling"
    authors = (await api.get("/api/v1/authors?q=Rowling")).json()
    assert [a["name"] for a in authors] == ["Robert Galbraith"]
    books = (await api.get("/api/v1/books?q=Rowling")).json()
    assert [b["title"] for b in books] == ["The Cuckoo's Calling"]


@pytest.mark.ac("001/AC-18")
async def test_real_name_requires_pen_name(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    create = await api.post(
        "/api/v1/authors", json={"name": "Someone", "real_name": "Someone Else"}
    )
    assert create.status_code == 422
    error = create.json()["errors"][0]
    assert (error["field"], error["message"]) == ("real_name", PEN_NAME_FIRST)
    plain = await factory.author("Plain Author", alice)
    patch = await api.patch(f"/api/v1/authors/{plain}", json={"real_name": "Hidden"})
    assert patch.status_code == 422
    error = patch.json()["errors"][0]
    assert (error["field"], error["message"]) == ("real_name", PEN_NAME_FIRST)
    both = await api.patch(
        f"/api/v1/authors/{plain}", json={"is_pen_name": True, "real_name": "Hidden"}
    )
    assert both.status_code == 200


async def test_unmarking_pen_name_clears_real_name(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    author = await factory.author(
        "Robert Galbraith", alice, is_pen_name=True, real_name="J.K. Rowling"
    )
    response = await api.patch(f"/api/v1/authors/{author}", json={"is_pen_name": False})
    assert response.status_code == 200
    assert (response.json()["is_pen_name"], response.json()["real_name"]) == (False, None)
