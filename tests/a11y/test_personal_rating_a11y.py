"""Spec 020 AC-14: the Rating field, the rating on My books, and the rating sort and filter,
in a real browser (marker ``a11y``)."""

from __future__ import annotations

import pytest
from playwright.async_api import Browser

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import WIDTHS, size
from tests.a11y.test_responsive import check
from tests.a11y.test_stories_a11y import _targets
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

RATING_ERROR = "Choose a rating from 1 to 5, or No rating"


@pytest.fixture
async def rated(seeded: Seeded, factory: Factory) -> None:
    """Alice's Mort rated 5, and a long-titled book rated 2."""
    await factory.execute("UPDATE reading_entry SET rating = 5 WHERE id = :id", id=seeded.entry_id)
    book = await factory.book(
        "A Rather Long Title For A Book That Has To Fit On A Small Phone Screen", seeded.alice
    )
    await factory.entry(seeded.alice, book, rating=2)


async def _every_width(ui: UI, name: str) -> None:
    for wh in WIDTHS:
        await size(ui.page, wh)
        await check(ui.page, f"{name} {wh}")
        await _targets(ui, "#rating", f"{name} {wh}")
        await assert_no_axe_violations(ui.page, f"{name} {wh}")


async def _open_filters(ui: UI) -> None:
    toggle = ui.page.locator(".filters-toggle")
    if await toggle.is_visible() and await toggle.get_attribute("aria-expanded") == "false":
        await toggle.click()


@pytest.mark.ac("020/AC-14")
async def test_rating_pages_at_every_width(ui: UI, seeded: Seeded, rated: None) -> None:
    await ui.sign_in(seeded.alice)
    for name, path in {
        "entry page": f"/entries/{seeded.entry_id}",
        "add a book": "/books/add",
        "book page": f"/books/{seeded.book_id}",
    }.items():
        await ui.go(path)
        await _every_width(ui, name)
    for name, path in {
        "my books": "/",
        "highest rated": "/?sort=-rating",
        "4 and up": "/?rating=4",
    }.items():
        await ui.go(path)
        for wh in WIDTHS:
            await size(ui.page, wh)
            await _open_filters(ui)
            await check(ui.page, f"{name} {wh}")
            await _targets(ui, "#rating, #sort", f"{name} {wh}")
            await assert_no_axe_violations(ui.page, f"{name} {wh}")
            assert "Rated 5 out of 5" in await ui.page.inner_text("#reading-list"), (name, wh)


@pytest.mark.ac("020/AC-14")
async def test_rating_error_at_every_width(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/entries/{seeded.entry_id}")
    # A tampered form: an option the page never offers.
    await ui.page.evaluate(
        "() => { const s = document.querySelector('#rating'); s.add(new Option('Six', '6'));"
        " s.value = '6'; }"
    )
    await ui.page.get_by_role("button", name="Save", exact=True).click()
    await ui.page.wait_for_load_state()
    assert RATING_ERROR in await ui.page.inner_text("main")
    described = await ui.page.get_attribute("#rating", "aria-describedby")
    assert described == "rating-error"
    await _every_width(ui, "rating error")


@pytest.mark.ac("020/AC-14")
async def test_rating_with_javascript_off(
    seeded: Seeded, rated: None, pw_browser: Browser, live_server: str
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go(f"/entries/{seeded.entry_id}")
    await view.page.select_option("#rating", "3")
    await view.page.get_by_role("button", name="Save", exact=True).click()
    await view.page.wait_for_load_state()
    assert await view.page.input_value("#rating") == "3"
    await view.go("/")
    await view.page.select_option("#sort", "-rating")
    await view.page.select_option("#rating", "3")
    await view.page.get_by_role("button", name="Apply").click()
    await view.page.wait_for_load_state()
    assert "sort=-rating" in view.page.url and "rating=3" in view.page.url
    rows = await view.page.locator(".reading-list .book-title").all_inner_texts()
    assert rows == ["Mort"]
    assert "Rated 3 out of 5" in await view.page.inner_text("#reading-list")
    await view.page.get_by_role("link", name="Clear filters").click()
    await view.page.wait_for_load_state()
    assert await view.page.input_value("#rating") == ""
    await context.close()
