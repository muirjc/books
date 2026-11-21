"""Spec 004: "Add and add another" in a real browser (marker ``a11y``)."""

from __future__ import annotations

import pytest
from playwright.async_api import Browser, Page

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, box, size
from tests.a11y.test_responsive import check

pytestmark = pytest.mark.a11y

LONG_TITLE = (
    "The Extraordinarily Long and Winding Title of a Book That Keeps Going Well Past "
    "Any Reasonable Length for One Line"
)
ANOTHER = "button[name=then][value=another]"
LIST = "button[name=then][value=list]"


async def _add(page: Page, title: str, author: str = "Neil Gaiman") -> None:
    await page.fill("#title", title)
    await page.fill("#author_name_0", author)
    await page.click(ANOTHER)
    await page.wait_for_load_state()
    # Spec 005: a new author needs a yes; the choice keeps "Add and add another".
    confirm = page.locator("button[name=confirm_author_0]")
    if await confirm.count():
        await confirm.click()
        await page.wait_for_load_state()


async def _active_id(page: Page) -> str:
    return str(await page.evaluate("document.activeElement && document.activeElement.id"))


@pytest.mark.ac("004/AC-03")
@pytest.mark.ac("004/AC-06")
@pytest.mark.parametrize("javascript", [True, False])
async def test_add_another_flow_with_and_without_js(
    seeded: Seeded, pw_browser: Browser, live_server: str, javascript: bool
) -> None:
    context = await pw_browser.new_context(java_script_enabled=javascript)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go("/books/add")
    await _add(view.page, "Good Omens")
    assert "/books/add?after=" in view.page.url
    notice = await view.page.inner_text("#added-notice")
    assert notice.strip() == "Added “Good Omens” to your list."
    assert await _active_id(view.page) == "title"
    assert await view.page.input_value("#author_name_0") == "Neil Gaiman"
    # Enter in a field submits with "Add to my list" (FR-010).
    await view.page.fill("#title", "Neverwhere")
    await view.page.press("#title", "Enter")
    await view.page.wait_for_load_state()
    assert view.page.url.endswith("/?msg=added"), view.page.url
    await context.close()


@pytest.mark.ac("004/AC-15")
async def test_conflict_button_keeps_choice(ui: UI, seeded: Seeded) -> None:
    """Clicking the real "Use existing author" button keeps "Add and add another" (R2)."""
    await ui.sign_in(seeded.alice)
    await ui.go("/books/add")
    await _add(ui.page, "Thief of Time", author="terry pratchett")
    use_existing = ui.page.locator("button[name=author_id_0]")
    assert await use_existing.count() == 1
    await use_existing.click()
    await ui.page.wait_for_load_state()
    assert "/books/add?after=" in ui.page.url, ui.page.url
    assert "Thief of Time" in await ui.page.inner_text("#added-notice")


@pytest.mark.ac("004/AC-17")
async def test_buttons_fit_every_width(
    ui: UI, seeded: Seeded, pw_browser: Browser, live_server: str
) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/books/add")
    await _add(ui.page, LONG_TITLE)
    carry_over = ui.page.url
    assert "/books/add?after=" in carry_over, carry_over  # the next-book form, not a prompt
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await ui.go(carry_over.removeprefix(ui.base_url))
        await check(ui.page, f"carry-over {wh}")
        first, second = await box(ui.page, LIST), await box(ui.page, ANOTHER)
        for button in (first, second):
            assert button["visible"] and button["width"] >= 44 and button["height"] >= 44, wh
        # Add to my list comes first, visually and in Tab order.
        assert (first["top"], first["left"]) < (second["top"], second["left"]), wh
        assert await ui.page.evaluate(
            """([a, b]) => !!(document.querySelector(a).compareDocumentPosition(
                 document.querySelector(b)) & Node.DOCUMENT_POSITION_FOLLOWING)""",
            [LIST, ANOTHER],
        )
    # 200% text: a 1,280 x 900 window at 200% zoom (spec 003 AC-22, FR-012).
    context = await pw_browser.new_context(
        viewport={"width": 640, "height": 450}, device_scale_factor=2
    )
    zoomed = UI(await context.new_page(), live_server)
    await zoomed.sign_in(seeded.alice)
    await zoomed.go(carry_over.removeprefix(ui.base_url))
    await check(zoomed.page, "carry-over at 200%")
    assert (await box(zoomed.page, ANOTHER))["visible"]
    await context.close()


@pytest.mark.ac("004/AC-18")
async def test_axe_add_another(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/books/add")
    await _add(ui.page, "American Gods")
    carry_over = ui.page.url.removeprefix(ui.base_url)
    assert "/books/add?after=" in carry_over, carry_over  # the next-book form, not a prompt
    for wh in (PHONE, IPAD, LAPTOP):
        await size(ui.page, wh)
        for label, path in (("plain", "/books/add"), ("carry-over", carry_over)):
            await ui.go(path)
            await assert_no_axe_violations(ui.page, f"{label} {wh}")
