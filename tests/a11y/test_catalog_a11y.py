"""Spec 010: the Catalog page in a real browser (marker ``a11y``)."""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

import pytest
from playwright.async_api import Browser, expect

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, box, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

LONG_TITLE = (
    "An Extraordinarily Long and Winding Title for a Catalog Book That Keeps Going Past Any "
    "Reasonable Length"
)


@pytest.fixture
async def catalog(seeded: Seeded, factory: Factory) -> Seeded:
    """Seeded Discworld (on Alice's list) plus 60 more books on nobody's list: a long title,
    an upcoming one, and 58 fillers, so there are two pages."""
    series, author = uuid.UUID(seeded.series_id), uuid.UUID(seeded.author_id)
    await factory.book(LONG_TITLE, seeded.ben, author_ids=[author], series_id=series,
                       series_number="7")  # fmt: skip
    await factory.book(
        "Coming Soon", seeded.ben, author_ids=[author],
        release_date=date.today() + timedelta(days=30),
    )  # fmt: skip
    for i in range(1, 59):
        await factory.book(f"Filler {i:02d}", seeded.ben, author_ids=[author])
    return seeded


async def _targets(ui: UI, where: str) -> None:
    for found in await ui.page.eval_on_selector_all(
        ".catalog-list .book-title, .catalog-list .series-action, .catalog-mine, .pagination a",
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {name: e.textContent.trim(), w: r.width, h: r.height}; })",
    ):
        assert found["h"] >= 44 and found["w"] >= 44, (where, found)


@pytest.mark.ac("010/AC-03")
@pytest.mark.ac("010/AC-09")
async def test_catalog_layouts(ui: UI, catalog: Seeded) -> None:
    """SC-003: no sideways scroll, 44 px targets and no axe violations at every width."""
    await ui.sign_in(catalog.alice)
    for path in ("/catalog", "/catalog?q=filler&page=2", "/catalog?q=zzz"):
        await ui.go(path)
        for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
            await size(ui.page, wh)
            await check(ui.page, f"{path} {wh}")
            await _targets(ui, f"{path} {wh}")
            if wh in (PHONE, IPAD, LAPTOP):
                await assert_no_axe_violations(ui.page, f"{path} {wh}")


@pytest.mark.ac("010/AC-16")
async def test_phone_folds_sort_and_filter(ui: UI, catalog: Seeded) -> None:
    await size(ui.page, PHONE)
    await ui.sign_in(catalog.alice)
    await ui.go("/catalog")
    assert not (await box(ui.page, "#sort"))["visible"]
    toggle = ui.page.locator(".filters-toggle")
    assert await toggle.get_attribute("aria-expanded") == "false"
    await toggle.click()
    assert (await box(ui.page, "#sort"))["visible"]
    assert (await box(ui.page, "#not_mine"))["visible"]
    await ui.go("/catalog?not_mine=1")
    assert await toggle.get_attribute("aria-expanded") == "true"


@pytest.mark.ac("010/AC-06")
@pytest.mark.ac("010/AC-16")
async def test_keyboard_journey(ui: UI, catalog: Seeded) -> None:
    """Search, sort and page by keyboard, the list updating in place; then Add to my list."""
    await ui.sign_in(catalog.alice)
    await ui.go("/")
    await ui.page.get_by_role("link", name="Catalog", exact=True).focus()
    await ui.page.keyboard.press("Enter")
    await ui.page.wait_for_url(re.compile(r"/catalog$"))
    await ui.page.locator("#q").focus()
    await ui.page.keyboard.type("filler")
    count = ui.page.get_by_role("status")
    await expect(count).to_have_text("58 books match")
    await expect(ui.page.locator("#catalog-clear")).to_be_visible()  # follows the update
    await expect(ui.page).to_have_url(re.compile(r"q=filler"))
    await ui.page.locator("#sort").focus()
    await ui.page.keyboard.press("ArrowDown")  # Title (Z–A)
    rows = ui.page.locator(".catalog-list > li .book-title")
    await expect(rows.first).to_have_text("Filler 58")
    next_link = ui.page.get_by_role("link", name="Next")
    await next_link.focus()
    await ui.page.keyboard.press("Enter")
    await ui.page.wait_for_url(re.compile(r"page=2"))
    await expect(ui.page.locator(".pagination span")).to_have_text("Page 2 of 2")
    add = ui.page.get_by_role("link", name="Add “Filler 08” to my list")
    await add.focus()
    await ui.page.keyboard.press("Enter")
    await ui.page.wait_for_url(re.compile(r"/books/add\?book="))
    await expect(ui.page.locator(".chosen-book")).to_contain_text("Filler 08")


@pytest.mark.ac("010/AC-14")
@pytest.mark.ac("010/AC-16")
async def test_catalog_without_js(catalog: Seeded, pw_browser: Browser, live_server: str) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(catalog.alice)
    await view.page.get_by_role("link", name="Catalog", exact=True).click()
    await view.page.wait_for_load_state()
    assert await view.page.locator("#list-count").inner_text() == "62 books in the family catalog"
    await view.page.fill("#q", "mort")
    await view.page.click(".filters .actions button[type=submit]")
    await view.page.wait_for_load_state()
    assert "On my list" in await view.page.locator(".catalog-row", has_text="Mort").inner_text()
    await view.page.fill("#q", "pratchett")
    await view.page.check("#not_mine")
    await view.page.click(".filters .actions button[type=submit]")
    await view.page.wait_for_load_state()
    assert "not_mine=1" in view.page.url and "q=pratchett" in view.page.url
    assert await view.page.locator("#list-count").inner_text() == "60 books match"
    assert await view.page.locator(".catalog-mine").count() == 0
    await check(view.page, "catalog no-js")
    await context.close()
