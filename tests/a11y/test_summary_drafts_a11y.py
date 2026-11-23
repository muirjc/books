"""Spec 012 (SC-005, AC-07): AI summary drafts in a real browser: layouts, axe, keyboard."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.async_api import expect

from book_tracker.services.errors import AiUnavailable
from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_layout_003 import IPAD, LAPTOP, LAPTOP_MIN, PHONE, SMALL, size
from tests.a11y.test_responsive import check
from tests.conftest import Factory
from tests.fakes import DRAFT_TEXT, FakeSummaryGenerator, good_draft

pytestmark = pytest.mark.a11y

NOTICE = "AI draft, not saved yet."
LONG_URL = "https://en.wikipedia.org/wiki/" + "A_Very_Long_Article_Name_" * 6


@pytest.fixture
def ai(live_summary_generator: FakeSummaryGenerator) -> Iterator[FakeSummaryGenerator]:
    live_summary_generator.results.clear()
    live_summary_generator.calls.clear()
    live_summary_generator.delay = 0.0
    live_summary_generator.configured = True
    yield live_summary_generator
    live_summary_generator.results.clear()
    live_summary_generator.delay = 0.0


async def _every_width(ui: UI, label: str) -> None:
    for wh in (SMALL, PHONE, IPAD, LAPTOP_MIN, LAPTOP):
        await size(ui.page, wh)
        await check(ui.page, f"{label} {wh}")
        if wh in (PHONE, IPAD, LAPTOP):
            await assert_no_axe_violations(ui.page, f"{label} {wh}")


@pytest.mark.ac("012/AC-07")
async def test_summary_draft_states(
    ui: UI, seeded: Seeded, factory: Factory, ai: FakeSummaryGenerator
) -> None:
    mort = await factory.scalar("SELECT id FROM book WHERE title = 'Mort'")
    page = f"/catalog/books/{mort}/summary"
    await ui.sign_in(seeded.alice)
    await ui.go(page)
    await _every_width(ui, "summary")
    # A draft with long sources and a series hint.
    long_sources = (LONG_URL, "https://openlibrary.org/works/OL1W")
    ai.results.append(good_draft(source_urls=long_sources, known_urls=frozenset(long_sources),
                                 series_name="Discworld", series_number="5"))  # fmt: skip
    await ui.page.get_by_role("button", name="Draft with AI").click()
    await expect(ui.page.get_by_text(NOTICE)).to_be_visible()
    await expect(ui.page.locator("#text")).to_have_value(DRAFT_TEXT)
    await _every_width(ui, "draft")
    # The confirmation before using the series (AC-21), as a full page.
    await ui.page.get_by_role("button", name="Use this series").click()
    await expect(ui.page.get_by_role("button", name="Save summary first")).to_be_visible()
    await _every_width(ui, "use series")
    # A failure message (no cached draft, so the AI is asked).
    await factory.execute("DELETE FROM summary_draft")
    await ui.go(page)
    ai.results.append(AiUnavailable())
    await ui.page.get_by_role("button", name="Draft with AI").click()
    await expect(ui.page.get_by_role("alert")).to_contain_text("didn't answer in time")
    await _every_width(ui, "failure")


@pytest.mark.ac("012/AC-07")
async def test_draft_review_save_by_keyboard(
    ui: UI, seeded: Seeded, factory: Factory, ai: FakeSummaryGenerator
) -> None:
    colour = await factory.scalar("SELECT id FROM book WHERE title = 'The Colour of Magic'")
    await ui.sign_in(seeded.alice)
    await ui.go(f"/catalog/books/{colour}/summary")
    ai.delay = 1.0
    await ui.page.get_by_role("button", name="Draft with AI").focus()
    await ui.page.keyboard.press("Enter")
    # While the AI works, the status says so and the buttons can't be pressed twice.
    drafting = ui.page.locator("#drafting")
    await expect(drafting).to_be_visible()
    await expect(drafting).to_have_attribute("role", "status")
    await expect(ui.page.get_by_role("button", name="Draft with AI")).to_be_disabled()
    await expect(ui.page.get_by_text(NOTICE)).to_be_visible(timeout=5000)
    await expect(drafting).to_be_hidden()
    textarea = ui.page.locator("#text")
    await textarea.focus()
    await ui.page.keyboard.press("End")
    await ui.page.keyboard.type(" Edited by keyboard.")
    save = ui.page.get_by_role("button", name="Save summary")
    await save.focus()
    await ui.page.keyboard.press("Enter")
    await ui.page.wait_for_url("**/summary?msg=saved")
    await expect(ui.page.get_by_text("(AI draft, edited)")).to_be_visible()


@pytest.mark.ac("012/AC-23")
async def test_add_a_book_draft(ui: UI, seeded: Seeded, ai: FakeSummaryGenerator) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/books/add")
    await ui.page.fill("#title", "Small Gods")
    await ui.page.fill("#author_name_0", "Terry Pratchett")
    await ui.page.get_by_role("button", name="Draft summary with AI").click()
    await expect(ui.page.get_by_text(NOTICE)).to_be_visible()
    await expect(ui.page.locator("#summary")).to_have_value(DRAFT_TEXT)
    await _every_width(ui, "add a book draft")
