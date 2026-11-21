"""Spec 005: confirming new author and series names in a real browser (marker ``a11y``)."""

from __future__ import annotations

import pytest
from playwright.async_api import Browser

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, box, size
from tests.a11y.test_responsive import check

pytestmark = pytest.mark.a11y

USE = "button[name=use_author_0]"
CONFIRM = "button[name=confirm_author_0]"
ADD = "button[name=then][value=list]"


async def _type_book(ui: UI, title: str, author: str) -> None:
    await ui.go("/books/add")
    await ui.page.fill("#title", title)
    await ui.page.fill("#author_name_0", author)
    await ui.page.click(ADD)
    await ui.page.wait_for_load_state()


@pytest.mark.ac("005/AC-13")
async def test_confirm_flow_without_js(
    seeded: Seeded, pw_browser: Browser, live_server: str
) -> None:
    """The seeded catalog has "Terry Pratchett"; "Terry Pratchet" is a typo of it."""
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await _type_book(view, "Thief of Time", "Terry Pratchet")
    use = view.page.locator(USE)
    assert await use.count() >= 1
    assert (await use.first.inner_text()).strip() == "Use “Terry Pratchett”"
    await use.first.click()
    await view.page.wait_for_load_state()
    assert view.page.url.endswith("/?msg=added"), view.page.url
    await _type_book(view, "Ancillary Justice", "Ann Leckie")
    assert await view.page.locator(USE).count() == 0
    await view.page.click(CONFIRM)
    await view.page.wait_for_load_state()
    assert view.page.url.endswith("/?msg=added"), view.page.url
    await context.close()


@pytest.mark.ac("005/AC-14")
async def test_prompt_accessibility(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await _type_book(ui, "Thief of Time", "Terry Pratchet")
    summary = ui.page.locator(".error-summary a[href='#author_name_0']")
    assert await summary.count() == 1
    assert "is not in the family catalog yet" in await summary.inner_text()
    described = await ui.page.get_attribute("#author_name_0", "aria-describedby") or ""
    assert "author_name_0-error" in described.split()
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"prompt {wh}")
        for selector in (USE, CONFIRM):
            button = await box(ui.page, selector)
            assert button["visible"] and button["height"] >= 44 and button["width"] >= 44, wh
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"prompt {wh}")
