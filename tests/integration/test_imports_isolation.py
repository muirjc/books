"""An import never reaches another member's list (spec 002 AC-18; Principle I; T025)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory
from tests.fakes import FakeBookSource
from tests.integration.import_helpers import (
    KEY,
    WORKS_URL,
    confirm_via_page,
    import_via_api,
    member,
    stock,
)


@pytest.mark.ac("002/AC-18")
async def test_api_import_reaches_only_the_importers_list(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    alice, alice_api = await member(factory, client_factory, "alice")
    ben, ben_api = await member(factory, client_factory, "ben")
    assert (await import_via_api(alice_api, ["OL1W", "OL2W"])).status_code == 201

    ben_list = await ben_api.get("/api/v1/me/readings")
    assert ben_list.json()["total"] == 0
    states = {w["work_key"]: w["state"] for w in (await ben_api.get(WORKS_URL)).json()["works"]}
    assert states == {"OL1W": "in_catalog", "OL2W": "in_catalog", "OL3W": "new"}

    assert (await import_via_api(ben_api, ["OL1W"])).status_code == 201
    assert (
        await factory.scalar("SELECT count(*) FROM reading_entry WHERE user_id = :u", u=alice.id)
        == 2
    )
    assert (
        await factory.scalar("SELECT count(*) FROM reading_entry WHERE user_id = :u", u=ben.id) == 1
    )


@pytest.mark.ac("002/AC-18")
async def test_no_import_endpoint_accepts_a_user_id(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, alice_api = await member(factory, client_factory, "alice")
    ben, _ = await member(factory, client_factory, "ben")
    await alice_api.get(WORKS_URL)
    sneaky = await alice_api.post(
        "/api/v1/me/imports",
        json={"author_key": KEY, "work_keys": ["OL1W"], "user_id": str(ben.id)},
    )
    assert sneaky.status_code == 422
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 0


@pytest.mark.ac("002/AC-18")
async def test_page_import_reaches_only_the_importers_list(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    alice, alice_web = await member(factory, client_factory, "alice")
    ben, ben_web = await member(factory, client_factory, "ben")
    done = await confirm_via_page(alice_web, ["OL1W"])
    assert done.status_code == 200, done.text

    ben_page = await ben_web.get(f"/import/authors/{KEY}")
    assert "In the family catalog" in ben_page.text
    assert "Already on your list" not in ben_page.text

    assert (await confirm_via_page(ben_web, ["OL1W", "OL2W"])).status_code == 200
    alice_status = await factory.scalar(
        "SELECT array_agg(status) FROM reading_entry WHERE user_id = :u", u=alice.id
    )
    assert alice_status == ["finished"]
    assert (
        await factory.scalar("SELECT count(*) FROM reading_entry WHERE user_id = :u", u=ben.id) == 2
    )
