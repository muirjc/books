"""Spec 002 import pages: WCAG 2.2 AA, keyboard, phone width, and real server limits (T046).

These run against the live uvicorn server with ``FakeBookSource`` injected, so no request
reaches Open Library (research R14).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from book_tracker.domain.imports import AuthorCandidate
from book_tracker.services.errors import SourceUnavailable
from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_keyboard_journeys import press_button, tab_to
from tests.a11y.test_responsive import check
from tests.conftest import Factory
from tests.fakes import FakeBookSource, listing, work

pytestmark = pytest.mark.a11y
KEY = "OL1A"


@pytest.fixture
def ol(live_book_source: FakeBookSource) -> Iterator[FakeBookSource]:
    live_book_source.authors["ann author"] = [
        AuthorCandidate(KEY, "Ann Author", "1950", None, "Book 1", 30),
        AuthorCandidate("OL2A", "Ann Author", None, "2001", "Other Book", 2),
    ]
    live_book_source.works[KEY] = listing(KEY, [work(n, f"Book {n}") for n in range(1, 31)])
    yield live_book_source
    live_book_source.authors.clear()
    live_book_source.works.clear()
    live_book_source.error = None


@pytest.mark.ac("002/AC-01")
@pytest.mark.ac("002/AC-08")
async def test_import_pages_pass_axe(ui: UI, seeded: Seeded, ol: FakeBookSource) -> None:
    await ui.sign_in(seeded.alice)
    pages = {
        "search": "/import",
        "author choice": "/import/authors?q=Ann+Author",
        "no author": "/import/authors?q=nobody",
        "works": f"/import/authors/{KEY}",
        "works sorted": f"/import/authors/{KEY}?sort=year&q=Book+1",
        "unknown author": "/import/authors/OL999A",
    }
    for label, path in pages.items():
        await ui.go(path)
        await assert_no_axe_violations(ui.page, label)
    await ui.go(f"/import/authors/{KEY}")
    await ui.page.check("#work-OL1W")
    await ui.page.click("text=Add ticked books to my list")
    await ui.page.wait_for_load_state()
    await assert_no_axe_violations(ui.page, "summary")
    ol.error = SourceUnavailable()
    await ui.page.goto(ui.base_url + "/import/authors?q=someone+else")
    await assert_no_axe_violations(ui.page, "unreachable")


@pytest.mark.ac("002/AC-02")
async def test_import_with_the_keyboard_only(
    ui: UI, seeded: Seeded, ol: FakeBookSource, factory: Factory
) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/import/authors/{KEY}")
    await tab_to(ui.page, "status", limit=60)
    await ui.page.keyboard.press("ArrowDown")  # Finished → Reading
    await tab_to(ui.page, "work-OL1W", limit=60)
    await ui.page.keyboard.press("Space")
    await ui.page.keyboard.press("Tab")
    await ui.page.keyboard.press("Space")  # OL10W, next in title order
    await press_button(ui.page, "Add ticked books to my list", limit=200)
    assert "Added 2 books to your list" in await ui.page.content()
    statuses = await factory.scalar("SELECT array_agg(DISTINCT status) FROM reading_entry "
                                    "WHERE user_id = :u", u=seeded.alice.id)  # fmt: skip
    assert "reading" in statuses


async def test_works_page_at_phone_width(ui: UI, seeded: Seeded, ol: FakeBookSource) -> None:
    await ui.page.set_viewport_size({"width": 360, "height": 740})
    await ui.sign_in(seeded.alice)
    for label, path in {"search": "/import", "works": f"/import/authors/{KEY}",
                        "choice": "/import/authors?q=Ann+Author"}.items():  # fmt: skip
        await ui.go(path)
        await check(ui.page, label)


@pytest.mark.ac("002/AC-21")
async def test_500_books_confirm_through_the_real_server(
    ui: UI, seeded: Seeded, ol: FakeBookSource, factory: Factory
) -> None:
    """500 ticks fit uvicorn/h11's header limit and Starlette's 1,000-field form limit."""
    ol.works[KEY] = listing(KEY, [work(n, f"Volume {n}") for n in range(1, 501)])
    await ui.sign_in(seeded.ben)
    await ui.go(f"/import/authors/{KEY}")
    await ui.page.click("text=Select all shown")
    await ui.page.wait_for_selector("#work-OL500W:checked")
    async with ui.page.expect_navigation():
        await ui.page.click("text=Add ticked books to my list")
    assert "Added 500 books to your list" in await ui.page.content()
    count: Any = await factory.scalar(
        "SELECT count(*) FROM reading_entry WHERE user_id = :u", u=seeded.ben.id
    )
    assert count == 500


async def test_works_columns_are_the_same_for_every_author(
    ui: UI, seeded: Seeded, ol: FakeBookSource
) -> None:
    """Column widths don't depend on what each author's titles and co-authors are."""
    ol.works["OL2A"] = listing("OL2A", [
        work(n, f"A Very Long Title For Book {n}, Being The Complete And Unabridged Edition "
                "With Notes, Appendices And A Foreword", tuple(f"Co-Author Number {i}"
                                                               for i in range(6)), year=None)
        for n in range(100, 110)
    ])  # fmt: skip
    await ui.page.set_viewport_size({"width": 1024, "height": 768})
    await ui.sign_in(seeded.alice)
    widths = []
    for key in (KEY, "OL2A"):
        await ui.go(f"/import/authors/{key}")
        widths.append(await ui.page.eval_on_selector_all(
            ".import-table thead th", "ths => ths.map(th => Math.round(th.offsetWidth))"
        ))  # fmt: skip
    assert widths[0] == widths[1], widths
