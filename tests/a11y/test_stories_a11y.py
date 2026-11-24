"""Spec 009: the story pages and story rows in a real browser (marker ``a11y``)."""

from __future__ import annotations

import uuid

import pytest
from playwright.async_api import Browser

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, boxes, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y


@pytest.fixture
async def collection(seeded: Seeded, factory: Factory) -> dict[str, str]:
    """Seeded Discworld (Alice: #1 Reading, #4 Finished) plus a collection, A Blink of the
    Screen, holding stories at #1.5 and #4.5; it is on nobody's list."""
    series, author = uuid.UUID(seeded.series_id), uuid.UUID(seeded.author_id)
    blink = await factory.book("A Blink of the Screen", seeded.alice, author_ids=[author])
    ids = {"blink": str(blink)}
    for title, number in (("Troll Bridge", "1.5"), ("The Sea and Little Fishes", "4.5")):
        story = await factory.story(
            title, seeded.alice, series_id=series, series_number=number, author_ids=[author],
            book_ids=[blink],
        )  # fmt: skip
        ids[number] = str(story)
    return ids


async def _targets(ui: UI, selector: str, where: str) -> None:
    for box in await boxes(ui.page, selector):
        assert box["height"] >= 44 and box["width"] >= 44, (where, box)


@pytest.mark.ac("009/AC-23")
async def test_story_pages_layout(ui: UI, seeded: Seeded, collection: dict[str, str]) -> None:
    await ui.sign_in(seeded.alice)
    pages = {
        "edit book": f"/catalog/books/{collection['blink']}/edit",
        "add story": f"/catalog/books/{collection['blink']}/stories/add",
        "edit story": f"/catalog/stories/{collection['1.5']}/edit",
        "series": f"/series/{seeded.series_id}",
    }
    for name, path in pages.items():
        await ui.go(path)
        for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
            await size(ui.page, wh)
            await check(ui.page, f"{name} {wh}")  # no sideways scroll, 44 px targets
            await _targets(ui, ".story-list a, .story-list button, .series-rows a", f"{name} {wh}")
            if wh in (PHONE, IPAD, LAPTOP):
                await assert_no_axe_violations(ui.page, f"{name} {wh}")
    await ui.go(f"/catalog/books/{collection['blink']}/edit")
    await ui.page.get_by_role("button", name="Remove “Troll Bridge”").click()
    await ui.page.wait_for_load_state()
    for wh in (SMALL, PHONE, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"confirm {wh}")
        if wh != SMALL:
            await assert_no_axe_violations(ui.page, f"confirm {wh}")


@pytest.mark.ac("009/AC-24")
async def test_story_row_reading_order(ui: UI, seeded: Seeded, collection: dict[str, str]) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/series/{seeded.series_id}")
    items = [
        " ".join(text.split())
        for text in await ui.page.locator(".series-rows > li").all_inner_texts()
    ]
    assert items[1] == (
        "#1.5 Story Troll Bridge In A Blink of the Screen · Not on my list "
        "Want to read “A Blink of the Screen” Add “A Blink of the Screen” with details…"
    )
    story = ui.page.locator(".series-rows > li.series-story").first
    assert await story.locator(".story-label").inner_text() == "Story"


@pytest.mark.ac("009/AC-25")
@pytest.mark.ac("009/AC-03")
@pytest.mark.ac("009/AC-19")
async def test_stories_without_js(
    seeded: Seeded, collection: dict[str, str], pw_browser: Browser, live_server: str
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go(f"/catalog/books/{collection['blink']}/edit")
    await view.page.get_by_role("link", name="Add a story").click()
    await view.page.wait_for_load_state()
    await view.page.fill("#title", "Theatre of Cruelty")
    await view.page.fill("#series_name", "Discworld")
    await view.page.fill("#series_number", "3.5")
    await check(view.page, "add story")
    await view.page.get_by_role("button", name="Add story").click()
    await view.page.wait_for_load_state()
    # A typed catalog name, without JavaScript to pick it: today's choice (spec 005).
    await view.page.get_by_role("button", name="Use existing series “Discworld”").click()
    await view.page.wait_for_load_state()
    notice = view.page.get_by_role("status").filter(has_text="Added the story")
    assert " ".join((await notice.inner_text()).split()) == "Added the story “Theatre of Cruelty”."
    stories = " ".join((await view.page.inner_text(".story-list")).split())
    assert "#3.5 Discworld — Theatre of Cruelty" in stories
    await view.page.get_by_role("link", name="Edit “Theatre of Cruelty”").click()
    await view.page.wait_for_load_state()
    await view.page.fill("#series_number", "3.75")
    await view.page.get_by_role("button", name="Save story").click()
    await view.page.wait_for_load_state()
    assert "Saved." in await view.page.inner_text("main")
    await view.go(f"/catalog/books/{collection['blink']}/edit")
    await view.page.get_by_role("button", name="Remove “Theatre of Cruelty”").click()
    await view.page.wait_for_load_state()
    assert "will be deleted from the family catalog" in await view.page.inner_text("main")
    await view.page.get_by_role("button", name="Remove", exact=True).click()
    await view.page.wait_for_load_state()
    assert "Story deleted from the catalog." in await view.page.inner_text("main")
    await context.close()
