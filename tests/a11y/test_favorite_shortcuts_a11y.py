"""Spec 017 AC-14: favorite stars, the empty favorites page and the offer, in a real
browser (marker ``a11y``)."""

from __future__ import annotations

import re
import uuid

import pytest
from playwright.async_api import Browser, Page, expect

from tests.a11y.conftest import UI, Seeded
from tests.a11y.test_book_page_a11y import _every_width
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.conftest import Factory

pytestmark = pytest.mark.a11y

# For each author-and-star pair: the link's and the button's vertical centres.
# The link's last line box, so a long name may wrap as long as the star stays with its end.
PAIRS = """() => Array.from(document.querySelectorAll('.author-pair')).map(p => {
  const rects = p.querySelector('a').getClientRects();
  const a = rects[rects.length - 1];
  const b = p.querySelector('button').getBoundingClientRect();
  return [p.textContent.trim(), a.top + a.height / 2, b.top + b.height / 2, b.left - a.right];
})"""


async def _pairs_together(page: Page, label: str) -> None:
    """A star stays on its author's line, just after the name."""
    for width in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(page, width)
        for name, link_y, star_y, gap in await page.evaluate(PAIRS):
            assert abs(link_y - star_y) < 16, f"{label} {width}: {name} wrapped apart"
            assert 0 <= gap < 24, f"{label} {width}: {name} star not next to the name ({gap})"
    await size(page, LAPTOP)


async def _star_follows_link(page: Page, author: str) -> None:
    await page.get_by_role("link", name=author, exact=True).first.focus()
    await page.keyboard.press("Tab")
    focused = await page.evaluate("() => document.activeElement.textContent.trim()")
    assert author in focused and "my favorite authors" in focused, focused


@pytest.fixture
async def shelf(seeded: Seeded, factory: Factory) -> dict[str, uuid.UUID]:
    p = uuid.UUID(seeded.author_id)  # Terry Pratchett
    g = await factory.author("Neil Gaiman", seeded.ben)
    # PR #42 review: a long name must wrap on a phone, not push the page sideways.
    long = await factory.author("Douglas Preston and Lincoln Child and Friends", seeded.ben)
    pen = await factory.author("Robert Galbraith", seeded.ben, is_pen_name=True,
                               real_name="J. K. Rowling")  # fmt: skip
    omens = await factory.book("Good Omens: The Nice and Accurate Prophecies of Agnes Nutter",
                               seeded.ben, author_ids=[p, g, pen, long])  # fmt: skip
    mort = await factory.book("Mort", seeded.ben, author_ids=[p])
    await factory.favorite(seeded.alice, g)
    return {
        "p": p, "omens": omens, "mort": mort,
        "e_omens": await factory.entry(seeded.alice, omens),
        "e_mort": await factory.entry(seeded.alice, mort),
    }  # fmt: skip


@pytest.mark.ac("017/AC-14")
async def test_stars_on_the_book_and_entry_pages(
    ui: UI, seeded: Seeded, shelf: dict[str, uuid.UUID]
) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/books/{shelf['omens']}")
    await expect(
        ui.page.get_by_role("button", name="Add Terry Pratchett to my favorite authors")
    ).to_have_count(1)
    await expect(
        ui.page.get_by_role("button", name="Remove Neil Gaiman from my favorite authors")
    ).to_have_count(1)
    await _every_width(ui, "book page stars")
    await _pairs_together(ui.page, "book page")
    for author in ("Terry Pratchett", "Neil Gaiman", "Robert Galbraith"):
        await _star_follows_link(ui.page, author)
    # A star tap keeps the reader on the page, with the notice.
    async with ui.page.expect_navigation():
        await ui.page.get_by_role(
            "button", name="Add Terry Pratchett to my favorite authors"
        ).click()
    await expect(ui.page.locator("#favorite-notice")).to_have_text(
        "Added Terry Pratchett to your favorite authors."
    )
    assert ui.page.url.endswith("#favorite-notice"), ui.page.url
    await _every_width(ui, "book page notice")

    await ui.go(f"/entries/{shelf['e_omens']}")
    await _every_width(ui, "entry page stars")
    await _pairs_together(ui.page, "entry page")
    await _star_follows_link(ui.page, "Neil Gaiman")


@pytest.mark.ac("017/AC-14")
async def test_empty_favorites_page(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/authors/favorites")
    await expect(ui.page.get_by_role("link", name="Browse the Catalog")).to_have_count(1)
    await _every_width(ui, "empty favorites")


@pytest.mark.ac("017/AC-14")
async def test_the_offer(ui: UI, seeded: Seeded, shelf: dict[str, uuid.UUID]) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/entries/{shelf['e_mort']}?msg=saved&finished={shelf['mort']}")
    offer = ui.page.get_by_role("button", name="Add Terry Pratchett to my favorite authors")
    await expect(offer).to_have_count(2)  # the offer, and the star in More
    await expect(ui.page.locator(".favorite-offer")).to_contain_text(
        re.compile(r"You've finished \d books by Terry Pratchett\.")
    )
    await _every_width(ui, "offer")
    async with ui.page.expect_navigation():
        await offer.first.click()
    await expect(ui.page.locator("#favorite-notice")).to_contain_text("Added Terry Pratchett")
    await expect(ui.page.locator(".favorite-offer")).to_have_count(0)
    await _every_width(ui, "offer accepted")


@pytest.mark.ac("017/AC-14")
async def test_star_without_javascript(
    seeded: Seeded, pw_browser: Browser, live_server: str, shelf: dict[str, uuid.UUID]
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go(f"/books/{shelf['mort']}")
    async with view.page.expect_navigation():
        await view.page.get_by_role(
            "button", name="Add Terry Pratchett to my favorite authors"
        ).click()
    assert f"/books/{shelf['mort']}?favorited={shelf['p']}" in view.page.url
    await expect(view.page.locator("#favorite-notice")).to_contain_text("Added Terry Pratchett")
    await context.close()
