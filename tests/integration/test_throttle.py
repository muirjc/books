"""T063: sign-in is throttled per login (FR-027); covers auth/throttle.py."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from book_tracker.auth import throttle
from tests.conftest import DEFAULT_PASSWORD, TEST_SECRET, Factory, api_login


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock(app: Any) -> FakeClock:
    fake = FakeClock()
    app.state.clock = fake
    return fake


async def fail(client: httpx.AsyncClient, login: str, times: int = 1) -> httpx.Response:
    response: httpx.Response | None = None
    for _ in range(times):
        response = await api_login(client, login, "wrong-password")
    assert response is not None
    return response


@pytest.mark.ac("001/AC-33")
async def test_locks_after_five_failures(
    client: httpx.AsyncClient, factory: Factory, clock: FakeClock
) -> None:
    await factory.user("ben")
    fourth = await fail(client, "ben", 4)
    assert fourth.status_code == 401
    fifth = await fail(client, "ben")
    assert fifth.status_code == 401
    locked = await api_login(client, "ben", DEFAULT_PASSWORD)
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) == 15 * 60
    assert "try again later" in locked.json()["title"].lower()
    clock.advance(minutes=14, seconds=59)
    assert (await api_login(client, "ben", DEFAULT_PASSWORD)).status_code == 429
    clock.advance(seconds=2)
    assert (await api_login(client, "ben", DEFAULT_PASSWORD)).status_code == 200


@pytest.mark.ac("001/AC-33")
async def test_unknown_login_behaves_the_same(
    client: httpx.AsyncClient, factory: Factory, clock: FakeClock
) -> None:
    await factory.user("ben")
    real = [await api_login(client, "ben", "nope") for _ in range(6)]
    fake = [await api_login(client, "nobody", "nope") for _ in range(6)]
    assert [r.status_code for r in real] == [r.status_code for r in fake]
    assert [r.json() for r in real] == [r.json() for r in fake]
    assert real[-1].status_code == 429


async def test_success_resets_the_count(
    client: httpx.AsyncClient, factory: Factory, clock: FakeClock
) -> None:
    await factory.user("ben")
    await fail(client, "ben", 4)
    assert (await api_login(client, "ben")).status_code == 200
    await fail(client, "ben", 4)
    assert (await api_login(client, "ben")).status_code == 200


async def test_attempts_during_lock_are_not_counted(
    client: httpx.AsyncClient, factory: Factory, clock: FakeClock
) -> None:
    await factory.user("ben")
    await fail(client, "ben", 5)
    clock.advance(minutes=10)
    for _ in range(10):
        assert (await fail(client, "ben")).status_code == 429
    clock.advance(minutes=5, seconds=1)  # the original 15 minutes are up
    assert (await api_login(client, "ben")).status_code == 200


async def test_ui_shows_the_same_message(
    client: httpx.AsyncClient, factory: Factory, clock: FakeClock
) -> None:
    await factory.user("ben")
    await fail(client, "ben", 5)
    page = await client.get("/sign-in")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert token
    response = await client.post(
        "/sign-in",
        data={"login": "ben", "password": DEFAULT_PASSWORD, "csrf_token": token.group(1)},
    )
    assert response.status_code == 429
    assert "try again later" in html.unescape(response.text).lower()


async def test_old_rows_are_pruned(
    app: Any, factory: Factory, clock: FakeClock, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    await factory.user("ben")
    await fail(client_factory(), "ben", 2)
    assert await factory.scalar("SELECT count(*) FROM login_throttle") == 1
    clock.advance(hours=25)
    await api_login(client_factory(), "someone-else", "x")
    keys = await factory.scalar("SELECT count(*) FROM login_throttle")
    assert keys == 1  # only the new failure remains


async def test_login_text_is_never_stored(
    factory: Factory, clock: FakeClock, client: httpx.AsyncClient
) -> None:
    await fail(client, "Someone.Outside@example.org", 1)
    key = await factory.scalar("SELECT login_key FROM login_throttle")
    assert key == throttle.login_key(TEST_SECRET, "  someone.outside@EXAMPLE.org ")
    assert "example" not in key and "@" not in key
    assert len(key) == 64


async def test_check_allowed_without_row(app: Any, clock: FakeClock) -> None:
    async with app.state.db.sessionmaker() as db:
        assert await throttle.check_allowed(db, "0" * 64, clock()) is None
