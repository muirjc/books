"""Spec 008: the author pages in a real browser (marker ``a11y``)."""

from __future__ import annotations

import pytest
from playwright.async_api import Browser

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory

pytestmark = pytest.mark.a11y


@pytest.fixture
async def typo(seeded: Seeded, factory: Factory) -> str:
    """An author no book lists, beside the seeded Terry Pratchett (who has books)."""
    return str(await factory.author("J DM Robb", seeded.alice))


async def _targets(ui: UI, selector: str, where: str) -> None:
    for box in await ui.page.eval_on_selector_all(
        selector,
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {name: e.textContent.trim(), w: r.width, h: r.height}; })",
    ):
        assert box["h"] >= 44 and box["w"] >= 44, (where, box)


@pytest.mark.ac("008/AC-09")
async def test_author_pages_layout(ui: UI, seeded: Seeded, typo: str) -> None:
    await ui.sign_in(seeded.alice)
    pages = {
        "unused": "/catalog/authors/unused",
        "no books": f"/catalog/authors/{typo}/edit",
        "with books": f"/catalog/authors/{seeded.author_id}/edit",
    }
    for name, path in pages.items():
        await ui.go(path)
        for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
            await size(ui.page, wh)
            await check(ui.page, f"{name} {wh}")
            await _targets(ui, "main .link-list a", f"{name} {wh}")
            if wh in (PHONE, IPAD, LAPTOP):
                await assert_no_axe_violations(ui.page, f"{name} {wh}")
    await ui.go(f"/catalog/authors/{typo}/edit")
    await ui.page.get_by_role("button", name="Delete author").click()
    await ui.page.wait_for_load_state()
    for wh in (SMALL, PHONE, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"confirm {wh}")
        if wh != SMALL:
            await assert_no_axe_violations(ui.page, f"confirm {wh}")


@pytest.mark.ac("008/AC-09")
@pytest.mark.ac("008/AC-04")
async def test_delete_without_js(
    seeded: Seeded, typo: str, pw_browser: Browser, live_server: str
) -> None:
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    await view.go("/authors")  # spec 018: the link moved from My books
    await view.page.get_by_role("link", name="Authors with no books (1)").click()
    await view.page.wait_for_load_state()
    await view.page.get_by_role("link", name="J DM Robb").click()
    await view.page.wait_for_load_state()
    await view.page.get_by_role("button", name="Delete author").click()
    await view.page.wait_for_load_state()
    assert "Delete “J DM Robb” from the family catalog?" in await view.page.inner_text("h1")
    await view.page.get_by_role("button", name="Delete", exact=True).click()
    await view.page.wait_for_load_state()
    status = view.page.get_by_role("status").filter(has_text="Deleted")
    assert " ".join((await status.inner_text()).split()) == "Deleted “J DM Robb”."
    assert (
        "Every author in the family catalog has at least one book."
        in await view.page.inner_text("main")
    )
    await context.close()
