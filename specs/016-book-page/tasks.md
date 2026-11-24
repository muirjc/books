# Tasks: Read-only Book Page (spec 016)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[contracts/ui-book-page.md](contracts/ui-book-page.md)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("016/AC-xx")`.

## Phase 1: Setup

- [X] T001 Baseline: main is green at ffbb281. Run `uv run pytest -q` on branch
  `016-book-page` before any change.

## Phase 2: User Story 1 – Look at any book (P1) 🎯 MVP

**Goal**: a read-only `/books/<id>` page.
**Independent Test**: open the page for a book on my list and one that isn't. Check the
details, summary, status and actions.

- [X] T002 [US1] Write failing tests in `tests/integration/test_book_page.py` for:
  - AC-01: the order (title heading, author links with pen names, series link, release
    information, source reference), and no inputs that change the book;
  - AC-02: the summary with "Written by", or "No summary yet."; the **Write a summary**
    link and the **Draft with AI** form;
  - AC-03: my badge with the finished date and **Open my entry**, or "Not on my list" with
    **Want to read** (`back=/books/<id>`) and **Add with details…**;
  - AC-04: posting the quick add from the page returns to `/books/<id>?wanted=…#book-<id>`,
    and the notice shows (and `already`);
  - AC-05: **Edit book**, author and series links;
  - AC-06: an unknown id is 404, an invalid id is 404 or 422, and signed out goes to
    sign-in.
- [X] T003 [US1] Allow `/books/<uuid>` as a quick-add return address in
  `src/book_tracker/web/quick.py` (`_BACK`). Add a unit case to the existing allow-list
  tests in `tests/integration/test_quick_add.py`: the book page is accepted, and
  `/books/add` and `/books/<uuid>/x` are refused.
- [X] T004 [US1] Add the route `GET /books/{book_id}` in
  `src/book_tracker/web/routes/readings.py`, after `/books/add`. It calls `get_book`,
  `book_stories`, `source_ref`, `entry_for_book` and `quick.notice` (research R1, R5).
  Add the template `src/book_tracker/web/templates/pages/book.html` per the UI contract,
  reusing `status_badge`, `quick_add`, `author_links`, `series_line`, `release_label` and
  `partials/source_ref.html`. Register the template in `ACTIVE_TABS` in
  `src/book_tracker/web/rendering.py` (the Catalog tab).

## Phase 3: User Story 2 – Titles open the book page (P1)

**Goal**: every listed title other than on My books opens the book page.
**Independent Test**: follow titles on each page; My books still opens my entry.

- [X] T005 [US2] Write failing tests in `tests/integration/test_book_page.py` for:
  - AC-07: titles on the Catalog, author page, Upcoming (both sections), series book rows,
    story rows' containing books, Edit author and Edit series link to `/books/<id>`, for
    books on and off my list; the badge still links to `/entries/<id>`;
  - AC-08: My books and Now out titles still link to `/entries/<id>`;
  - AC-09: "View the book page" on my entry page and Edit book;
  - the spec's edge case: Edit book's back link still goes to my entry, or to the Catalog;
  - AC-10: the quick-add redirect from the book page (covered with T003).
- [X] T006 [US2] Change the title links:
  - `book_row` in `src/book_tracker/web/templates/macros.html`;
  - `src/book_tracker/web/templates/pages/series.html` (book rows, and story rows'
    containing books);
  - `pages/edit_author.html` and `pages/edit_series.html`.

  Add "View the book page" to `pages/entry.html` and `pages/edit_book.html`. Update the
  existing tests that assert the old targets (for example `tests/integration/test_book_rows.py`
  AC-10, and the a11y title helpers).

## Phase 4: User Story 3 – Collections and their stories (P2)

**Goal**: a collection's page lists its stories, with "Also in".
**Independent Test**: a collection with two stories, one shared with another book.

- [X] T007 [US3] Write failing tests in `tests/integration/test_book_page.py` for:
  - AC-11: each story as "#n Series — Title" with the series link, in the entry page's
    order; "Also in “X”" linking to `/books/<X>` for other containing books, and never the
    book itself; the entry page and Edit book unchanged;
  - AC-12: no stories → the message and **Add a story** (`?from=page`). Adding a story
    from there returns to `/books/<id>?msg=story_added#stories-heading`, with the notice;
    **Add another** keeps `from=page`; the add form's back link goes to the book page.
- [X] T008 [US3] Implement:
  - the `also_in` flag in `src/book_tracker/web/templates/partials/book_stories.html`;
  - `from=page` in `_origin`, `_back` and `_after_add` in
    `src/book_tracker/web/routes/stories.py` (research R3), plus the template's back link
    in `pages/add_story.html`;
  - the story notices on the book page.

## Phase 5: User Story 4 – Private, accessible and fast (P2)

- [X] T009 [US4] Write a failing test in `tests/integration/test_book_page.py` for AC-13:
  another member's entry for the book (status, notes, rating, dates) never shows, and my
  own does.
- [X] T010 [P] [US4] Write `tests/a11y/test_book_page_a11y.py` for AC-14: the book page on
  and off my list, with a summary, stories and the quick-add notice, at every spec 003
  width. Check no sideways scroll, 44 px targets and axe; a keyboard pass in which Tab
  reaches the actions in the page's reading order; and a JavaScript-off quick add. Fix whatever fails (CSS in
  `src/book_tracker/web/static/css/app.css`).
- [X] T011 [P] [US4] Add an AC-15 perf test in `tests/perf/`: the book page for a book with
  50 stories at 5,000 books, under 1 s p95. Re-run the Catalog, author and series budgets.

## Phase 6: Polish

- [X] T012 Update `specs/001-family-reading-list/contracts/ui-routes.md` with
  `/books/{id}` and the changed links.
- [X] T013 Run every gate (ruff, mypy, pytest with coverage, check_coverage, a11y, perf,
  pip-audit, the OpenAPI export check), then the quickstart.

## Dependencies

- T001, then US1 (T002 → T003, T004).
- US2 and US3 need the page from US1.
- US4 needs US1–US3.
- Polish comes last.

**Parallel**: T010 and T011 touch different files.

## Implementation strategy

The MVP is US1: the page exists and is reachable by URL. US2 makes it the destination of
every title. US3 adds the collection detail. US4 hardens privacy, layout and speed.

## Notes from implementation

- **Tests first:** the T002, T005, T007 and T009 tests were written first, and 12 of 14
  failed. The 2 that passed are guards on behaviour that already held: an unsafe return
  address is refused, and My books titles open my entry. The a11y and perf tests were
  written after the page existed and passed at once: no layout fixes were needed.
- **`from=page`:** `routes/stories.py` has an `Origin` type: my entry's id, the literal
  `page`, or None (Edit book). `page` carries no address, so it can only return to the
  book being edited.
- **"Also in"** comes from `Story.books`, which `book_stories` already loads, with this
  book filtered out in the template.
- **Old tests updated:** the title-link patterns in the Catalog, author, series, Edit
  author and Edit series tests now expect `/books/<id>`.
- **Perf:** book page with 50 stories p95 30 ms (5,000 books).
- **Gates:** 994 passed; a11y and perf 84; ruff and mypy clean; 8 critical modules at
  100%; pip-audit clean.

## PR #37 review (4 findings, all fixed with failing tests first)

1. The books named in an author page's Stories list and on Edit story ("In these books")
   now open the book page.
2. The summary page's back link goes to the book page when the book isn't on my list
   (was Edit book). The spec 014 AC-07 test is updated for it.
3. The quick-add notice now follows the My reading section, as the contract says.
4. The book page shows only the `story_added` / `story_already` messages; other `msg`
   codes show nothing.

Gates after the fixes: 997 passed; book page and rows a11y pass; ruff and mypy clean.
