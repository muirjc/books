"""T098: summary endpoints match contracts/openapi.yaml."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, signed_in
from tests.contract.conftest import assert_matches_contract


@pytest.mark.ac("001/AC-24")
@pytest.mark.ac("001/AC-25")
async def test_summaries(factory: Factory, client_factory: Callable[[], httpx.AsyncClient]) -> None:
    alice = await factory.user("alice")
    api = await signed_in(client_factory(), alice)
    book = await factory.book("The Hobbit", alice)
    saved = await api.post(f"/api/v1/books/{book}/summaries", json={"text": "An adventure."})
    assert saved.status_code == 201
    assert_matches_contract(saved)
    await api.post(f"/api/v1/books/{book}/summaries", json={"text": "A better summary."})
    history = await api.get(f"/api/v1/books/{book}/summaries")
    assert history.status_code == 200
    assert_matches_contract(history)
    with_summary = await api.get(f"/api/v1/books/{book}")
    assert_matches_contract(with_summary)
    for response in (
        await api.post(f"/api/v1/books/{book}/summaries", json={"text": ""}),
        await api.post(f"/api/v1/books/{book}/summaries", json={"text": "x" * 5001}),
    ):
        assert response.status_code == 422
        assert_matches_contract(response)
    missing = await api.get("/api/v1/books/00000000-0000-4000-8000-000000000000/summaries")
    assert missing.status_code == 404
    assert_matches_contract(missing)
