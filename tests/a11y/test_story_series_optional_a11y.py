"""Spec 019 AC-15: stories without a series in a real browser (marker ``a11y``)."""

from __future__ import annotations

import uuid

import pytest
from playwright.async_api import Browser

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.a11y.test_stories_a11y import _targets
from tests.conftest import Factory

pytestmark = pytest.mark.a11y


@pytest.fixture
async def anthology(seeded: Seeded, factory: Factory) -> dict[str, str]:
    """An anthology with a long story title and no series, on Alice's list."""
    author = uuid.UUID(seeded.author_id)
    book = await factory.book("The Best Short Stories of the Year", seeded.alice,
                              author_ids=[author])  # fmt: skip
    for title in (
        "The Lottery",
        "A Very Long Story Title That Has To Wrap On A Small Phone Screen Somehow",
    ):
        story = await factory.story(title, seeded.alice, series_id=None, series_number=None,
                                    author_ids=[author], book_ids=[book])  # fmt: skip
    entry = await factory.entry(seeded.alice, book, status="reading")
    return {"book": str(book), "entry": str(entry), "story": str(story)}


async def _every_width(ui: UI, name: str) -> None:
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"{name} {wh}")
        await _targets(ui, ".story-list a, .story-list button", f"{name} {wh}")
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"{name} {wh}")


@pytest.mark.ac("019/AC-15")
async def test_pages_listing_stories_without_a_series(
    ui: UI, seeded: Seeded, anthology: dict[str, str]
) -> None:
    await ui.sign_in(seeded.alice)
    for name, path in {
        "book page": f"/books/{anthology['book']}",
        "entry page": f"/entries/{anthology['entry']}",
        "edit book": f"/catalog/books/{anthology['book']}/edit",
        "edit story": f"/catalog/stories/{anthology['story']}/edit",
    }.items():
        await ui.go(path)
        await _every_width(ui, name)


@pytest.mark.ac("019/AC-15")
async def test_forms_with_errors(ui: UI, seeded: Seeded, anthology: dict[str, str]) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/catalog/books/{anthology['book']}/stories/add")
    await ui.page.fill("#title", "Half")
    await ui.page.fill("#series_name", "Discworld")
    await ui.page.get_by_role("button", name="Add story").click()
    await ui.page.wait_for_load_state()
    assert "clear the series" in await ui.page.inner_text("main")
    await _every_width(ui, "add story error")
    await ui.go("/books/add")
    await ui.page.check("input[name=anthology]")
    await ui.page.fill("#title", "Anthology")
    await ui.page.fill("#story_title_0", "Half")
    await ui.page.fill("#story_series_name_0", "Discworld")
    await ui.page.get_by_role("button", name="Add to my list").click()
    await ui.page.wait_for_load_state()
    assert "Story 1: Enter a number, or clear the series" in await ui.page.inner_text("main")
    await _every_width(ui, "story row error")


@pytest.mark.ac("019/AC-15")
async def test_without_javascript(
    seeded: Seeded, anthology: dict[str, str], pw_browser: Browser, live_server: str
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go(f"/catalog/books/{anthology['book']}/stories/add")
    await view.page.fill("#title", "Harrison Bergeron")
    await view.page.fill("#series_name", "")
    await view.page.get_by_role("button", name="Add story").click()
    await view.page.wait_for_load_state()
    stories = " ".join((await view.page.inner_text(".story-list")).split())
    assert "Harrison Bergeron" in stories and "#" not in stories
    await view.go("/books/add")
    await view.page.check("input[name=anthology]")
    await view.page.fill("#title", "No-JS Anthology")
    await view.page.fill("#author_name_0", "Terry Pratchett")
    await view.page.fill("#story_title_0", "Plain Tale")
    await view.page.get_by_role("button", name="Add to my list").click()
    await view.page.wait_for_load_state()
    await view.page.get_by_role("button", name="Use existing author “Terry Pratchett”").click()
    await view.page.wait_for_load_state()
    assert "with 1 story" in await view.page.inner_text("main")
    await context.close()
