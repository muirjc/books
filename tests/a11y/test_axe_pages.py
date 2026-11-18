"""T105: every page passes axe-core's WCAG 2.2 AA rules (FR-030, SC-007)."""

from __future__ import annotations

import pytest

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations

pytestmark = pytest.mark.a11y


async def test_sign_in_and_error_pages(ui: UI, seeded: Seeded) -> None:
    await ui.go("/sign-in")
    await assert_no_axe_violations(ui.page, "sign-in")
    await ui.page.fill("#login", "alice")
    await ui.page.fill("#password", "wrong-password")
    await ui.page.click("button[type=submit]")
    await assert_no_axe_violations(ui.page, "sign-in with error")
    await ui.sign_in(seeded.alice)
    await ui.go("/sign-in")  # now shows a recent profile
    await assert_no_axe_violations(ui.page, "sign-in with recent profiles")


async def test_change_password_page(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.forced)
    assert ui.page.url.endswith("/account/password")
    await assert_no_axe_violations(ui.page, "change password")
    await ui.page.click("button[type=submit]")
    await assert_no_axe_violations(ui.page, "change password with errors")


@pytest.mark.ac("001/AC-21")
async def test_member_pages(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    pages = {
        "list": "/",
        "list filtered": "/?status=reading&sort=-title",
        "list empty result": "/?q=zzzz",
        "add book": "/books/add",
        "entry": f"/entries/{seeded.entry_id}",
        "series": f"/series/{seeded.series_id}",
        "edit book": f"/catalog/books/{seeded.book_id}/edit",
        "edit author": f"/catalog/authors/{seeded.author_id}/edit",
        "edit series": f"/catalog/series/{seeded.series_id}/edit",
        "summary": f"/catalog/books/{seeded.book_id}/summary",
        "not found": "/entries/00000000-0000-4000-8000-000000000000",
    }
    for label, path in pages.items():
        await ui.go(path)
        await assert_no_axe_violations(ui.page, label)


async def test_add_book_with_errors_and_suggestions(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go("/books/add")
    await ui.page.click("button.button-primary")
    await ui.page.wait_for_load_state()
    await assert_no_axe_violations(ui.page, "add book with errors")
    await ui.go("/books/add")
    await ui.page.fill("#author_name_0", "Terr")
    await ui.page.wait_for_selector("#author_name_0-listbox [role=option]")
    await assert_no_axe_violations(ui.page, "add book with suggestions open")


async def test_remove_confirmation(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    await ui.go(f"/entries/{seeded.entry_id}")
    await ui.page.click("text=Remove from my list")
    await ui.page.wait_for_load_state()
    await assert_no_axe_violations(ui.page, "confirm remove")


async def test_admin_pages(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.admin)
    for label, path in {"accounts": "/admin/users", "new account": "/admin/users/new"}.items():
        await ui.go(path)
        await assert_no_axe_violations(ui.page, label)
    await ui.page.click("button.button-primary")
    await ui.page.wait_for_load_state()
    await assert_no_axe_violations(ui.page, "new account with errors")
