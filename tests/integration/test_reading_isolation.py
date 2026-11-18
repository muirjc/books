"""T048: a member can never see or change another member's entries (AC-04, Principle I)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, signed_in


@pytest.fixture
async def setup(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> dict[str, Any]:
    alice = await factory.user("alice")
    ben = await factory.user("ben")
    book = await factory.book("Shared Book", alice)
    other = await factory.book("Ben Only", ben)
    alice_entry = await factory.entry(alice, book, notes="alice notes")
    ben_entry = await factory.entry(ben, other, notes="ben secret notes")
    client = await signed_in(client_factory(), alice)
    return {"client": client, "alice_entry": alice_entry, "ben_entry": ben_entry}


@pytest.mark.ac("001/AC-04")
async def test_list_shows_only_own(setup: dict[str, Any]) -> None:
    response = await setup["client"].get("/api/v1/me/readings")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(setup["alice_entry"])}
    assert "ben secret notes" not in response.text


API_CASES = [
    ("GET", "/api/v1/me/readings/{id}", None),
    ("PATCH", "/api/v1/me/readings/{id}", {"notes": "changed"}),
    ("DELETE", "/api/v1/me/readings/{id}", None),
    ("POST", "/api/v1/me/readings/{id}/read-again", None),
]


@pytest.mark.ac("001/AC-04")
@pytest.mark.parametrize("method,path,body", API_CASES)
async def test_api_other_members_entry_is_not_found(
    setup: dict[str, Any], factory: Factory, method: str, path: str, body: Any
) -> None:
    client: httpx.AsyncClient = setup["client"]
    theirs = await client.request(method, path.format(id=setup["ben_entry"]), json=body)
    missing = await client.request(method, path.format(id=uuid.uuid4()), json=body)
    assert theirs.status_code == missing.status_code == 404
    assert theirs.content == missing.content
    notes = await factory.scalar(
        "SELECT notes FROM reading_entry WHERE id = :id", id=setup["ben_entry"]
    )
    assert notes == "ben secret notes"


UI_CASES = [
    ("GET", "/entries/{id}", None),
    ("POST", "/entries/{id}", {"status": "reading", "notes": "changed"}),
    ("POST", "/entries/{id}/read-again", {}),
    ("POST", "/entries/{id}/remove", {"confirm": "yes"}),
]


@pytest.mark.ac("001/AC-04")
@pytest.mark.parametrize("method,path,form", UI_CASES)
async def test_pages_other_members_entry_is_not_found(
    setup: dict[str, Any], factory: Factory, method: str, path: str, form: Any
) -> None:
    client: httpx.AsyncClient = setup["client"]
    theirs = await client.request(method, path.format(id=setup["ben_entry"]), data=form)
    missing = await client.request(method, path.format(id=uuid.uuid4()), data=form)
    assert theirs.status_code == missing.status_code == 404
    assert theirs.text == missing.text
    assert "ben secret notes" not in theirs.text
    count = await factory.scalar(
        "SELECT count(*) FROM reading_entry WHERE id = :id", id=setup["ben_entry"]
    )
    assert count == 1
