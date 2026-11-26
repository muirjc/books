"""Spec 018 AC-18 and SC-001: the menu, the Authors page, the Series view, Upcoming with
Now out and My books' Now out line, in a real browser (marker ``a11y``)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from playwright.async_api import Browser, expect

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_book_page_a11y import _every_width
from tests.a11y.test_layout_003 import IPAD, LAPTOP, PHONE, SMALL, WIDTHS, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

MENU_ROWS = """() => new Set([...document.querySelectorAll('.nav-list a')]
  .map(a => Math.round(a.getBoundingClientRect().top))).size"""


@pytest.fixture
async def shelf(seeded: Seeded, factory: Factory) -> dict[str, uuid.UUID]:
    """Seeded's Terry Pratchett, plus a long name, a pen name, a series, and books of
    Alice's just out and coming."""
    p = uuid.UUID(seeded.author_id)
    long = await factory.author("Douglas Preston and Lincoln Child and Friends", seeded.ben)
    await factory.author(
        "Robert Galbraith", seeded.ben, is_pen_name=True, real_name="J. K. Rowling"
    )
    saga = await factory.series("A Very Long Series Name That Goes On and On and On", seeded.ben)
    await factory.book("Saga One", seeded.ben, author_ids=[long], series_id=saga)
    out = await factory.book("Just Out", seeded.ben, author_ids=[p],
                             release_date=date.today() - timedelta(days=3))  # fmt: skip
    soon = await factory.book("Coming Soon", seeded.ben, author_ids=[p],
                              release_date=date.today() + timedelta(days=30))  # fmt: skip
    await factory.book("Also Coming", seeded.ben, author_ids=[long],
                       release_date=date.today() + timedelta(days=60))  # fmt: skip
    await factory.entry(seeded.alice, out, status="want_to_read")
    await factory.entry(seeded.alice, soon, status="want_to_read")
    await factory.favorite(seeded.alice, long)
    return {"p": p, "long": long, "saga": saga}


@pytest.mark.ac("018/AC-18")
async def test_menu_at_every_width(seeded: Seeded, pw_browser: Browser, live_server: str) -> None:
    for user in (seeded.alice, seeded.admin):
        view = UI(await (await pw_browser.new_context()).new_page(), live_server)
        await view.sign_in(user)
        await view.go("/authors")
        for wh in WIDTHS:
            await size(view.page, wh)
            await check(view.page, f"{user.login} menu {wh}")
            rows = await view.page.evaluate(MENU_ROWS)
            assert rows <= 2, (user.login, wh, rows)
            if wh in (PHONE, IPAD, LAPTOP):
                await assert_no_axe_violations(view.page, f"{user.login} menu {wh}")
        await view.page.context.close()


@pytest.mark.ac("018/AC-18")
async def test_authors_page_layouts(ui: UI, seeded: Seeded, shelf: dict[str, uuid.UUID]) -> None:
    await ui.sign_in(seeded.alice)
    for label, path in (("authors", "/authors"), ("no match", "/authors?q=zzz")):
        await ui.go(path)
        await _every_width(ui, label)
    await ui.go("/authors?favorites=1")
    await expect(ui.page.locator(".author-row")).to_have_count(1)
    await ui.go(f"/authors/{shelf['long']}")
    await ui.page.get_by_role("button", name="Remove from my favorite authors").click()
    await ui.go("/authors?favorites=1")
    await expect(
        ui.page.get_by_text("You haven't chosen any favorite authors yet.")
    ).to_be_visible()
    await _every_width(ui, "favorites only empty")


@pytest.mark.ac("018/AC-18")
async def test_series_view_and_upcoming_layouts(
    ui: UI, seeded: Seeded, shelf: dict[str, uuid.UUID]
) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/catalog/series")
    await expect(ui.page.locator(".series-row")).not_to_have_count(0)
    await _every_width(ui, "series view")
    await ui.go("/upcoming")
    for heading in ("Now out", "On my list", "Also coming in the family catalog"):
        await expect(ui.page.get_by_role("heading", name=heading)).to_have_count(1)
    await _every_width(ui, "upcoming")
    await ui.go("/")
    await expect(
        ui.page.get_by_role("link", name="1 book you want to read is now out")
    ).to_be_visible()
    await _every_width(ui, "my books now out line")


@pytest.mark.ac("018/AC-18")
async def test_search_without_javascript(
    seeded: Seeded, shelf: dict[str, uuid.UUID], pw_browser: Browser, live_server: str
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go("/authors")
    await view.page.fill("#q", "prat")
    await view.page.click(".index-filters button[type=submit]")
    await view.page.wait_for_load_state()
    assert "q=prat" in view.page.url
    await expect(view.page.locator(".author-row .row-name")).to_have_text(["Terry Pratchett"])
    await view.page.fill("#q", "")
    await view.page.check("#favorites")
    await view.page.click(".index-filters button[type=submit]")
    await view.page.wait_for_load_state()
    await expect(view.page.locator(".author-row .row-name")).to_have_text(
        ["Douglas Preston and Lincoln Child and Friends"]
    )
    await view.go("/catalog/series")
    await view.page.fill("#q", "very long")
    await view.page.click(".index-filters button[type=submit]")
    await view.page.wait_for_load_state()
    await expect(view.page.locator(".series-row .row-name")).to_have_count(1)
    await context.close()


@pytest.mark.ac("018/AC-18")
async def test_any_author_in_three_steps_by_keyboard(ui: UI, seeded: Seeded) -> None:
    """SC-001: from any page, menu → Authors, type a name, choose the author."""
    await ui.sign_in(seeded.alice)
    await size(ui.page, SMALL)
    await ui.go(f"/entries/{seeded.entry_id}")
    await ui.page.get_by_role("link", name="Authors", exact=True).focus()
    await ui.page.keyboard.press("Enter")  # 1: the menu
    await ui.page.wait_for_url("**/authors")
    await ui.page.locator("#q").focus()
    await ui.page.keyboard.type("prat")  # 2: search, the list updates as I type
    await expect(ui.page.locator(".author-row")).to_have_count(1)
    await ui.page.locator(".author-row .row-name").focus()
    await ui.page.keyboard.press("Enter")  # 3: choose
    await ui.page.wait_for_url(f"**/authors/{seeded.author_id}")
    await expect(ui.page.get_by_role("link", name="Authors", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
