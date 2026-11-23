# Tasks: Consistent Book Rows and Quick Want to read (spec 015)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("015/AC-xx")`.

## Phase 1: Setup

- [X] T001 Baseline: main is green (merged at 5690c15 with 950 passed).

## Phase 2: User Story 1 – Quick add (P1) 🎯 MVP

- [X] T002 [US1] Write failing tests in `tests/integration/test_quick_add.py` for:
  - AC-01: the buttons and links on the four pages, rows only;
  - AC-02: the entry is created; the redirect keeps the query and anchor; the notice
    shows;
  - AC-03: a book already on my list;
  - AC-04: story rows on a series page;
  - AC-05: an unknown book is Not Found; every unsafe `back` goes to `/catalog`; CSRF is
    required;
  - another member's entry doesn't block my quick add.
- [X] T003 [US1] Implement:
  - in `src/book_tracker/web/routes/readings.py`, the route and `safe_back`;
  - `partials/quick_notice.html`, with the notices on the four routes;
  - the `quick_add` macro, used on the four pages.

## Phase 3: User Story 2 – One row layout (P2)

- [X] T004 [US2] Write failing tests in `tests/integration/test_book_rows.py` for:
  - AC-07: the order, and the series on author rows;
  - AC-08: the badge linking to my entry, or "Not on my list";
  - AC-09: series badges;
  - AC-10: where the title links;
  - AC-11: only my entries.
- [X] T005 [US2] Implement the `book_row` macro and use it in `catalog_list.html`,
  `author.html` and `upcoming.html`. Add the series status badges in `series.html`. Update
  the existing tests that assert on the "On my list" text.

## Phase 4: User Story 3 – Usable everywhere (P2)

- [X] T006 [US3] Write `tests/a11y/test_rows_a11y.py` for:
  - AC-12: the four pages at every width with axe, including the quick-add notice and
    Upcoming target sizes;
  - AC-13: accessible names;
  - AC-06: a JavaScript-off quick add.

  Fix whatever fails.
- [X] T007 [US3] Add a perf test for AC-14: Catalog pages with quick-add rows, and the
  quick-add redirect, at 5,000 books.

## Phase 5: Polish

- [X] T008 Update `specs/001-family-reading-list/contracts/ui-routes.md`.
- [X] T009 Run every gate, then the quickstart.

## Notes from implementation

- **Tests first:** the T002 and T004 tests were written first and seen failing (20 of 21,
  and all of T004). The a11y tests, written after the rows existed, failed on real
  layout problems and drove the CSS fixes below.
- **Story rows show the containing book's name on their buttons**
  (`quick_add(..., named=true)`). A story may be in several books, so a hidden name alone
  wasn't enough for sighted users.
- **CSS:**
  - the series page's number-badge rule now matches only the row's direct child
    (`.series-rows > li > .badge`), so the status badge isn't put in the number column;
  - the status badge is `box-sizing: border-box; vertical-align: top`, so it doesn't make
    a series row's details taller than its title (spec 003 layout test);
  - row actions wrap on phones.
- **`here` (the return address)** is added to every render by `render()`. The quick-add
  route allow-lists it (`web/quick.py`).
- **Old tests updated for the new rows:**
  - "On my list" became the status badge, and "Add … to my list" became "Add … with
    details…";
  - row finders use `id="book-<id>"`;
  - title finders accept a link to my entry;
  - the series text helpers read visible text only.
- **Perf:** Catalog p95 60 ms; quick add p95 22 ms (5,000 books).
- **Gates:** 975 passed; a11y and perf 81; ruff and mypy clean; 8 critical modules at 100%;
  pip-audit clean.
