"""Spec 016 AC-14: the book page in a real browser (marker ``a11y``)."""

from __future__ import annotations

import uuid

import pytest
from playwright.async_api import Browser, expect

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

# Every focusable control in the main content, in document order.
FOCUSABLE = (
    "() => Array.from(document.querySelectorAll("
    "'main a[href], main button, main input:not([type=hidden])')).map(e => e.outerHTML)"
)


async def _every_width(ui: UI, label: str) -> None:
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"{label} {wh}")
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"{label} {wh}")
    await size(ui.page, LAPTOP)


async def _tab_order(ui: UI, label: str) -> None:
    """Tab reaches every control in the main content, in the page's reading order."""
    expected = await ui.page.evaluate(FOCUSABLE)
    # Start just before the content: the heading, made focusable for the test only.
    await ui.page.evaluate("() => { const h = document.querySelector('main h1');"
                           " h.setAttribute('tabindex', '-1'); h.focus(); }")  # fmt: skip
    seen: list[str] = []
    for _ in expected:
        await ui.page.keyboard.press("Tab")
        seen.append(await ui.page.evaluate("() => document.activeElement.outerHTML"))
    assert seen == expected, label


@pytest.mark.ac("016/AC-14")
async def test_book_page_everywhere(ui: UI, seeded: Seeded, factory: Factory) -> None:
    author = uuid.UUID(seeded.author_id)
    series = uuid.UUID(seeded.series_id)
    tales = await factory.book("Disc Tales", seeded.ben, author_ids=[author])
    omnibus = await factory.book("A Very Long Omnibus Title For Narrow Phones", seeded.ben,
                                 author_ids=[author])  # fmt: skip
    for n, title in (("4.5", "Troll Bridge"), ("23.5", "The Sea and Little Fishes")):
        await factory.story(title, seeded.ben, series_id=series, series_number=n,
                            author_ids=[author], book_ids=[tales, omnibus])  # fmt: skip
    await ui.sign_in(seeded.alice)
    # On my list, with a summary and no stories.
    await ui.go(f"/books/{seeded.book_id}")
    await expect(ui.page.get_by_role("link", name="Open my entry")).to_have_count(1)
    await _every_width(ui, "mine")
    await _tab_order(ui, "mine")
    # Not on my list, with stories and "Also in".
    await ui.go(f"/books/{tales}")
    await expect(ui.page.get_by_role("button", name="Want to read “Disc Tales”")).to_have_count(1)
    await _every_width(ui, "not mine")
    await _tab_order(ui, "not mine")
    # The quick-add notice.
    async with ui.page.expect_navigation():
        await ui.page.get_by_role("button", name="Want to read “Disc Tales”").click()
    await expect(ui.page.locator("#quick-notice")).to_contain_text("Added “Disc Tales”")
    assert ui.page.url.endswith(f"#book-{tales}"), ui.page.url
    await _every_width(ui, "notice")


@pytest.mark.ac("016/AC-14")
async def test_quick_add_without_javascript(
    seeded: Seeded, pw_browser: Browser, live_server: str, factory: Factory
) -> None:
    book = await factory.book("Small Gods", seeded.ben, author_ids=[uuid.UUID(seeded.author_id)])
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go(f"/books/{book}")
    async with view.page.expect_navigation():
        await view.page.get_by_role("button", name="Want to read “Small Gods”").click()
    assert f"/books/{book}?wanted=" in view.page.url
    await expect(view.page.locator("#quick-notice")).to_contain_text("as Want to read")
    await context.close()
