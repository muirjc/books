"""Spec 015: book rows and the one-tap Want to read in a real browser (marker ``a11y``)."""

from __future__ import annotations

import re

import pytest
from playwright.async_api import Browser, expect

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y


async def _targets(ui: UI, where: str) -> None:
    for found in await ui.page.eval_on_selector_all(
        ".status-link, .quick-add button, .row-actions .series-action",
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {name: e.textContent.trim(), w: r.width, h: r.height}; })",
    ):
        assert found["h"] >= 44 and found["w"] >= 44, (where, found)


async def _every_width(ui: UI, label: str) -> None:
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"{label} {wh}")
        await _targets(ui, f"{label} {wh}")
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"{label} {wh}")
    await size(ui.page, LAPTOP)


@pytest.mark.ac("015/AC-12")
@pytest.mark.ac("015/AC-13")
async def test_rows_on_every_page(ui: UI, seeded: Seeded, factory: Factory) -> None:
    import uuid
    from datetime import date, timedelta

    author = uuid.UUID(seeded.author_id)
    series = uuid.UUID(seeded.series_id)
    gods = await factory.book("Small Gods", seeded.ben, author_ids=[author], series_id=series,
                              series_number="13")  # fmt: skip
    await factory.book("The Shepherd's Crown", seeded.ben, author_ids=[author],
                       release_date=date.today() + timedelta(days=90))  # fmt: skip
    tales = await factory.book("Disc Tales", seeded.ben, author_ids=[author])
    await factory.story("Troll Bridge", seeded.ben, series_id=series, series_number="4.5",
                        author_ids=[author], book_ids=[tales])  # fmt: skip
    await ui.sign_in(seeded.alice)
    for label, path in {
        "catalog": "/catalog",
        "author": f"/authors/{seeded.author_id}",
        "upcoming": "/upcoming",
        "series": f"/series/{seeded.series_id}",
    }.items():
        await ui.go(path)
        await _every_width(ui, label)
    # On a laptop, Upcoming rows match the Catalog: actions at the end (PR #35 review).
    await ui.go("/upcoming")
    gaps = await ui.page.eval_on_selector_all(
        ".upcoming-list > li",
        "els => els.filter(li => li.querySelector('.row-actions')).map(li => {"
        " const a = li.querySelector('.row-actions').getBoundingClientRect();"
        " return li.getBoundingClientRect().right - a.right; })",
    )
    assert gaps and all(gap < 2 for gap in gaps), gaps
    # Accessible names (AC-13).
    await ui.go("/catalog")
    await expect(ui.page.get_by_role("button", name="Want to read “Small Gods”")).to_have_count(1)
    await expect(ui.page.get_by_role("link", name="Add “Small Gods” with details…")).to_have_count(
        1
    )
    colour = ui.page.locator(".status-link", has_text="The Colour of Magic")
    await expect(colour).to_have_count(1)
    await expect(colour).to_have_accessible_name(re.compile(r"^Reading\s*: “The Colour of Magic”$"))
    # The notice after a one-tap add, at every width.
    async with ui.page.expect_navigation():
        await ui.page.get_by_role("button", name="Want to read “Small Gods”").click()
    await expect(ui.page.locator("#quick-notice")).to_contain_text("Added “Small Gods”")
    assert ui.page.url.endswith(f"#book-{gods}"), ui.page.url
    await _every_width(ui, "catalog notice")


@pytest.mark.ac("015/AC-06")
async def test_quick_add_without_javascript(
    seeded: Seeded, pw_browser: Browser, live_server: str, factory: Factory
) -> None:
    import uuid

    author = uuid.UUID(seeded.author_id)
    await factory.book("Small Gods", seeded.ben, author_ids=[author])
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go(f"/authors/{seeded.author_id}")
    button = view.page.get_by_role("button", name="Want to read “Small Gods”")
    await button.focus()
    async with view.page.expect_navigation():
        await view.page.keyboard.press("Enter")
    assert f"/authors/{seeded.author_id}?wanted=" in view.page.url
    await expect(view.page.locator("#quick-notice")).to_contain_text("as Want to read")
    status = await factory.scalar(
        "SELECT status FROM reading_entry e JOIN book b ON b.id = e.book_id "
        "WHERE b.title = 'Small Gods' AND e.user_id = :u", u=seeded.alice.id,
    )  # fmt: skip
    assert status == "want_to_read"
    await context.close()
