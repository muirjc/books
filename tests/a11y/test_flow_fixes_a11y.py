"""Spec 014 User Story 6: the changed pages in a real browser (marker ``a11y``)."""

from __future__ import annotations

import pytest
from playwright.async_api import Browser, expect

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y


async def _every_width(ui: UI, label: str) -> None:
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"{label} {wh}")
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"{label} {wh}")
    await size(ui.page, LAPTOP)


@pytest.mark.ac("014/AC-20")
async def test_changed_pages(ui: UI, seeded: Seeded, factory: Factory) -> None:
    await ui.sign_in(seeded.alice)
    pages = {
        "my books": "/",
        "entry": f"/entries/{seeded.entry_id}",
        "edit book": f"/catalog/books/{seeded.book_id}/edit",
        "summary": f"/catalog/books/{seeded.book_id}/summary",
        "edit series": f"/catalog/series/{seeded.series_id}/edit",
        "series": f"/series/{seeded.series_id}",
        "author": f"/authors/{seeded.author_id}",
        "add story": f"/catalog/books/{seeded.book_id}/stories/add?from=entry:{seeded.entry_id}",
        "collection": f"/books/add?series={seeded.series_id}&anthology=yes",
    }
    for label, path in pages.items():
        await ui.go(path)
        await _every_width(ui, label)
    # The admin confirmation page.
    await ui.sign_in(seeded.admin)
    await ui.go("/admin/users")
    async with ui.page.expect_navigation():
        await ui.page.get_by_role("button", name="Deactivate Ben").click()
    await expect(ui.page.get_by_role("heading", name="Deactivate Ben?")).to_be_visible()
    await _every_width(ui, "confirm deactivate")


@pytest.mark.ac("014/AC-21")
async def test_journeys_without_javascript(
    seeded: Seeded, pw_browser: Browser, live_server: str, factory: Factory
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    page = view.page
    await view.sign_in(seeded.alice)
    # Two stories for Mort from its entry page, by keyboard.
    await view.go(f"/entries/{seeded.entry_id}")
    async with page.expect_navigation():
        await page.get_by_role("link", name="Add a story").click()
    for title, number, button in (("Troll Bridge", "4.5", "Add and add another"),
                                  ("The Sea and Little Fishes", "4.6", "Add story")):  # fmt: skip
        await page.fill("#title", title)
        await page.fill("#series_number", number)
        await page.get_by_role("button", name=button, exact=True).focus()
        async with page.expect_navigation():
            await page.keyboard.press("Enter")
        if button == "Add and add another":
            await expect(page.locator("#added-notice")).to_contain_text("Troll Bridge")
            await expect(page.locator("#title")).to_be_focused()
    assert page.url.endswith(f"/entries/{seeded.entry_id}?msg=story_added"), page.url
    await expect(page.get_by_text("The Sea and Little Fishes")).to_be_visible()
    # Add #next from the series page.
    await view.go(f"/series/{seeded.series_id}")
    async with page.expect_navigation():
        await page.get_by_role("link", name="Add #5").click()
    await expect(page.locator("#series_number")).to_have_value("5")
    # An admin confirms a deactivation.
    await view.sign_in(seeded.admin)
    await view.go("/admin/users")
    async with page.expect_navigation():
        await page.get_by_role("button", name="Deactivate Ben").click()
    async with page.expect_navigation():
        await page.get_by_role("button", name="Confirm").click()
    await expect(page.get_by_text("Account updated.")).to_be_visible()
    assert await factory.scalar("SELECT is_active FROM app_user WHERE login = 'ben'") is False
    await context.close()
