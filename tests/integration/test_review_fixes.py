"""Regression tests for the PR #1 code review findings."""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import Request

from book_tracker.persistence import catalog
from book_tracker.persistence.db import DbSession
from book_tracker.web.rendering import render_error
from tests.conftest import Factory, TestUser, api_login, gather, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


async def author_names(factory: Factory, book: object) -> list[str]:
    async with factory._app.state.db.sessionmaker() as db:
        from sqlalchemy import text

        rows = await db.execute(
            text(
                "SELECT a.name FROM book_author ba JOIN author a ON a.id = ba.author_id "
                "WHERE ba.book_id = :b ORDER BY ba.position"
            ),
            {"b": book},
        )
        return [r[0] for r in rows]


# 1 ------------------------------------------------------------------- authors beyond 3


async def test_edit_book_keeps_every_author(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    ids = [await factory.author(f"Author {n}", alice) for n in range(1, 6)]
    book = await factory.book("Anthology", alice, author_ids=ids)
    page = (await member.get(f"/catalog/books/{book}/edit")).text
    for n in range(5):
        assert f'id="author_name_{n}"' in page
    form: dict[str, str] = {"title": "Anthology (revised)"}
    for n, author in enumerate(ids):
        form[f"author_name_{n}"] = f"Author {n + 1}"
        form[f"author_id_{n}"] = str(author)
    saved = await member.post(f"/catalog/books/{book}/edit", data=form)
    assert saved.status_code == 303
    assert await author_names(factory, book) == [f"Author {n}" for n in range(1, 6)]


# 2 ------------------------------------------------------------------- spaces in names


async def test_extra_spaces_still_match_the_existing_author(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    existing = await factory.author("J.K. Rowling", alice)
    first = await member.post(
        "/books/add", data={"title": "Book", "author_name_0": "J.K.  Rowling"}
    )
    assert first.status_code == 409
    chosen = await member.post(
        "/books/add",
        data={"title": "Book", "author_name_0": "J.K.  Rowling", "author_id_0": str(existing)},
    )
    assert chosen.status_code == 303
    assert await factory.scalar("SELECT count(*) FROM author") == 1


# 3 ------------------------------------------------------------------- cookie slides


def session_cookie(response: httpx.Response) -> str | None:
    return next(
        (c for c in response.headers.get_list("set-cookie") if c.startswith("__Host-session=")),
        None,
    )


async def test_session_cookie_lifetime_slides_with_use(
    app: Any, alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    start = datetime.now(UTC)
    app.state.clock = lambda: start
    client = await signed_in(client_factory(), alice)
    app.state.clock = lambda: start + timedelta(seconds=30)
    assert session_cookie(await client.get("/api/v1/me")) is None  # not touched yet
    app.state.clock = lambda: start + timedelta(minutes=5)
    refreshed = session_cookie(await client.get("/api/v1/me"))
    assert refreshed is not None
    assert "max-age=1209600" in refreshed.lower()
    assert "httponly" in refreshed.lower() and "secure" in refreshed.lower()
    app.state.clock = lambda: start + timedelta(minutes=10)
    logout = await client.post("/api/v1/auth/logout")
    cleared = session_cookie(logout)
    assert cleared is not None and ("max-age=0" in cleared.lower() or "expires" in cleared.lower())
    assert "max-age=1209600" not in cleared.lower()


# 4 ------------------------------------------------------------------- throttle race


async def test_parallel_wrong_passwords_still_lock(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    await factory.user("ben")
    clients = [client_factory() for _ in range(12)]
    responses = await gather(*(api_login(c, "ben", "wrong-password") for c in clients))
    statuses = sorted(r.status_code for r in responses)
    # Exactly 5 guesses get a password check; the other 7 are refused by the lock.
    assert statuses == [401] * 5 + [429] * 7, statuses
    locked = await api_login(client_factory(), "ben")
    assert locked.status_code == 429


# 5 ------------------------------------------------------------------- one "today"


async def test_auto_date_uses_the_same_today_as_validation(
    app: Any, member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    local = datetime.now().astimezone()
    offset = local.utcoffset() or timedelta(0)
    # An instant where the UTC date and the local date differ (when the zone isn't UTC).
    if offset < timedelta(0):
        instant = local.replace(hour=23, minute=30, second=0, microsecond=0)
    else:
        instant = local.replace(hour=0, minute=30, second=0, microsecond=0)
    app.state.clock = lambda: instant.astimezone(UTC)
    book = await factory.book("Dune", alice)
    entry = await factory.entry(alice, book, status="reading")
    done = await member.patch(f"/api/v1/me/readings/{entry}", json={"status": "finished"})
    assert done.json()["finished_on"] == instant.date().isoformat()
    again = await member.patch(
        f"/api/v1/me/readings/{entry}",
        json={"finished_on": done.json()["finished_on"], "notes": "edited later"},
    )
    assert again.status_code == 200


# 6 ------------------------------------------------------------------- remove without JS


async def test_blank_name_removes_series_and_author_without_js(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    first = await factory.author("First", alice)
    second = await factory.author("Second", alice)
    series = await factory.series("Discworld", alice)
    book = await factory.book(
        "Mort", alice, author_ids=[first, second], series_id=series, series_number="4"
    )
    saved = await member.post(
        f"/catalog/books/{book}/edit",
        data={
            "title": "Mort",
            "author_name_0": "First",
            "author_id_0": str(first),
            "author_name_1": "",
            "author_id_1": str(second),
            "series_name": "",
            "series_id": str(series),
            "series_number": "",
        },
    )
    assert saved.status_code == 303
    assert await factory.scalar("SELECT series_id FROM book WHERE id = :b", b=book) is None
    assert await author_names(factory, book) == ["First"]


# 7 ------------------------------------------------------------------- per-field messages


async def test_edit_author_shows_each_fields_own_error(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    author = await factory.author("Someone", alice)
    response = await member.post(
        f"/catalog/authors/{author}/edit", data={"name": "", "sort_name": "x" * 201}
    )
    assert response.status_code == 422
    text = html.unescape(response.text)
    name_error = text.split('id="name-error">')[1].split("</p>")[0]
    sort_error = text.split('id="sort_name-error">')[1].split("</p>")[0]
    assert name_error != sort_error
    assert "200" in sort_error


# 8 ------------------------------------------------------------------- no 500s


async def test_stale_author_id_without_name_is_a_form_error(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    response = await member.post("/books/add", data={"title": "Book", "author_id_0": missing})
    assert response.status_code == 422
    assert "Enter at least one author" in response.text
    book = await factory.book("Kept", alice)
    edit = await member.post(
        f"/catalog/books/{book}/edit", data={"title": "Kept", "author_id_0": missing}
    )
    assert edit.status_code == 422
    assert len(await author_names(factory, book)) == 1


async def test_api_refuses_an_empty_author_list(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    book = await factory.book("Kept", alice)
    response = await member.patch(f"/api/v1/books/{book}", json={"author_ids": []})
    assert response.status_code == 422
    assert len(await author_names(factory, book)) == 1


# 9 ------------------------------------------------------------------- no half-commits


async def test_error_pages_never_commit_partial_writes(
    app: Any, member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    """A page shown with a 4xx status rolls back, even if the handler doesn't."""
    probe = app.router

    @probe.post("/_probe/partial-write", include_in_schema=False)
    async def partial(request: Request, db: DbSession) -> Any:
        await catalog.create_series(db, name="Half done", actor_id=alice.id)
        return render_error(request, 409, "Something conflicted")

    try:
        response = await member.post("/_probe/partial-write")
        assert response.status_code == 409
        assert await factory.scalar("SELECT count(*) FROM series") == 0
    finally:
        probe.routes[:] = [
            r for r in probe.routes if getattr(r, "path", "") != "/_probe/partial-write"
        ]
