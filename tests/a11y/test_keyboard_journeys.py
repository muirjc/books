"""T106: the main journeys work with the keyboard alone (FR-030, SC-007)."""

from __future__ import annotations

import pytest
from playwright.async_api import Page

from tests.a11y.conftest import UI, Seeded
from tests.conftest import without_finished

pytestmark = pytest.mark.a11y


async def focused(page: Page) -> str:
    """A short description of the focused element: id, or tag and text."""
    result: str = await page.evaluate(
        "() => { const e = document.activeElement;"
        " return e.id || (e.tagName + ':' + (e.textContent || '').trim()); }"
    )
    return result


async def focus_is_visible(page: Page) -> bool:
    result: bool = await page.evaluate(
        "() => { const s = getComputedStyle(document.activeElement);"
        " return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2; }"
    )
    return result


async def tab_to(page: Page, target: str, limit: int = 40) -> list[str]:
    """Press Tab until ``target`` is focused; returns the focus order on the way."""
    order: list[str] = []
    for _ in range(limit):
        await page.keyboard.press("Tab")
        current = await focused(page)
        order.append(current)
        if current == target:
            assert await focus_is_visible(page), f"focus on {target} is not visible"
            return order
    raise AssertionError(f"{target} not reached by Tab; order was {order}")


async def press_button(page: Page, text: str, limit: int = 40) -> None:
    for _ in range(limit):
        await page.keyboard.press("Tab")
        if await focused(page) == f"BUTTON:{text}":
            assert await focus_is_visible(page)
            async with page.expect_navigation():
                await page.keyboard.press("Enter")
            return
    raise AssertionError(f"button {text!r} not reached by Tab")


@pytest.mark.ac("001/AC-01")
async def test_sign_in(ui: UI, seeded: Seeded) -> None:
    await ui.go("/sign-in")
    order = await tab_to(ui.page, "login")
    assert order[0].startswith("A:Skip to main content")
    await ui.page.keyboard.type(seeded.alice.login)
    order = await tab_to(ui.page, "password")
    assert order == ["password"]  # login → password, nothing in between
    await ui.page.keyboard.type(seeded.alice.password)
    async with ui.page.expect_navigation():
        await ui.page.keyboard.press("Enter")
    assert ui.page.url == ui.base_url + "/"
    assert "My books" in await ui.page.inner_text("h1")


@pytest.mark.ac("001/AC-15")
async def test_add_book_choosing_author_from_suggestions(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/books/add")
    await tab_to(ui.page, "title")
    await ui.page.keyboard.type("Small Gods")
    await tab_to(ui.page, "author_name_0")
    await ui.page.keyboard.type("Terr")
    await ui.page.wait_for_selector("#author_name_0-listbox [role=option]")
    assert await ui.page.get_attribute("#author_name_0", "aria-expanded") == "true"
    await ui.page.keyboard.press("ArrowDown")
    active = await ui.page.get_attribute("#author_name_0", "aria-activedescendant")
    assert active and await ui.page.get_attribute(f"#{active}", "aria-selected") == "true"
    await ui.page.keyboard.press("Enter")
    assert await ui.page.input_value("#author_name_0") == "Terry Pratchett"
    assert await ui.page.input_value("#author_id_0") == seeded.author_id
    await press_button(ui.page, "Add to my list")
    assert without_finished(ui.page.url).endswith("/?msg=added")
    assert "Small Gods" in await ui.page.inner_text("#reading-list")


@pytest.mark.ac("001/AC-08")
async def test_edit_entry_status(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/entries/{seeded.entry_id}")
    await tab_to(ui.page, "status")
    await ui.page.keyboard.press("ArrowDown")  # Finished → Reading
    assert await ui.page.input_value("#status") == "reading"
    await press_button(ui.page, "Save")
    assert "msg=saved" in ui.page.url
    assert await ui.page.input_value("#status") == "reading"


@pytest.mark.ac("001/AC-28")
async def test_switch_user(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await press_button(ui.page, "Switch user")
    assert ui.page.url.endswith("/sign-in")
    order = await tab_to(ui.page, "BUTTON:Alice (alice)")
    assert "login" not in order  # profiles come before the form
    await ui.page.keyboard.press("Enter")
    assert await ui.page.input_value("#login") == "alice"
    assert await focused(ui.page) == "password"
