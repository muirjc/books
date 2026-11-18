"""T049: adding, editing, re-reading and removing entries, through the JSON API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, gather, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def api(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


async def new_author(api: httpx.AsyncClient, name: str = "J.R.R. Tolkien") -> str:
    response = await api.post("/api/v1/authors", json={"name": name})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def counts(factory: Factory) -> tuple[int, int, int, int]:
    return (
        await factory.scalar("SELECT count(*) FROM book"),
        await factory.scalar("SELECT count(*) FROM author"),
        await factory.scalar("SELECT count(*) FROM series"),
        await factory.scalar("SELECT count(*) FROM reading_entry"),
    )


@pytest.mark.ac("001/AC-03")
async def test_add_with_title_and_author_only(api: httpx.AsyncClient) -> None:
    author = await new_author(api)
    response = await api.post(
        "/api/v1/me/readings", json={"new_book": {"title": "The Hobbit", "author_ids": [author]}}
    )
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["book"]["series"] is None
    assert entry["book"]["series_number"] is None
    assert entry["book"]["authors"][0]["name"] == "J.R.R. Tolkien"
    listed = (await api.get("/api/v1/me/readings")).json()
    assert [item["book"]["title"] for item in listed["items"]] == ["The Hobbit"]


@pytest.mark.ac("001/AC-05")
async def test_duplicate_is_refused(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    first = await api.post("/api/v1/me/readings", json={"book_id": str(book)})
    assert first.status_code == 201
    before = await counts(factory)
    again = await api.post("/api/v1/me/readings", json={"book_id": str(book)})
    assert again.status_code == 409
    body = again.json()
    assert body["code"] == "already_on_list"
    assert body["title"] == "Already on your list"
    assert body["existing_id"] == first.json()["id"]
    assert await counts(factory) == before


@pytest.mark.ac("001/AC-06")
async def test_number_without_series_saves_nothing(
    api: httpx.AsyncClient, factory: Factory
) -> None:
    author = await new_author(api)
    before = await counts(factory)
    response = await api.post(
        "/api/v1/me/readings",
        json={"new_book": {"title": "Book", "author_ids": [author], "series_number": "2"}},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "new_book.series_number"
    assert await counts(factory) == before


async def test_unknown_book_is_not_found(api: httpx.AsyncClient) -> None:
    response = await api.post(
        "/api/v1/me/readings", json={"book_id": "00000000-0000-4000-8000-000000000000"}
    )
    assert response.status_code == 404


async def test_unknown_author_is_a_validation_error(api: httpx.AsyncClient) -> None:
    response = await api.post(
        "/api/v1/me/readings",
        json={
            "new_book": {"title": "Book", "author_ids": ["00000000-0000-4000-8000-000000000000"]}
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "new_book.author_ids"


@pytest.mark.ac("001/AC-07")
async def test_remove_keeps_catalog_and_others(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    ben = await factory.user("ben")
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book)
    ben_entry = await factory.entry(ben, book)
    response = await api.delete(f"/api/v1/me/readings/{entry}")
    assert response.status_code == 204
    assert (await api.get(f"/api/v1/me/readings/{entry}")).status_code == 404
    assert await factory.scalar("SELECT count(*) FROM book WHERE id = :id", id=book) == 1
    assert (
        await factory.scalar("SELECT count(*) FROM reading_entry WHERE id = :id", id=ben_entry) == 1
    )


@pytest.mark.ac("001/AC-08")
async def test_status_date_and_notes_are_private(
    api: httpx.AsyncClient,
    factory: Factory,
    alice: TestUser,
    client_factory: Callable[[], httpx.AsyncClient],
) -> None:
    ben = await factory.user("ben")
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book, status="reading")
    await factory.entry(ben, book)
    response = await api.patch(
        f"/api/v1/me/readings/{entry}",
        json={"status": "finished", "finished_on": "2026-01-15", "notes": "Loved the sandworms"},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["finished_on"], body["notes"]) == (
        "finished",
        "2026-01-15",
        "Loved the sandworms",
    )
    ben_api = await signed_in(client_factory(), ben)
    ben_list = await ben_api.get("/api/v1/me/readings")
    assert "sandworms" not in ben_list.text
    assert ben_list.json()["items"][0]["notes"] is None


@pytest.mark.ac("001/AC-31")
async def test_default_status_and_future_date(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    added = (await api.post("/api/v1/me/readings", json={"book_id": str(book)})).json()
    assert (added["status"], added["times_read"]) == ("finished", 1)
    other = await factory.book("Emma", alice)
    want = (
        await api.post(
            "/api/v1/me/readings", json={"book_id": str(other), "status": "want_to_read"}
        )
    ).json()
    assert want["times_read"] == 0
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    future = await api.patch(f"/api/v1/me/readings/{added['id']}", json={"finished_on": tomorrow})
    assert future.status_code == 422
    assert future.json()["errors"][0]["field"] == "finished_on"


@pytest.mark.ac("001/AC-35")
async def test_read_again_then_finish(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book, finished_on=date(2025, 5, 1))
    again = (await api.post(f"/api/v1/me/readings/{entry}/read-again")).json()
    assert (again["status"], again["times_read"], again["finished_on"]) == (
        "reading",
        1,
        "2025-05-01",
    )
    done = (
        await api.patch(
            f"/api/v1/me/readings/{entry}", json={"status": "finished", "finished_on": "2026-02-01"}
        )
    ).json()
    assert (done["status"], done["times_read"], done["finished_on"]) == (
        "finished",
        2,
        "2026-02-01",
    )
    listed = (await api.get("/api/v1/me/readings")).json()
    assert listed["total"] == 1


async def test_finishing_without_a_date_uses_today(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book, status="reading")
    done = (await api.patch(f"/api/v1/me/readings/{entry}", json={"status": "finished"})).json()
    assert done["finished_on"] == date.today().isoformat()
    assert done["times_read"] == 1


async def test_remove_then_add_again_is_fresh(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book, status="reading", notes="old notes")
    await api.delete(f"/api/v1/me/readings/{entry}")
    again = await api.post("/api/v1/me/readings", json={"book_id": str(book)})
    assert again.status_code == 201
    body = again.json()
    assert body["notes"] is None
    assert body["status"] == "finished"
    assert body["id"] != str(entry)


@pytest.mark.ac("001/AC-16")
async def test_duplicate_author_and_series_names(api: httpx.AsyncClient, factory: Factory) -> None:
    author = await new_author(api, "Robert Galbraith")
    series = (await api.post("/api/v1/series", json={"name": "Cormoran Strike"})).json()
    before = await counts(factory)
    dup_author = await api.post("/api/v1/authors", json={"name": "robert  galbraith"})
    assert dup_author.status_code == 409
    assert dup_author.json()["code"] == "author_exists"
    assert dup_author.json()["existing_id"] == author
    assert dup_author.json()["existing_label"] == "Robert Galbraith"
    dup_series = await api.post("/api/v1/series", json={"name": "CORMORAN STRIKE"})
    assert dup_series.status_code == 409
    assert dup_series.json()["code"] == "series_exists"
    assert dup_series.json()["existing_id"] == series["id"]
    assert await counts(factory) == before


@pytest.mark.ac("001/AC-19")
async def test_series_number_taken(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    series = await factory.series("Strike", alice)
    existing = await factory.book("Troubled Blood", alice, series_id=series, series_number="5")
    author = await new_author(api)
    before = await counts(factory)
    response = await api.post(
        "/api/v1/me/readings",
        json={
            "new_book": {
                "title": "Other",
                "author_ids": [author],
                "series_id": str(series),
                "series_number": "5",
            }
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "series_number_taken"
    assert body["existing_id"] == str(existing)
    assert body["existing_label"] == "Troubled Blood"
    assert await counts(factory) == before


@pytest.mark.ac("001/AC-30")
async def test_isbn_already_in_catalog(
    api: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    existing = await factory.book("Existing", alice, isbn_13="9780306406157")
    author = await new_author(api)
    before = await counts(factory)
    response = await api.post(
        "/api/v1/me/readings",
        json={
            "new_book": {"title": "Copy", "author_ids": [author], "isbn_13": "978-0-306-40615-7"}
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "isbn_exists"
    assert response.json()["existing_id"] == str(existing)
    assert await counts(factory) == before
    invalid = await api.post(
        "/api/v1/me/readings",
        json={"new_book": {"title": "Copy", "author_ids": [author], "isbn_13": "9780306406158"}},
    )
    assert invalid.status_code == 422


@pytest.mark.ac("001/AC-16")
async def test_concurrent_author_creates_leave_one_row(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    alice, ben = await factory.user("alice2"), await factory.user("ben2")
    a = await signed_in(client_factory(), alice)
    b = await signed_in(client_factory(), ben)
    responses: list[Any] = await gather(
        a.post("/api/v1/authors", json={"name": "Ann Leckie"}),
        b.post("/api/v1/authors", json={"name": "Ann Leckie"}),
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409]
    winner = next(r for r in responses if r.status_code == 201).json()
    loser = next(r for r in responses if r.status_code == 409).json()
    assert loser["existing_id"] == winner["id"]
    assert await factory.scalar("SELECT count(*) FROM author") == 1
