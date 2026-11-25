"""Spec 003: responsive layout for phone, tablet and laptop (marker ``a11y``).

Layout is checked from element boxes in a real browser at the widths in research R8.
Two boxes are "on one line" when their vertical extents overlap.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from playwright.async_api import Browser, Page

from tests.a11y.conftest import UI, Seeded, assert_no_axe_violations
from tests.a11y.test_import_a11y import KEY, ol  # noqa: F401 (fixture)
from tests.a11y.test_responsive import check
from tests.conftest import Factory
from tests.fakes import FakeBookSource, listing, work

pytestmark = pytest.mark.a11y

SMALL = (360, 740)
PHONE = (390, 844)
IPAD_MINI = (768, 1024)
IPAD = (820, 1180)
LAPTOP_MIN = (1024, 768)
LAPTOP = (1440, 900)
WIDTHS = (SMALL, PHONE, IPAD_MINI, IPAD, LAPTOP_MIN, LAPTOP)

BOXES = """sel => [...document.querySelectorAll(sel)].map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {cls: e.className, top: r.top, bottom: r.bottom, left: r.left, right: r.right,
          width: r.width, height: r.height,
          visible: r.width > 0 && r.height > 0 && s.visibility !== 'hidden'};
})"""

ROW_CELLS = """() => [...document.querySelectorAll('.book-list > li')].map(li =>
  [...li.children].map(c => {
    const r = c.getBoundingClientRect();
    return {cls: c.className.split(' ')[0], top: r.top, bottom: r.bottom, left: r.left,
            visible: r.width > 0 && r.height > 0, shown: getComputedStyle(c).display !== 'none'};
  }))"""

VISIBLE_ROWS = """() => [...document.querySelectorAll('.book-list > li')].filter(li => {
  const r = li.getBoundingClientRect();
  return r.top >= 0 && r.bottom <= window.innerHeight;
}).length"""


def same_line(boxes: list[dict[str, Any]]) -> bool:
    shown = [b for b in boxes if b["visible"]]
    return bool(shown) and max(b["top"] for b in shown) < min(b["bottom"] for b in shown)


async def size(page: Page, wh: tuple[int, int]) -> None:
    await page.set_viewport_size({"width": wh[0], "height": wh[1]})


async def boxes(page: Page, selector: str) -> list[dict[str, Any]]:
    return list(await page.evaluate(BOXES, selector))


async def box(page: Page, selector: str) -> dict[str, Any]:
    found = await boxes(page, selector)
    assert found, selector
    return found[0]


@pytest.fixture
async def many_books(seeded: Seeded, factory: Factory) -> Seeded:
    author = await factory.author("Ursula K. Le Guin", seeded.alice)
    series = await factory.series("Earthsea", seeded.alice)
    for n in range(1, 31):
        book = await factory.book(
            f"Book {n:02} of a Reasonably Long Title", seeded.alice, author_ids=[author],
            series_id=series if n <= 6 else None, series_number=str(n) if n <= 6 else None,
        )  # fmt: skip
        await factory.entry(
            seeded.alice, book, finished_on=date(2026, 3, n % 28 + 1), times_read=n % 3 + 1
        )
    return seeded


# --------------------------------------------------------------------------- all pages


def _pages(seeded: Seeded) -> dict[str, str]:
    return {
        "list": "/",
        "add book": "/books/add",
        "entry": f"/entries/{seeded.entry_id}",
        "series": f"/series/{seeded.series_id}",
        "edit book": f"/catalog/books/{seeded.book_id}/edit",
        "edit author": f"/catalog/authors/{seeded.author_id}/edit",
        "edit series": f"/catalog/series/{seeded.series_id}/edit",
        "summary": f"/catalog/books/{seeded.book_id}/summary",
        "change password": "/account/password",
        "import": "/import",
        "import works": f"/import/authors/{KEY}",
    }


async def _session(pw_browser: Browser, live_server: str, user: Any) -> UI:
    view = UI(await (await pw_browser.new_context()).new_page(), live_server)
    await view.sign_in(user)
    return view


@pytest.mark.ac("003/AC-19")
@pytest.mark.ac("003/AC-20")
async def test_no_sideways_scroll_at_every_width(
    seeded: Seeded,
    pw_browser: Browser,
    live_server: str,
    ol: FakeBookSource,  # noqa: F811
) -> None:
    admin = await _session(pw_browser, live_server, seeded.admin)
    alice = await _session(pw_browser, live_server, seeded.alice)
    admin_pages = {"accounts": "/admin/users", "new account": "/admin/users/new"}
    for wh in WIDTHS:
        for view, pages in ((admin, admin_pages), (alice, _pages(seeded))):
            await size(view.page, wh)
            for label, path in pages.items():
                await view.go(path)
                await check(view.page, f"{label} at {wh[0]}")
    for view in (admin, alice):
        await view.page.context.close()


# --------------------------------------------------------------------------- US1 My books


@pytest.mark.ac("003/AC-01")
@pytest.mark.ac("003/AC-02")
async def test_my_books_laptop(ui: UI, many_books: Seeded) -> None:
    await size(ui.page, LAPTOP)
    await ui.sign_in(many_books.alice)
    await ui.go("/")
    rows = await ui.page.evaluate(ROW_CELLS)
    assert len(rows) == 32
    for cells in rows:
        shown = {c["cls"] for c in cells if c["shown"]}
        assert {"book-title", "book-meta", "book-status", "book-finished"} <= shown, cells
        assert same_line(cells), cells
    times = [c for cells in rows for c in cells if c["cls"] == "book-times" and c["shown"]]
    assert times, "times read shown on laptop"
    assert (await box(ui.page, ".book-list"))["width"] > 1200
    filters = await boxes(ui.page, ".filters .field, .filters button[type=submit]")
    assert len(filters) == 7 and same_line(filters), filters  # + Upcoming only (spec 007)
    visible = await ui.page.evaluate(VISIBLE_ROWS)
    assert visible >= 12, f"SC-001: {visible} books visible"


@pytest.mark.ac("003/AC-03")
async def test_my_books_tablet(ui: UI, many_books: Seeded) -> None:
    await ui.sign_in(many_books.alice)
    for wh in (IPAD_MINI, IPAD):
        await size(ui.page, wh)
        await ui.go("/")
        for cells in await ui.page.evaluate(ROW_CELLS):
            shown = {c["cls"] for c in cells if c["shown"]}
            assert {"book-title", "book-meta", "book-status"} <= shown, (wh, cells)
            assert "book-times" not in shown, (wh, cells)
            assert same_line(cells), (wh, cells)


@pytest.mark.ac("003/AC-04")
@pytest.mark.ac("003/AC-05")
@pytest.mark.ac("003/AC-06")
async def test_my_books_phone(ui: UI, many_books: Seeded) -> None:
    await size(ui.page, PHONE)
    await ui.sign_in(many_books.alice)
    await ui.go("/")
    for cells in await ui.page.evaluate(ROW_CELLS):
        by = {c["cls"]: c for c in cells}
        assert not by["book-finished"]["shown"] and not by["book-times"]["shown"], cells
        title, meta, status = by["book-title"], by["book-meta"], by["book-status"]
        assert title["bottom"] <= meta["top"] + 1, cells  # title on line one
        assert same_line([meta, status]), cells  # meta and status share line two
    assert not (await box(ui.page, "#sort"))["visible"]
    toggle = ui.page.locator(".filters-toggle")
    assert await toggle.is_visible()
    assert await toggle.get_attribute("aria-expanded") == "false"
    visible = await ui.page.evaluate(VISIBLE_ROWS)
    assert visible >= 6, f"SC-002: {visible} books visible"
    await toggle.click()
    assert await toggle.get_attribute("aria-expanded") == "true"
    assert (await box(ui.page, "#sort"))["visible"]
    await ui.go("/?status=finished")
    assert (await box(ui.page, "#sort"))["visible"]
    assert await ui.page.locator(".filters-toggle").get_attribute("aria-expanded") == "true"


# --------------------------------------------------------------------------- US2 width, header


@pytest.mark.ac("003/AC-07")
async def test_page_width(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    for wh in (LAPTOP, (2560, 1440)):
        await size(ui.page, wh)
        await ui.go("/")
        main = await box(ui.page, "main")
        assert 1200 <= main["width"] <= 1320, (wh, main)
        assert abs(main["left"] - (wh[0] - main["right"])) <= 2, (wh, main)  # centred


@pytest.mark.ac("003/AC-08")
@pytest.mark.ac("003/AC-09")
async def test_header_rows(seeded: Seeded, pw_browser: Browser, live_server: str) -> None:
    for user in (seeded.alice, seeded.admin):
        view = await _session(pw_browser, live_server, user)
        page = view.page
        for wh in (LAPTOP_MIN, LAPTOP):
            await size(page, wh)
            await view.go("/")
            parts = await boxes(page, ".brand, .nav-list a, .account-actions button")
            assert same_line(parts), (user.login, wh, parts)
        for wh in (IPAD_MINI, IPAD):
            await size(page, wh)
            await view.go("/")
            links = await boxes(page, ".nav-list a")
            assert same_line(links), (user.login, wh, links)
        await page.context.close()


CH_WIDTH = """sel => [...document.querySelectorAll(sel)].map(e => {
  const s = document.createElement('span');
  s.textContent = '0'.repeat(75);
  s.style.font = getComputedStyle(e).font;
  s.style.position = 'absolute'; s.style.whiteSpace = 'nowrap'; s.style.visibility = 'hidden';
  document.body.append(s);
  const limit = s.getBoundingClientRect().width; s.remove();
  return [Math.round(e.getBoundingClientRect().width), Math.round(limit)];
})"""


@pytest.mark.ac("003/AC-10")
async def test_readable_line_length(ui: UI, seeded: Seeded) -> None:
    await size(ui.page, LAPTOP)
    await ui.sign_in(seeded.alice)
    for path in (f"/entries/{seeded.entry_id}", f"/catalog/books/{seeded.book_id}/summary", "/"):
        await ui.go(path)
        for width, limit in await ui.page.evaluate(CH_WIDTH, "main p"):
            assert width <= limit + 1, (path, width, limit)
    await ui.go("/account/password")
    for field in await boxes(ui.page, "main input[type=password]"):
        assert field["width"] <= 640 + 1, field


# --------------------------------------------------------------------------- US3 forms

FORM = "document.querySelector('.form-columns')?.closest('form')"


@pytest.mark.ac("003/AC-11")
@pytest.mark.ac("003/AC-12")
@pytest.mark.ac("003/AC-13")
@pytest.mark.ac("003/AC-14")
async def test_book_forms_by_size(ui: UI, seeded: Seeded) -> None:
    await ui.sign_in(seeded.alice)
    for path in (f"/entries/{seeded.entry_id}", "/books/add"):
        await size(ui.page, LAPTOP)
        await ui.go(path)
        left, right = await boxes(ui.page, ".form-columns > *")
        assert abs(left["top"] - right["top"]) <= 2 and right["left"] > left["right"], path
        # The submit buttons follow the two columns, alone or in a row (spec 004 .form-actions).
        submit = await box(
            ui.page,
            ".form-columns ~ button[type=submit],"
            " .form-columns ~ .form-actions button[type=submit]",
        )
        assert submit["top"] >= max(left["bottom"], right["bottom"]), path
        tall = await ui.page.evaluate(f"{FORM}.getBoundingClientRect().height")
        await size(ui.page, IPAD)
        assert same_line(await boxes(ui.page, "#series_name, #series_number")), path
        assert same_line(await boxes(ui.page, "#status, #finished_on")), path
        await size(ui.page, PHONE)
        fields = [f for f in await boxes(ui.page, "form .field") if f["visible"]]
        fields.sort(key=lambda f: f["top"])
        for above, below in zip(fields, fields[1:], strict=False):
            assert below["top"] >= above["bottom"] - 1, (path, above, below)
        if path.startswith("/entries/"):
            narrow = await ui.page.evaluate(f"{FORM}.getBoundingClientRect().height")
            assert tall <= 0.6 * narrow, f"SC-004: {tall:.0f} vs {narrow:.0f}"


FOCUS_ID = "() => document.activeElement.id || document.activeElement.textContent.trim()"


@pytest.mark.ac("003/AC-15")
@pytest.mark.ac("003/AC-16")
async def test_book_form_focus_order_and_rotation(ui: UI, seeded: Seeded) -> None:
    await size(ui.page, LAPTOP)
    await ui.sign_in(seeded.alice)
    await ui.go(f"/entries/{seeded.entry_id}")
    await ui.page.focus("#title")
    seen = ["title"]
    for _ in range(30):
        if seen[-1] == "Save":
            break
        await ui.page.keyboard.press("Tab")
        focused = await ui.page.evaluate(FOCUS_ID)
        if focused != seen[-1]:  # a date field has a Tab stop per part
            seen.append(focused)
    # Spec 007 adds release_date and pre_ordered.
    assert seen == ["title", "author_name_0", "author_name_1", "author_name_2", "series_name",
                    "series_number", "isbn_13", "release_date", "status", "finished_on",
                    "times_read", "pre_ordered", "notes", "Save"]  # fmt: skip
    await size(ui.page, IPAD)
    await ui.page.fill("#title", "Mort, typed")
    await ui.page.fill("#notes", "typed before turning")
    await size(ui.page, (1180, 820))
    assert await ui.page.input_value("#title") == "Mort, typed"
    assert await ui.page.input_value("#notes") == "typed before turning"


# --------------------------------------------------------------------------- US4 import


@pytest.mark.ac("003/AC-17")
async def test_import_laptop(ui: UI, seeded: Seeded, ol: FakeBookSource) -> None:  # noqa: F811
    await size(ui.page, LAPTOP)
    await ui.sign_in(seeded.alice)
    await ui.go(f"/import/authors/{KEY}")
    controls = await boxes(ui.page, "#status, .import-controls .field, .import-controls button")
    assert len(controls) == 5 and same_line(controls), controls
    table, main = await box(ui.page, ".import-table"), await box(ui.page, "main h1")
    assert abs(table["width"] - main["width"]) <= 2, (table, main)


@pytest.mark.ac("003/AC-18")
async def test_import_columns_same_per_author(
    ui: UI,
    seeded: Seeded,
    ol: FakeBookSource,  # noqa: F811
) -> None:
    ol.works["OL2A"] = listing("OL2A", [
        work(n, "A Very Long Title, Being The Complete And Unabridged Edition With Notes",
             tuple(f"Co-Author Number {i}" for i in range(6)), year=None)
        for n in range(100, 110)
    ])  # fmt: skip
    await ui.sign_in(seeded.alice)
    for wh in (IPAD, LAPTOP):
        await size(ui.page, wh)
        widths = []
        for key in (KEY, "OL2A"):
            await ui.go(f"/import/authors/{key}")
            widths.append(await ui.page.eval_on_selector_all(
                ".import-table thead th", "ths => ths.map(th => Math.round(th.offsetWidth))"
            ))  # fmt: skip
        assert widths[0] == widths[1], (wh, widths)


# --------------------------------------------------------------------------- accessibility


@pytest.mark.ac("003/AC-21")
async def test_axe_by_size(ui: UI, seeded: Seeded, ol: FakeBookSource) -> None:  # noqa: F811
    for wh in (PHONE, IPAD, LAPTOP):
        await size(ui.page, wh)
        await ui.page.context.clear_cookies()
        await ui.go("/sign-in")
        await assert_no_axe_violations(ui.page, f"sign in at {wh[0]}")
    await ui.sign_in(seeded.alice)
    for wh in (PHONE, IPAD, LAPTOP):
        await size(ui.page, wh)
        for path in ("/", "/books/add", f"/entries/{seeded.entry_id}", f"/import/authors/{KEY}"):
            await ui.go(path)
            await assert_no_axe_violations(ui.page, f"{path} at {wh[0]}")


OVERFLOW = """() => [...document.querySelectorAll('main *')].filter(e => {
  const p = e.parentElement; if (!p) return false;
  const s = getComputedStyle(p);
  if (s.display === 'contents') return false;  // no box of its own
  if (s.overflowX !== 'visible' || s.textOverflow === 'ellipsis') return false;
  return e.getBoundingClientRect().right > p.getBoundingClientRect().right + 1;
}).map(e => e.tagName + '.' + e.className).slice(0, 5)"""


@pytest.mark.ac("003/AC-22")
async def test_200_percent_text(
    many_books: Seeded,
    pw_browser: Browser,
    live_server: str,
    ol: FakeBookSource,  # noqa: F811
) -> None:
    """A 1,280 × 900 window at 200% zoom has a 640 × 450 CSS viewport (research R8)."""
    context = await pw_browser.new_context(
        viewport={"width": 640, "height": 450}, device_scale_factor=2
    )
    view = UI(await context.new_page(), live_server)
    seeded = many_books
    await view.sign_in(seeded.alice)
    await view.go("/")
    for cells in await view.page.evaluate(ROW_CELLS):
        shown = {c["cls"] for c in cells if c["shown"]}
        assert "book-times" not in shown and same_line(cells), cells  # tablet layout
    assert same_line(await boxes(view.page, ".nav-list a"))
    for path in ("/", "/books/add", f"/entries/{seeded.entry_id}", f"/import/authors/{KEY}"):
        await view.go(path)
        await check(view.page, f"200% {path}")
        assert await view.page.evaluate(OVERFLOW) == [], path
    await context.close()


@pytest.fixture(autouse=True)
def _clear_source(live_book_source: FakeBookSource) -> Iterator[None]:
    yield
    live_book_source.works.pop("OL2A", None)


# --------------------------------------------------------------------------- review fixes


@pytest.mark.ac("003/AC-05")
async def test_phone_filters_without_javascript(
    seeded: Seeded, pw_browser: Browser, live_server: str
) -> None:
    """Without JavaScript the toggle stays hidden and search spans the filter row."""
    context = await pw_browser.new_context(java_script_enabled=False)
    view = UI(await context.new_page(), live_server)
    await view.sign_in(seeded.alice)
    for wh in (SMALL, PHONE):
        await size(view.page, wh)
        await view.go("/")
        assert not (await box(view.page, ".filters-toggle"))["visible"], wh
        search, status = await box(view.page, "#q"), await box(view.page, "#status")
        assert status["visible"], wh
        assert abs(search["right"] - status["right"]) <= 1, (wh, search, status)
    await context.close()


async def test_js_flag_set_before_first_paint(ui: UI, seeded: Seeded) -> None:
    """The fold (html.js flag and toggle) comes from its own blocking script, so phones
    never see the filters open and then jump shut, and it works even if app.js fails."""
    await size(ui.page, PHONE)
    await ui.sign_in(seeded.alice)
    await ui.page.route("**/static/js/app.js", lambda route: route.abort())
    await ui.go("/")
    assert await ui.page.evaluate("document.documentElement.classList.contains('js')")
    assert not (await box(ui.page, "#sort"))["visible"]
    await ui.page.click(".filters-toggle")
    assert (await box(ui.page, "#sort"))["visible"]


@pytest.mark.ac("003/AC-01")
async def test_series_and_summary_lists_keep_their_layout(
    ui: UI, seeded: Seeded, factory: Factory
) -> None:
    """Only My books uses the one-line book rows: the series number stays first, and
    earlier summaries wrap in full."""
    long_text = "An earlier summary that runs well past one line of text. " * 12
    await factory.execute(
        "INSERT INTO book_summary (id, book_id, text, origin, created_by, is_current) "
        "VALUES (gen_random_uuid(), :b, :t, 'manual', :u, false)",
        b=seeded.book_id, t=long_text, u=seeded.alice.id,
    )  # fmt: skip
    await ui.sign_in(seeded.alice)
    for wh in (SMALL, IPAD, LAPTOP):
        await size(ui.page, wh)
        await ui.go(f"/series/{seeded.series_id}")
        rows = await ui.page.evaluate("""() => [...document.querySelectorAll('ol > li')].map(li =>
          [...li.children].map(c => { const r = c.getBoundingClientRect();
            return {cls: c.className, top: r.top, bottom: r.bottom, left: r.left,
                    right: r.right, width: r.width, height: r.height, visible: true}; }))""")
        assert rows, wh
        # Spec 006 rows: number, title, authors, status (and an Add link), or a gap row.
        books = [cells for cells in rows if cells[1]["cls"] == "book-title"]
        assert books, wh
        for cells in books:
            badge, title, meta = cells[:3]
            assert badge["cls"] == "badge", cells
            assert badge["right"] <= title["left"] and same_line([badge, title]), (wh, cells)
            assert meta["cls"] == "series-detail" and meta["top"] >= title["top"], (wh, cells)
            assert meta["left"] >= title["left"], (wh, cells)
        # Gap rows: the badge, then the text on its line, then the Add link after them.
        gaps = [cells for cells in rows if cells[1]["cls"].startswith("series-detail")
                and cells not in books]  # fmt: skip
        assert gaps, wh  # seeded #1 and #4 leave gaps #2 and #3
        for cells in gaps:
            badge, detail, action = cells
            assert badge["cls"] == "badge" and action["cls"] == "series-action", cells
            assert badge["right"] <= detail["left"] and same_line([badge, detail]), (wh, cells)
            # After the text: to its right (wider screens) or below it (phone).
            after = action["left"] >= detail["right"] or action["top"] >= detail["bottom"] - 1
            assert after, (wh, cells)
        await ui.go(f"/catalog/books/{seeded.book_id}/summary")
        text = await ui.page.evaluate(
            """t => { const p = [...document.querySelectorAll('ol > li > p')]
                 .find(e => e.textContent.startsWith(t));
               return {lines: Math.round(p.getBoundingClientRect().height /
                         parseFloat(getComputedStyle(p).lineHeight)),
                       cut: p.scrollWidth > p.clientWidth}; }""",
            long_text[:20],
        )
        assert text["lines"] > 1 and not text["cut"], (wh, text)


# The search box, dropdowns and Apply, each with the box of the grid cell that holds it.
# Upcoming only is left out: a checkbox, label and hint have no edge to share with a
# dropdown (its own layout is books-02q). Clear sits beside Apply in the same cell.
FILTER_CONTROLS = """() => [...document.querySelectorAll(
    '#q, #sort, #status, #author_id, #series_id, .filters button[type=submit]')].map(e => {
  const r = e.getBoundingClientRect(), f = e.parentElement.getBoundingClientRect();
  return {id: e.id || e.type, top: r.top, bottom: r.bottom,
          visible: r.width > 0 && r.height > 0,
          field: {top: f.top, bottom: f.bottom, visible: f.width > 0 && f.height > 0}};
})"""


@pytest.mark.ac("003/AC-01")
@pytest.mark.ac("003/AC-03")
@pytest.mark.ac("014/AC-18")
async def test_my_books_filter_controls_line_up(ui: UI, seeded: Seeded) -> None:
    """books-349: the search box and dropdowns on one line share a top edge, and Apply
    lines up with their bottom, at every width; the favorites link stays in the filters."""
    await ui.sign_in(seeded.alice)
    for wh in WIDTHS:
        await size(ui.page, wh)
        await ui.go("/")
        toggle = ui.page.locator(".filters-toggle")
        link = '.filters a[href="/authors/favorites"]'
        if await toggle.is_visible():  # phone: folded with the filters until opened
            assert not (await box(ui.page, link))["visible"], wh
            await toggle.click()
        controls = await ui.page.evaluate(FILTER_CONTROLS)
        assert len(controls) == 6 and all(c["visible"] for c in controls), (wh, controls)
        for c in controls:
            for d in controls:
                if same_line([c["field"], d["field"]]):  # one row of the filter grid
                    edge = "bottom" if "submit" in (c["id"], d["id"]) else "top"
                    assert abs(c[edge] - d[edge]) <= 1, (wh, edge, c, d)
        shown = await box(ui.page, link)
        assert shown["visible"] and shown["height"] >= 44, (wh, shown)
