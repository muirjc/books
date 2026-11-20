"""T107: usable at phone width (FR-026, SC-006).

At 360 × 740 no page scrolls sideways. Form controls, buttons and navigation links are at
least 44 × 44 px; checkboxes at least 24 × 24 px. Links inside running text are exempt,
as in WCAG 2.2 success criterion 2.5.8.
"""

from __future__ import annotations

import pytest
from playwright.async_api import Page

from tests.a11y.conftest import UI, Seeded

pytestmark = pytest.mark.a11y

SMALL_TARGETS = """() => {
  const problems = [];
  const visible = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const check = (sel, min) => document.querySelectorAll(sel).forEach(e => {
    if (!visible(e) || e.closest('.visually-hidden')) return;
    const r = e.getBoundingClientRect();
    if (r.width < min - 0.5 || r.height < min - 0.5)
      problems.push(`${e.tagName}#${e.id || ''} "${(e.textContent||'').trim().slice(0,30)}" `
                    + `${Math.round(r.width)}x${Math.round(r.height)}`);
  });
  check('button, select, textarea, input:not([type=hidden]):not([type=checkbox])', 44);
  check('input[type=checkbox]', 24);
  check('nav a, .brand, .button', 44);
  return problems;
}"""


async def check(page: Page, label: str) -> None:
    widths = await page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    assert widths[0] <= widths[1], f"{label}: page scrolls sideways ({widths})"
    problems = await page.evaluate(SMALL_TARGETS)
    assert problems == [], f"{label}: small targets {problems}"


@pytest.mark.ac("001/AC-21")
async def test_phone_width(ui: UI, seeded: Seeded) -> None:
    await ui.page.set_viewport_size({"width": 360, "height": 740})
    await ui.go("/sign-in")
    await check(ui.page, "sign-in")
    await ui.sign_in(seeded.alice)
    for label, path in {
        "list": "/",
        "add book": "/books/add",
        "entry": f"/entries/{seeded.entry_id}",
        "series": f"/series/{seeded.series_id}",
        "edit book": f"/catalog/books/{seeded.book_id}/edit",
        "edit author": f"/catalog/authors/{seeded.author_id}/edit",
        "edit series": f"/catalog/series/{seeded.series_id}/edit",
        "summary": f"/catalog/books/{seeded.book_id}/summary",
    }.items():
        await ui.go(path)
        await check(ui.page, label)


async def test_phone_width_admin(ui: UI, seeded: Seeded) -> None:
    await ui.page.set_viewport_size({"width": 360, "height": 740})
    await ui.sign_in(seeded.admin)
    for label, path in {"accounts": "/admin/users", "new account": "/admin/users/new"}.items():
        await ui.go(path)
        await check(ui.page, label)


ROW_TOPS = """() => [...document.querySelectorAll('.book-list > li')].map(li =>
  [...li.children].map(c => Math.round(c.getBoundingClientRect().top)))"""


async def test_my_books_one_line_per_book(ui: UI, seeded: Seeded) -> None:
    """On a tablet or wider, each book's title, authors and status share one line."""
    await ui.page.set_viewport_size({"width": 1024, "height": 768})
    await ui.sign_in(seeded.alice)
    await ui.go("/")
    rows = await ui.page.evaluate(ROW_TOPS)
    assert rows, "no books listed"
    for tops in rows:
        assert max(tops) - min(tops) <= 2, rows
    await check(ui.page, "list at tablet width")
