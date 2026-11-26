"""Spec 013 User Story 5: story rows on Add a book in a real browser (marker ``a11y``)."""

from __future__ import annotations

import uuid

import pytest
from playwright.async_api import Browser, expect

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory, without_finished

pytestmark = pytest.mark.a11y

ADD = ".form-actions button[name=then][value=list]"
ADD_ROW = "button[name=action][value=add_story]"


async def _every_width(ui: UI, label: str) -> None:
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"{label} {wh}")
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"{label} {wh}")
    await size(ui.page, LAPTOP)


async def _book(ui: UI, title: str) -> None:
    await ui.page.fill("#title", title)
    await ui.page.fill("#author_name_0", "Terry Pratchett")
    await ui.page.fill("#series_name", "Discworld")


async def _submit(ui: UI, selector: str) -> None:
    async with ui.page.expect_navigation():
        await ui.page.click(selector)


@pytest.mark.ac("013/AC-28")
@pytest.mark.ac("013/AC-29")
async def test_story_section_states(ui: UI, seeded: Seeded, factory: Factory) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/books/add")
    stories = ui.page.locator("#stories")
    await expect(stories).to_be_hidden()  # JavaScript hides it while unticked
    await ui.page.check("#anthology")
    await expect(stories).to_be_visible()  # no page load
    await ui.page.uncheck("#anthology")
    await expect(stories).to_be_hidden()
    await ui.page.check("#anthology")
    await _every_width(ui, "section open")
    # Two rows: one missing its number, one with a new author name.
    await _book(ui, "Tales of the Disc")
    await ui.page.fill("#story_title_0", "Troll Bridge")
    await _submit(ui, ADD_ROW)
    await expect(ui.page.locator("#story_title_1")).to_be_focused()
    await ui.page.fill("#story_title_1", "The Sea and Little Fishes")
    await ui.page.fill("#story_number_1", "23.5")
    await ui.page.fill("#story_author_name_1", "Zed Unknown Writer")
    await _submit(ui, ADD)
    await expect(ui.page.locator("#story_number_0-error")).to_contain_text("Story 1:")
    await expect(ui.page.locator("#story_author_name_1-error")).to_contain_text("Story 2:")
    await expect(ui.page.locator("button[name=confirm_story_author_1]")).to_be_visible()
    await _every_width(ui, "row errors and prompt")
    # A number another story holds: the "Use that story" choice.
    mort = uuid.UUID(seeded.book_id)
    await factory.story(
        "Troll Bridge", seeded.alice, series_id=uuid.UUID(seeded.series_id), series_number="4.5",
        author_ids=[uuid.UUID(seeded.author_id)], book_ids=[mort],
    )  # fmt: skip
    await ui.page.fill("#story_number_0", "4.5")
    await ui.page.fill("#story_author_name_1", "")
    await _submit(ui, ADD)
    await expect(ui.page.locator("button[name=use_story_0]")).to_be_visible()
    await _every_width(ui, "taken number")
    await _submit(ui, "button[name=use_story_0]")
    await expect(ui.page.locator(".chosen-story")).to_contain_text("already in the catalog")
    await _every_width(ui, "existing story chosen")


@pytest.mark.ac("013/AC-29")
@pytest.mark.ac("013/AC-30")
async def test_keyboard_journey_without_javascript(
    seeded: Seeded, pw_browser: Browser, live_server: str, factory: Factory
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    page = view.page
    await view.sign_in(seeded.alice)
    await view.go("/books/add")
    await expect(page.locator("#stories")).to_be_visible()  # always shown without JS
    await page.fill("#title", "A Blink of the Screen")
    await page.fill("#author_name_0", "Zed Editor")
    await page.focus("#anthology")
    await page.keyboard.press("Space")
    await expect(page.locator("#anthology")).to_be_checked()
    await page.fill("#story_title_0", "Troll Bridge")
    await page.fill("#story_number_0", "4.5")
    await page.fill("#story_series_name_0", "Discworld")
    group = page.get_by_role("group", name="Story 1")
    await expect(group).to_have_count(1)
    # Add another story twice, by keyboard: focus lands on the new row's title.
    for n in (2, 3):
        await page.focus(ADD_ROW)
        async with page.expect_navigation():
            await page.keyboard.press("Enter")
        await expect(page.locator(f"#story_title_{n - 1}")).to_be_focused()
        await page.keyboard.type(f"Story number {n}")
        await page.fill(f"#story_number_{n - 1}", f"{n}0.5")
        await page.fill(f"#story_series_name_{n - 1}", "Discworld")
    await expect(page.get_by_role("button", name="Remove story 3")).to_have_count(1)
    # Remove story 2: focus goes to the section heading; the others are kept.
    await page.get_by_role("button", name="Remove story 2").focus()
    async with page.expect_navigation():
        await page.keyboard.press("Enter")
    await expect(page.locator("#stories-heading")).to_be_focused()
    await expect(page.locator("#story_title_1")).to_have_value("Story number 3")
    # Save; confirm the new editor's name; done.
    await page.focus(ADD)
    async with page.expect_navigation():
        await page.keyboard.press("Enter")
    confirm = page.locator("button[name=confirm_author_0]")
    await confirm.focus()
    async with page.expect_navigation():
        await page.keyboard.press("Enter")
    assert without_finished(page.url).endswith("/?msg=added&stories=2"), page.url
    await expect(page.get_by_text("Added to your list, with 2 stories.")).to_be_visible()
    assert await factory.scalar("SELECT count(*) FROM story") == 2
    await context.close()
