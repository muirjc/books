"""T104: browser fixtures for accessibility tests (marker ``a11y``).

A second app instance runs under uvicorn in a background thread (its own event loop and
database pool) against the same test database. Tests drive it with Playwright's async API
and check pages with axe-core for WCAG 2.2 AA.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import uvicorn
from axe_playwright_python.async_playwright import Axe
from playwright.async_api import Browser, Page, async_playwright

from book_tracker.main import create_app
from book_tracker.settings import Settings
from tests.conftest import Factory, TestUser
from tests.fakes import FakeBookSource, FakeSummaryGenerator

WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
_axe = Axe()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def live_book_source() -> FakeBookSource:
    """The live server's Open Library: a fake, so these tests never call the real one
    (spec 002 research R14). Tests fill it in and should clear what they add."""
    return FakeBookSource()


@pytest.fixture(scope="session")
def live_summary_generator() -> FakeSummaryGenerator:
    """The live server's AI: a fake (spec 012). Tests script it and should reset it."""
    return FakeSummaryGenerator()


@pytest.fixture(scope="session")
def live_server(
    settings: Settings,
    database_url: str,
    live_book_source: FakeBookSource,
    live_summary_generator: FakeSummaryGenerator,
) -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(
        create_app(
            settings, book_source=live_book_source, summary_generator=live_summary_generator
        ),
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:  # pragma: no cover - start-up failure
            raise RuntimeError("live server did not start")
        time.sleep(0.05)
    # localhost is a secure context, so __Host- (Secure) cookies work over plain HTTP.
    yield f"http://localhost:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="session")
async def pw_browser() -> AsyncIterator[Browser]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        yield browser
        await browser.close()


@dataclass
class UI:
    page: Page
    base_url: str

    async def go(self, path: str) -> None:
        response = await self.page.goto(self.base_url + path)
        assert response is not None and response.status < 500, path

    async def sign_in(self, user: TestUser) -> None:
        await self.go("/sign-in")
        await self.page.fill("#login", user.login)
        await self.page.fill("#password", user.password)
        await self.page.click("button[type=submit]")
        await self.page.wait_for_load_state()


@pytest.fixture
async def ui(pw_browser: Browser, live_server: str, app: Any) -> AsyncIterator[UI]:
    context = await pw_browser.new_context(viewport={"width": 1024, "height": 768})
    page = await context.new_page()
    yield UI(page, live_server)
    await context.close()


async def assert_no_axe_violations(page: Page, label: str = "") -> None:
    results = await _axe.run(page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}})
    assert results.violations_count == 0, f"{label or page.url}\n{results.generate_report()}"


@dataclass
class Seeded:
    admin: TestUser
    alice: TestUser
    ben: TestUser
    forced: TestUser
    book_id: str
    entry_id: str
    series_id: str
    author_id: str


@pytest.fixture
async def seeded(factory: Factory) -> Seeded:
    admin = await factory.user("parent", role="admin", display_name="Parent")
    alice = await factory.user("alice", display_name="Alice")
    ben = await factory.user("ben", display_name="Ben")
    forced = await factory.user(
        "newkid", display_name="New Kid", must_change_password=True, password="temporary-1"
    )
    author = await factory.author("Terry Pratchett", alice, sort_name="Pratchett, Terry")
    series = await factory.series("Discworld", alice)
    mort = await factory.book(
        "Mort", alice, author_ids=[author], series_id=series, series_number="4"
    )
    colour = await factory.book(
        "The Colour of Magic", alice, author_ids=[author], series_id=series, series_number="1"
    )
    entry = await factory.entry(alice, mort, notes="Death takes an apprentice.")
    await factory.entry(alice, colour, status="reading")
    await factory.execute(
        "INSERT INTO book_summary (id, book_id, text, origin, created_by, is_current) "
        "VALUES (gen_random_uuid(), :b, 'Death takes an apprentice.', 'manual', :u, true)",
        b=mort,
        u=alice.id,
    )
    return Seeded(admin, alice, ben, forced, str(mort), str(entry), str(series), str(author))
