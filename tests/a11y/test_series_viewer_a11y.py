"""Spec 006: the series viewer in a real browser (marker ``a11y``)."""

from __future__ import annotations

import pytest
from playwright.async_api import Browser

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, boxes, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

LONG_TITLE = (
    "The Extraordinarily Long and Winding Title of a Discworld Book That Keeps Going Past "
    "Any Reasonable Length for One Line"
)


@pytest.fixture
async def discworld(seeded: Seeded, factory: Factory) -> Seeded:
    """Seeded Discworld (Alice: #1 Reading, #4 Finished) plus #2 and a long #5 on nobody's
    list, so the page has every row kind: mine, not on my list, and a gap (#3)."""
    import uuid

    series, author = uuid.UUID(seeded.series_id), uuid.UUID(seeded.author_id)
    await factory.book(
        "The Light Fantastic", seeded.alice, author_ids=[author], series_id=series,
        series_number="2",
    )  # fmt: skip
    await factory.book(
        LONG_TITLE, seeded.alice, author_ids=[author], series_id=series, series_number="5"
    )
    return seeded


@pytest.mark.ac("006/AC-17")
async def test_series_page_layout(ui: UI, discworld: Seeded) -> None:
    await ui.sign_in(discworld.alice)
    await ui.go(f"/series/{discworld.series_id}")
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"series {wh}")  # no sideways scroll, 44 px targets
        for link in await boxes(ui.page, ".series-rows a"):
            assert link["height"] >= 44 and link["width"] >= 44, (wh, link)
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"series {wh}")
    # Add a book, started from a row: the chosen book's details (PR #22 review).
    await ui.page.get_by_role("link", name="Add “The Light Fantastic” to my list").click()
    await ui.page.wait_for_load_state()
    for wh in (SMALL, PHONE, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"add from series {wh}")
        if wh != SMALL:
            await assert_no_axe_violations(ui.page, f"add from series {wh}")


@pytest.mark.ac("006/AC-18")
async def test_row_reading_order(ui: UI, discworld: Seeded) -> None:
    await ui.sign_in(discworld.alice)
    await ui.go(f"/series/{discworld.series_id}")
    items = [
        " ".join(text.split())
        for text in await ui.page.locator(".series-rows > li").all_inner_texts()
    ]
    assert items[0] == "#1 The Colour of Magic Terry Pratchett · Reading"
    assert items[1] == (
        "#2 The Light Fantastic Terry Pratchett · Not on my list "
        "Add “The Light Fantastic” to my list"  # the title is visually hidden
    )
    assert items[2] == "#3 Not in the family catalog yet Add #3"
    assert items[3].startswith("#4 Mort Terry Pratchett · Finished")
    # The visible "Add to my list" is named for its book (WCAG 2.4.4).
    add = ui.page.get_by_role("link", name="Add “The Light Fantastic” to my list")
    assert await add.count() == 1


@pytest.mark.ac("006/AC-19")
@pytest.mark.ac("006/AC-08")
async def test_flow_without_js(discworld: Seeded, pw_browser: Browser, live_server: str) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(discworld.alice)
    await view.go(f"/series/{discworld.series_id}")
    await view.page.get_by_role("link", name="Add “The Light Fantastic” to my list").click()
    await view.page.wait_for_load_state()
    chosen = " ".join((await view.page.inner_text(".chosen-book")).split())
    assert "The Light Fantastic · Terry Pratchett · Discworld #2" in chosen
    assert await view.page.locator("#title").count() == 0
    await check(view.page, "add from series")
    assert await view.page.input_value("#status") == "want_to_read"
    await view.page.click(".form-actions button[name=then][value=list]")
    await view.page.wait_for_load_state()
    assert f"/series/{discworld.series_id}?added=" in view.page.url, view.page.url
    notice = " ".join((await view.page.inner_text("#added-notice")).split())
    assert notice == "Added “The Light Fantastic” to your list."
    row = view.page.locator(".series-rows > li", has_text="The Light Fantastic")
    assert "Want to read" in await row.inner_text()
    await check(view.page, "series after add")
    await context.close()
