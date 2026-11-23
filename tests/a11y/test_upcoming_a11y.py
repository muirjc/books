"""Spec 007: the Upcoming page, the Now out notice and the new fields in a real browser
(marker ``a11y``). The live server uses the real clock, so dates are relative to today."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from playwright.async_api import Browser

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

LONG_TITLE = (
    "The Extraordinarily Long and Winding Title of an Upcoming Discworld Book That Keeps "
    "Going Past Any Reasonable Length"
)


@pytest.fixture
async def upcoming(seeded: Seeded, factory: Factory) -> Seeded:
    """Seeded Discworld plus: Alice's pre-ordered upcoming #5 (a long title), her Want to
    read book out 3 days ago (the notice), and Ben's upcoming book (Also coming)."""
    today = date.today()
    series, author = uuid.UUID(seeded.series_id), uuid.UUID(seeded.author_id)
    soon = await factory.book(
        LONG_TITLE, seeded.alice, author_ids=[author], series_id=series, series_number="5",
        release_date=today + timedelta(days=60),
    )  # fmt: skip
    await factory.entry(seeded.alice, soon, status="want_to_read", pre_ordered=True)
    out = await factory.book(
        "Just Out", seeded.alice, author_ids=[author], release_date=today - timedelta(days=3)
    )
    await factory.entry(seeded.alice, out, status="want_to_read", pre_ordered=True)
    theirs = await factory.book(
        "Ben's Upcoming Book", seeded.ben, author_ids=[author],
        release_date=today + timedelta(days=10),
    )  # fmt: skip
    await factory.entry(seeded.ben, theirs, status="want_to_read")
    return seeded


async def _targets(ui: UI, selector: str, where: str) -> None:
    for box in await ui.page.eval_on_selector_all(
        selector,
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {name: e.textContent.trim(), w: r.width, h: r.height}; })",
    ):
        assert box["h"] >= 44 and box["w"] >= 44, (where, box)


@pytest.mark.ac("007/AC-19")
async def test_upcoming_layouts(ui: UI, upcoming: Seeded) -> None:
    await ui.sign_in(upcoming.alice)
    pages = {
        "upcoming": "/upcoming",
        "my books": "/?upcoming=1",
        "my books notice": "/",
        "add": "/books/add",
        "entry": f"/entries/{upcoming.entry_id}",
    }
    for name, path in pages.items():
        await ui.go(path)
        for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
            await size(ui.page, wh)
            await check(ui.page, f"{name} {wh}")  # no sideways scroll, 44 px targets
            if name == "upcoming":
                # Author names (spec 011) are inline links in a line of text, exempt from
                # the target size (WCAG 2.5.8); the row's own targets are checked.
                await _targets(ui, ".upcoming-list a:not(.book-meta a)", f"{name} {wh}")
            if name.startswith("my books"):
                await _targets(ui, "#now-out a", f"{name} {wh}")
            if wh in (PHONE, IPAD, LAPTOP):
                await assert_no_axe_violations(ui.page, f"{name} {wh}")


@pytest.mark.ac("007/AC-20")
async def test_upcoming_without_js(upcoming: Seeded, pw_browser: Browser, live_server: str) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(upcoming.alice)
    # Record a release date with Pre-ordered.
    await view.go("/books/add")
    due = (date.today() + timedelta(days=30)).isoformat()
    await view.page.fill("#title", "Hogfather Returns")
    await view.page.fill("#author_name_0", "Terry Pratchett")
    await view.page.fill("#release_date", due)
    await view.page.check("#pre_ordered")
    await view.page.select_option("#status", "want_to_read")
    await view.page.click(".form-actions button[name=then][value=list]")
    await view.page.wait_for_load_state()
    # Without the type-ahead the typed name matches the catalog's author: use it.
    await view.page.get_by_role("button", name="Use existing author “Terry Pratchett”").click()
    await view.page.wait_for_load_state()
    assert "msg=added" in view.page.url, view.page.url
    # The filter, by checkbox and Apply.
    await view.page.check("#upcoming")
    await view.page.click(".filters .actions button[type=submit]")
    await view.page.wait_for_load_state()
    assert "upcoming=1" in view.page.url
    items = await view.page.locator(".reading-list > li").all_inner_texts()
    rows = [" ".join(t.split()) for t in items]
    assert rows and rows[0].startswith("Hogfather Returns"), rows
    assert "Pre-ordered" in rows[0]
    # The Upcoming page from the navigation.
    await view.page.get_by_role("link", name="Upcoming", exact=True).click()
    await view.page.wait_for_load_state()
    assert view.page.url.endswith("/upcoming")
    assert await view.page.get_by_role("heading", name="On my list").count() == 1
    assert "Ben's Upcoming Book" in await view.page.inner_text("main")
    await check(view.page, "upcoming no-js")
    await context.close()


@pytest.mark.ac("007/AC-21")
async def test_now_out_is_status_text(ui: UI, upcoming: Seeded) -> None:
    await ui.sign_in(upcoming.alice)
    await ui.go("/")
    notice = ui.page.get_by_role("status").filter(has_text="Now out")
    assert await notice.count() == 1
    assert " ".join((await notice.inner_text()).split()) == "Now out: Just Out (pre-ordered)"
    row = ui.page.locator(".reading-list > li", has_text=LONG_TITLE)
    assert "Pre-ordered" in await row.inner_text()
    assert "Coming " in await row.locator(".book-release").inner_text()
