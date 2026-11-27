"""Spec 020 AC-11: the reading entry API accepts, returns, sorts and filters by rating, and
every response matches the published contract (contracts/api-rating.md)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in
from tests.contract.conftest import assert_matches_contract

READINGS = "/api/v1/me/readings"


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def api(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


async def ok(response: httpx.Response, status: int = 200) -> dict[str, object]:
    assert response.status_code == status, response.text
    assert_matches_contract(response)
    body = response.json()
    assert isinstance(body, dict)
    return body


@pytest.mark.ac("020/AC-11")
async def test_create_and_update_a_rating(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    dune = await factory.book("Dune", alice)
    emma = await factory.book("Emma", alice)
    rated = await ok(await api.post(READINGS, json={"book_id": str(dune), "rating": 4}), 201)
    assert rated["rating"] == 4
    plain = await ok(await api.post(READINGS, json={"book_id": str(emma)}), 201)
    assert plain["rating"] is None
    url = f"{READINGS}/{rated['id']}"
    assert (await ok(await api.get(url)))["rating"] == 4
    assert (await ok(await api.patch(url, json={"rating": 5})))["rating"] == 5
    kept = await ok(await api.patch(url, json={"status": "reading"}))
    assert kept["rating"] == 5 and kept["status"] == "reading"
    assert (await ok(await api.patch(url, json={"rating": None})))["rating"] is None
    listed = await ok(await api.get(READINGS))
    assert all("rating" in item for item in listed["items"])  # type: ignore[union-attr]


@pytest.mark.ac("020/AC-11")
@pytest.mark.parametrize("bad", [0, 6, "4", "4.5", 4.5, True, -1])
async def test_a_rating_outside_1_to_5_is_refused(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser, bad: object
) -> None:
    dune = await factory.book("Dune", alice)
    created = await api.post(READINGS, json={"book_id": str(dune), "rating": bad})
    assert created.status_code == 422, created.text
    assert_matches_contract(created)
    entry = await factory.entry(alice, await factory.book("Emma", alice), rating=3)
    patched = await api.patch(f"{READINGS}/{entry}", json={"rating": bad})
    assert patched.status_code == 422, patched.text
    assert_matches_contract(patched)
    assert await factory.scalar("SELECT rating FROM reading_entry WHERE id = :id", id=entry) == 3


@pytest.mark.ac("020/AC-11")
async def test_list_sorts_and_filters_by_rating(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    for title, rating in (("Middlemarch", 4), ("Dune", 5), ("Emma", 2), ("Ivanhoe", None),
                          ("Beowulf", None)):  # fmt: skip
        await factory.entry(alice, await factory.book(title, alice), rating=rating)

    async def listed(**params: str) -> list[str]:
        body = await ok(await api.get(READINGS, params=params))
        return [item["book"]["title"] for item in body["items"]]  # type: ignore[index, union-attr]

    assert await listed(sort="-rating") == ["Dune", "Middlemarch", "Emma", "Beowulf", "Ivanhoe"]
    assert await listed(sort="rating") == ["Emma", "Middlemarch", "Dune", "Beowulf", "Ivanhoe"]
    assert await listed(min_rating="4") == ["Dune", "Middlemarch"]
    assert await listed(min_rating="1") == ["Dune", "Emma", "Middlemarch"]
    assert await listed(rated="true") == ["Dune", "Emma", "Middlemarch"]
    assert await listed(rated="false") == ["Beowulf", "Ivanhoe"]
    assert await listed(rated="false", min_rating="2") == []
    assert await listed(min_rating="2", sort="-rating", q="m") == ["Middlemarch", "Emma"]
    for bad in ({"min_rating": "0"}, {"min_rating": "6"}, {"min_rating": "x"},
                {"rated": "maybe"}, {"sort": "stars"}):  # fmt: skip
        refused = await api.get(READINGS, params=bad)
        assert refused.status_code == 422, bad
        assert_matches_contract(refused)


async def test_another_members_entry_is_404(api: httpx.AsyncClient, factory: Factory) -> None:
    ben = await factory.user("ben")
    theirs = await factory.entry(ben, await factory.book("Dune", ben), rating=5)
    for response in (
        await api.get(f"{READINGS}/{theirs}"),
        await api.patch(f"{READINGS}/{theirs}", json={"rating": 1}),
        await api.get(f"{READINGS}/{uuid.uuid4()}"),
    ):
        assert response.status_code == 404
        assert_matches_contract(response)
    assert await factory.scalar("SELECT rating FROM reading_entry WHERE id = :id", id=theirs) == 5
