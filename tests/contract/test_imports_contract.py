"""Spec 002's API operations match its contract (task T022)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import httpx
import pytest

from book_tracker.services.errors import SourceUnavailable
from tests.conftest import Factory
from tests.fakes import FakeBookSource
from tests.integration.import_helpers import KEY, WORKS_URL, import_via_api, member, stock

Check = Callable[[httpx.Response], None]


@pytest.mark.ac("002/AC-01")
@pytest.mark.ac("002/AC-02")
async def test_search_list_and_import(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient],
    book_source: FakeBookSource, matches_contract_002: Check,
) -> None:  # fmt: skip
    stock(book_source)
    _, api = await member(factory, client_factory, "alice")
    found = await api.get("/api/v1/import/authors", params={"q": "Ann Author"})
    assert found.status_code == 200
    matches_contract_002(found)
    listed = await api.get(WORKS_URL, params={"sort": "year"})
    assert listed.status_code == 200
    matches_contract_002(listed)
    added = await api.post(
        "/api/v1/me/imports",
        json={"author_key": KEY, "work_keys": ["OL1W", "OL2W"], "status": "reading"},
    )
    assert added.status_code == 201, added.text
    matches_contract_002(added)
    again = await import_via_api(api, ["OL1W"])
    assert again.status_code == 201
    assert again.json()["skipped"][0]["reason"] == "on_list"
    matches_contract_002(again)


async def test_errors_match_the_contract(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient],
    book_source: FakeBookSource, matches_contract_002: Check, app: object,
) -> None:  # fmt: skip
    stock(book_source)
    _, api = await member(factory, client_factory, "alice")

    unauthenticated = await client_factory().get("/api/v1/import/authors", params={"q": "x"})
    assert unauthenticated.status_code == 401
    matches_contract_002(unauthenticated)

    no_csrf = await api.post(
        "/api/v1/me/imports",
        json={"author_key": KEY, "work_keys": ["OL1W"]},
        headers={"X-CSRF-Token": ""},
    )
    assert no_csrf.status_code == 403
    matches_contract_002(no_csrf)

    unknown = await api.get("/api/v1/import/authors/OL999A/works")
    assert unknown.status_code == 404 and unknown.json()["code"] == "author_not_found"
    matches_contract_002(unknown)

    too_many = await api.post(
        "/api/v1/me/imports",
        json={"author_key": KEY, "work_keys": [f"OL{n}W" for n in range(1, 502)]},
    )
    assert too_many.status_code == 422
    matches_contract_002(too_many)

    await api.get(WORKS_URL)
    app.state.clock = lambda: _later()  # type: ignore[attr-defined]  # past the 24 h cache
    expired = await api.post("/api/v1/me/imports", json={"author_key": KEY, "work_keys": ["OL1W"]})
    assert expired.status_code == 409 and expired.json()["code"] == "results_expired"
    matches_contract_002(expired)

    book_source.error = SourceUnavailable()
    down = await api.get("/api/v1/import/authors", params={"q": "someone new"})
    assert down.status_code == 503 and down.json()["code"] == "source_unavailable"
    matches_contract_002(down)


def _later():  # type: ignore[no-untyped-def]  # tiny clock helper
    from datetime import UTC, datetime

    return datetime.now(UTC) + timedelta(hours=25)
