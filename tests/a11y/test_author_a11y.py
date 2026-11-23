"""Spec 011 (AC-18): the Author page and My favorite authors in a real browser."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from playwright.async_api import Browser, expect

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

LONG_TITLE = (
    "An Extraordinarily Long and Winding Title for a Discworld Book That Keeps Going Past Any "
    "Reasonable Length"
)


@pytest.fixture
async def author(seeded: Seeded, factory: Factory) -> Seeded:
    """Seeded Discworld (Alice: #1 Reading, #4 Finished) plus an upcoming long title, a book
    in no series, and a story."""
    series, pratchett = uuid.UUID(seeded.series_id), uuid.UUID(seeded.author_id)
    await factory.book(
        LONG_TITLE, seeded.ben, author_ids=[pratchett], series_id=series, series_number="9",
        release_date=date.today() + timedelta(days=40),
    )  # fmt: skip
    blink = await factory.book("A Blink of the Screen", seeded.ben, author_ids=[pratchett])
    await factory.story(
        "Troll Bridge", seeded.ben, series_id=series, series_number="1.5",
        author_ids=[pratchett], book_ids=[blink],
    )  # fmt: skip
    return seeded


async def _targets(ui: UI, where: str) -> None:
    for found in await ui.page.eval_on_selector_all(
        ".catalog-list .book-title, .catalog-list .series-action, .catalog-mine, "
        ".favorite-form button, .link-list a",
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {name: e.textContent.trim(), w: r.width, h: r.height}; })",
    ):
        assert found["h"] >= 44 and found["w"] >= 44, (where, found)


@pytest.mark.ac("011/AC-18")
async def test_author_pages_layout(ui: UI, author: Seeded, factory: Factory) -> None:
    await ui.sign_in(author.alice)
    pages = {"author": f"/authors/{author.author_id}", "favorites (none)": "/authors/favorites"}
    for name, path in pages.items():
        await ui.go(path)
        for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
            await size(ui.page, wh)
            await check(ui.page, f"{name} {wh}")
            await _targets(ui, f"{name} {wh}")
            if wh in (PHONE, IPAD, LAPTOP):
                await assert_no_axe_violations(ui.page, f"{name} {wh}")
    await factory.favorite(author.alice, uuid.UUID(author.author_id))
    for path in (f"/authors/{author.author_id}?msg=favorited", "/authors/favorites"):
        await ui.go(path)
        for wh in (SMALL, LAPTOP):
            await size(ui.page, wh)
            await check(ui.page, f"{path} {wh}")
            await assert_no_axe_violations(ui.page, f"{path} {wh}")


@pytest.mark.ac("011/AC-18")
async def test_favorite_by_keyboard(ui: UI, author: Seeded) -> None:
    await ui.sign_in(author.alice)
    await ui.go("/")
    link = ui.page.locator(".reading-list a", has_text="Terry Pratchett").first
    await link.focus()
    await ui.page.keyboard.press("Enter")
    await ui.page.wait_for_url(f"**/authors/{author.author_id}")
    await ui.page.get_by_role("button", name="Add to my favorite authors").focus()
    await ui.page.keyboard.press("Enter")
    await ui.page.wait_for_url("**msg=favorited")
    await expect(ui.page.get_by_role("status")).to_have_text("Added to your favorite authors.")
    await expect(ui.page.get_by_text("One of your favorite authors")).to_be_visible()
    await ui.page.get_by_role("link", name="My favorite authors").focus()
    await ui.page.keyboard.press("Enter")
    await ui.page.wait_for_url("**/authors/favorites")
    await expect(ui.page.locator("main .link-list a")).to_have_text(["Terry Pratchett"])


@pytest.mark.ac("011/AC-18")
async def test_favorite_without_js(author: Seeded, pw_browser: Browser, live_server: str) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(author.alice)
    await view.go(f"/authors/{author.author_id}")
    await view.page.get_by_role("button", name="Add to my favorite authors").click()
    await view.page.wait_for_load_state()
    assert "msg=favorited" in view.page.url
    await view.page.get_by_role("button", name="Remove from my favorite authors").click()
    await view.page.wait_for_load_state()
    assert "msg=unfavorited" in view.page.url
    await view.go("/?author_id=favorites")
    assert "No books on your list match." in await view.page.inner_text("main")
    await check(view.page, "no-js")
    await context.close()
