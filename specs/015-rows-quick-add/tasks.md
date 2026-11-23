# Tasks: Consistent Book Rows and Quick Want to read (spec 015)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("015/AC-xx")`.

## Phase 1: Setup

- [ ] T001 Baseline: main is green (merged at 5690c15 with 950 passed).

## Phase 2: User Story 1 – Quick add (P1) 🎯 MVP

- [ ] T002 [US1] Write failing tests in `tests/integration/test_quick_add.py` for:
  - AC-01: the buttons and links on the four pages, rows only;
  - AC-02: the entry is created; the redirect keeps the query and anchor; the notice
    shows;
  - AC-03: a book already on my list;
  - AC-04: story rows on a series page;
  - AC-05: an unknown book is Not Found; every unsafe `back` goes to `/catalog`; CSRF is
    required;
  - another member's entry doesn't block my quick add.
- [ ] T003 [US1] Implement:
  - in `src/book_tracker/web/routes/readings.py`, the route and `safe_back`;
  - `partials/quick_notice.html`, with the notices on the four routes;
  - the `quick_add` macro, used on the four pages.

## Phase 3: User Story 2 – One row layout (P2)

- [ ] T004 [US2] Write failing tests in `tests/integration/test_book_rows.py` for:
  - AC-07: the order, and the series on author rows;
  - AC-08: the badge linking to my entry, or "Not on my list";
  - AC-09: series badges;
  - AC-10: where the title links;
  - AC-11: only my entries.
- [ ] T005 [US2] Implement the `book_row` macro and use it in `catalog_list.html`,
  `author.html` and `upcoming.html`. Add the series status badges in `series.html`. Update
  the existing tests that assert on the "On my list" text.

## Phase 4: User Story 3 – Usable everywhere (P2)

- [ ] T006 [US3] Write `tests/a11y/test_rows_a11y.py` for:
  - AC-12: the four pages at every width with axe, including the quick-add notice and
    Upcoming target sizes;
  - AC-13: accessible names;
  - AC-06: a JavaScript-off quick add.

  Fix whatever fails.
- [ ] T007 [US3] Add a perf test for AC-14: Catalog pages with quick-add rows, and the
  quick-add redirect, at 5,000 books.

## Phase 5: Polish

- [ ] T008 Update `specs/001-family-reading-list/contracts/ui-routes.md`.
- [ ] T009 Run every gate, then the quickstart.
