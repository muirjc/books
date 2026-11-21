---
description: "Task list for spec 003, responsive layout"
---

# Tasks: Responsive Layout for Phone, Tablet and Laptop

**Input**: Design documents from `/specs/003-responsive-layout/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-layout.md, quickstart.md

**Tests**: REQUIRED (Constitution Principle V). Every test is tagged `@pytest.mark.ac("003/AC-xx")`.
- Browser layout tests use the `a11y` marker (Playwright, live server).
- Server-HTML tests are integration tests.
- Each test task comes before the change it covers and must be seen failing first. The
  exceptions are tests marked **guard**, which pin behaviour that already holds.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- File paths are relative to the repository root

---

## Phase 1: Setup

- [X] T001 Create `tests/a11y/test_layout_003.py` with:
  - the `a11y` marker;
  - width constants `PHONE=(390, 844)`, `SMALL=(360, 740)`, `IPAD=(820, 1180)`,
    `IPAD_MINI=(768, 1024)`, `LAPTOP_MIN=(1024, 768)` and `LAPTOP=(1440, 900)`;
  - JS helpers: `ROW_CELLS` (bounding boxes and visibility of each `.book-list > li` child),
    `same_row(boxes)` and `visible_rows(page)`, which counts list rows wholly inside the
    viewport;
  - a fixture `many_books` that seeds alice with 30 books, some with series, finished
    dates and times read greater than 1, reusing `seeded` from `tests/a11y/conftest.py`.
- [X] T002 [P] Create `tests/integration/test_layout_markup.py` with the `member` / `alice`
  fixtures (as in `tests/integration/test_catalog_pages.py`) and an `entries` helper that
  adds books with finished dates and times read.

---

## Phase 2: Foundational (blocking)

**Purpose**: one set of breakpoints for every story (FR-001, FR-014).

- [X] T003 **guard** In `tests/a11y/test_layout_003.py`, write `test_no_sideways_scroll_at_every_width`.
  - It covers every signed-in page in `test_responsive.py`'s list, plus the import pages and
    admin users.
  - It runs at all six widths and uses `tests.a11y.test_responsive.check` (no sideways
    scroll, target sizes).
  - Tags: (AC-19, AC-20).
- [X] T004 Refactor `src/book_tracker/web/static/css/app.css` to the two em breakpoints:
  - Replace the `40rem`, `40.0625rem` and `max-width: 40rem` queries with mobile-first
    `@media (min-width: 40em)` and `@media (min-width: 64em)` sections, keeping today's
    behaviour.
  - The import authors column is hidden by base styles and shown from 40em.
  - Run T003 and the existing `tests/a11y` suite: all pass (FR-001, FR-014).

**Checkpoint**: same look as today, one breakpoint system.

---

## Phase 3: User Story 1 - My books fits the screen (P1) 🎯 MVP

**Goal**: laptop rows show 5 cells and filters on one row; phone rows take two lines with
folded filters.

**Independent test**: T005–T009 pass at 390, 820 and 1,440 px.

### Tests (write first, see them fail)

- [X] T005 [P] [US1] In `tests/integration/test_layout_markup.py`, write
  `test_list_rows_have_five_cells`.
  - Each `li` holds `.book-title`, `.book-meta`, `.book-status`, `.book-finished` and
    `.book-times`, in that order.
  - `.book-finished` reads "Finished 12 Mar 2026"; `.book-times` reads "Read 3 times", and is
    empty when the count is 1.
  - Tags: (AC-01, AC-03, AC-04).
- [X] T006 [P] [US1] In `tests/integration/test_layout_markup.py`, write
  `test_filter_fold_state`.
  - `/` renders `data-fold="closed"`; `/?status=reading`, `/?q=x` and `/?sort=author` render
    `data-fold="open"`.
  - Search `#q` is outside `#filter-extra`; sort, status, author, series and Apply are inside
    it.
  - A hidden `button.filters-toggle` has `aria-controls="filter-extra"` and `aria-expanded`
    matching the fold state.
  - Tags: (AC-05, AC-06).
- [X] T007 [US1] In `tests/a11y/test_layout_003.py`, write `test_my_books_laptop`.
  - At LAPTOP, each row's five cells share one line (finished and times visible).
  - The list is more than 1,200 px wide.
  - The filter fields and Apply share one line.
  - `visible_rows` ≥ 12 with `many_books`.
  - Tags: (AC-01, AC-02, SC-001).
- [X] T008 [US1] In `tests/a11y/test_layout_003.py`, write `test_my_books_tablet`.
  - At IPAD and IPAD_MINI, title, meta and status share one line.
  - `.book-times` is hidden.
  - Tag: (AC-03).
- [X] T009 [US1] In `tests/a11y/test_layout_003.py`, write `test_my_books_phone`.
  - At PHONE, each row spans at most two lines (title on the first; meta and status share
    the second).
  - Finished and times are hidden.
  - Sort and filter controls are hidden, with the "Sort and filter" toggle visible;
    clicking it shows them and sets `aria-expanded="true"`.
  - `/?status=reading` loads with them shown.
  - `visible_rows` ≥ 6.
  - Tags: (AC-04, AC-05, AC-06, SC-002).

### Implementation

- [X] T010 [US1] `src/book_tracker/web/templates/partials/reading_list.html`: render the five
  cells per row (contract ui-layout.md, My books) (FR-005, FR-006).
- [X] T011 [US1] Change the list route and filter form:
  - `src/book_tracker/web/routes/readings.py`: pass `filters_open` (a non-default sort, or
    any of q, status, author_id, series_id).
  - `src/book_tracker/web/templates/pages/list.html`: add `data-fold`, the `#filter-extra`
    wrapper and the hidden `button.filters-toggle` (FR-007).
- [X] T012 [US1] `src/book_tracker/web/static/js/app.js`:
  - add `js` to `<html>`;
  - unhide `.filters-toggle`;
  - on click, flip `data-fold` and `aria-expanded`.

  (FR-007, R5)
- [X] T013 [US1] Add the My books styles to `src/book_tracker/web/static/css/app.css`:
  - row grid areas per size, with hidden cells (R4);
  - phone fold rules under `.js`;
  - toggle hidden from 40em;
  - laptop filter row: `grid-template-columns: 2fr repeat(4, 1fr) auto`.

  (FR-005, FR-006, FR-007, FR-008)

**Checkpoint**: T005–T009 pass; existing list tests and `test_my_books_one_line_per_book` pass.

---

## Phase 4: User Story 2 - Pages use the laptop's width, and navigation fits (P1)

**Goal**: a wider container on laptop, header on one row, nav on one row on tablet,
readable line length.

### Tests

- [X] T014 [P] [US2] In `tests/a11y/test_layout_003.py`, write `test_page_width`.
  - At LAPTOP, `main.container` content is at least 1,200 px wide and centred.
  - At 2,560 × 1,440, it is 1,320 px wide or less and centred.
  - Tag: (AC-07, SC-003).
- [X] T015 [P] [US2] In `tests/a11y/test_layout_003.py`, write `test_header_rows`.
  - At LAPTOP_MIN and LAPTOP, for alice and for the admin, the brand, every nav link and the
    account action buttons share one line.
  - At IPAD_MINI and IPAD, all nav links share one line.
  - Tags: (AC-08, AC-09).
- [X] T016 [P] [US2] In `tests/a11y/test_layout_003.py`, write `test_readable_line_length`.
  - At LAPTOP, paragraphs in `main` on sign in, a book's summary page and the entry page are
    at most 75 characters wide, measured with `ch` against computed font size.
  - Single text inputs on change password are at most 40rem wide.
  - Tag: (AC-10).

### Implementation

- [X] T017 [US2] Add to `src/book_tracker/web/static/css/app.css`:
  - laptop `.container` max-width of 82.5rem with 1.5rem padding;
  - `main p, .hint, .notice` max-width of 75ch;
  - stacked text inputs max-width of 40rem.

  (FR-002, FR-013)
- [X] T018 [US2] Change the header:
  - `src/book_tracker/web/templates/base.html`: wrap the "Signed in as" words in a span that
    is visually hidden at laptop width.
  - `app.css`, tablet header: brand and account actions on row 1, nav full width with
    `flex-wrap: nowrap` on row 2.
  - `app.css`, laptop header: one row, nav after brand, account actions pushed right.

  (FR-003, FR-004)

**Checkpoint**: T014–T016 pass; phone header unchanged (T003 still passes).

---

## Phase 5: User Story 3 - Book forms use two columns on a laptop (P2)

### Tests

- [X] T019 [P] [US3] In `tests/integration/test_layout_markup.py`, write
  `test_form_groups_and_pairs`.
  - On `/books/add` and `/entries/{id}`, `.form-columns` holds exactly two groups in order:
    book fields, then reading fields.
  - The submit button follows `.form-columns`.
  - `.field-row` wraps `series_name` with `series_number`, and `status` with `finished_on`.
  - The DOM order of all inputs is unchanged from today: the titles, authors, series,
    number and ISBN, then the reading fields.
  - Tags: (AC-11, AC-12, AC-13, AC-15).
- [X] T020 [US3] In `tests/a11y/test_layout_003.py`, write `test_book_forms_by_size`.
  - At LAPTOP, on a book's page and Add a book, the two groups sit side by side (the same
    top, the reading group to the right) and the submit is below both.
  - The book page form's height is at most 60% of its height at PHONE.
  - At IPAD, series and number share a line, and status and date share a line.
  - At PHONE, every `.field` is on its own line.
  - Tags: (AC-11, AC-12, AC-13, AC-14, SC-004).
- [X] T021 [US3] **guard** In `tests/a11y/test_layout_003.py`, write
  `test_book_form_focus_order_and_rotation`.
  - At LAPTOP, pressing Tab from the title visits the book fields, then status, finished,
    times read and notes, then Save.
  - At IPAD, type into the title and notes, resize to 1,180 × 820, and both values are
    kept.
  - Tags: (AC-15, AC-16).

### Implementation

- [X] T022 [US3] Change the form templates:
  - `src/book_tracker/web/templates/partials/book_fields.html`: wrap the series and number
    fields in `<div class="field-row">`.
  - `src/book_tracker/web/templates/partials/entry_fields.html`: wrap the status and date
    finished fields in `<div class="field-row">`.

  (FR-010)
- [X] T023 [US3] Wrap the two form groups in `<div class="form-columns">`:
  - `src/book_tracker/web/templates/pages/entry.html`: Book details and My reading.
  - `src/book_tracker/web/templates/pages/add_book.html`: `<div>` book fields + summary,
    then `<div>` reading fields.

  The submit stays after the wrapper (FR-009, FR-012).
- [X] T024 [US3] Add the form layout to `src/book_tracker/web/static/css/app.css`:
  - tablet: `.field-row` as a 2-column grid;
  - laptop: `.form-columns` as a 3fr / 2fr grid with a 2rem gap;
  - phone: single column.

  (FR-009, FR-010, FR-011)

**Checkpoint**: T019–T021 pass; existing reading and catalog page tests pass.

---

## Phase 6: User Story 4 - Import uses the space (P3)

### Tests

- [X] T025 [US4] In `tests/a11y/test_layout_003.py`, write `test_import_laptop`.
  - At LAPTOP, the import controls (fields and buttons) share one line.
  - The works table is as wide as `main` content, within 2 px.
  - Tag: (AC-17).
- [X] T026 [US4] **guard** In `tests/a11y/test_layout_003.py`, write
  `test_import_columns_same_per_author`.
  - At IPAD and LAPTOP, header widths match for two very different authors (as in
    `test_works_columns_are_the_same_for_every_author`).
  - Tag: (AC-18).

### Implementation

- [X] T027 [US4] Change the import styles in `src/book_tracker/web/static/css/app.css`:
  - laptop: `.import-controls` set to `flex-wrap: nowrap`, fields `flex: 1 1 0`, buttons
    `flex: none`;
  - keep the fixed table columns from 40em.

  (FR-015)

---

## Phase 7: Accessibility and polish (cross-cutting)

- [X] T028 [P] In `tests/a11y/test_layout_003.py`, write `test_axe_by_size`.
  - Run `assert_no_axe_violations` on sign in, My books, Add a book, a book's page and an
    author's works, at PHONE, IPAD and LAPTOP.
  - Tag: (AC-21).
- [X] T029 [P] In `tests/a11y/test_layout_003.py`, write `test_200_percent_text`.
  - Use a new browser context with a 640 × 450 viewport and `device_scale_factor=2`.
  - The main pages show the tablet layout: list rows on one line with times hidden, and the
    nav on one line.
  - `check()` passes, and no element in `main` overflows its parent box.
  - Tags: (AC-22, FR-014).
- [X] T030 Run the full gates:
  - `ruff check`, `ruff format --check`, `mypy --strict src`;
  - `pytest --cov` with `check_coverage.py`;
  - `pytest -m a11y` and `pytest -m perf` (SC-006, FR-016, FR-017).
- [X] T031 Take screenshots at PHONE, IPAD and LAPTOP of My books, a book's page and the
  import works page into the scratchpad, and review them. Fix anything that looks broken.
- [X] T032 Final steps:
  - Update `specs/001-family-reading-list/contracts/ui-routes.md`, adding a line that points
    to `specs/003-responsive-layout/contracts/ui-layout.md` for layout.
  - Mark the tasks done.
  - Open a PR that references `specs/003-responsive-layout/`.

---

## Traceability

| Requirement | Tasks |
|---|---|
| AC-01 | T005, T007, T010, T013 |
| AC-02 | T007, T013 |
| AC-03 | T005, T008, T010, T013 |
| AC-04 | T005, T009, T010, T013 |
| AC-05 | T006, T009, T011, T012, T013 |
| AC-06 | T006, T009, T011 |
| AC-07 | T014, T017 |
| AC-08 | T015, T018 |
| AC-09 | T015, T018 |
| AC-10 | T016, T017 |
| AC-11 | T019, T020, T023, T024 |
| AC-12 | T019, T020, T023, T024 |
| AC-13 | T019, T020, T022, T024 |
| AC-14 | T020, T024 |
| AC-15 | T019, T021, T023 |
| AC-16 | T021 |
| AC-17 | T025, T027 |
| AC-18 | T026, T027 |
| AC-19 | T003, T030 |
| AC-20 | T003 |
| AC-21 | T028 |
| AC-22 | T029 |
| FR-001 | T004 |
| FR-002 | T017 |
| FR-003 | T018 |
| FR-004 | T003, T018 |
| FR-005 | T010, T013 |
| FR-006 | T010, T013 |
| FR-007 | T011, T012, T013 |
| FR-008 | T013 |
| FR-009 | T023, T024 |
| FR-010 | T022, T024 |
| FR-011 | T024 |
| FR-012 | T021, T023 |
| FR-013 | T016, T017 |
| FR-014 | T004, T029 |
| FR-015 | T025, T027 |
| FR-016 | T003, T030 |
| FR-017 | T030 (full suite unchanged) |
| FR-018 | T021 |
| SC-001 | T007 |
| SC-002 | T009 |
| SC-003 | T014 |
| SC-004 | T020 |
| SC-005 | T003, T028, T029 |
| SC-006 | T030 |

## Dependencies & Execution Order

- **Setup** (T001, T002): first. **Foundational** (T003, T004) blocks all stories.
- **US1** (T005–T013) and **US2** (T014–T018) both edit `app.css`, so run them one after the
  other. US1 is first, as the MVP.
- **US3** (T019–T024) can start after Foundational. It shares `app.css`, so its CSS task
  goes after US2's.
- **US4** (T025–T027) is after Foundational.
- **Polish** (T028–T032) comes last.
- Within each story: tests, then templates and route, then JS, then CSS.

## Parallel Example: User Story 1

```text
T005 test_list_rows_have_five_cells   (tests/integration/test_layout_markup.py)
T006 test_filter_fold_state           (same file: write after T005, or together in one edit)
T007–T009 browser tests               (tests/a11y/test_layout_003.py)
```

## Implementation Strategy

1. Phases 1–2: breakpoints refactor with no visible change.
2. US1 (MVP): My books on all three sizes. Deployable on its own.
3. US2: wider pages and the header.
4. US3: two-column forms.
5. US4: import controls.
6. Polish: zoom, axe, screenshots, PR.

## Notes

- **guard** tests (T003, T021, T026) pin existing behaviour and may pass on first run.
  Principle V's fail-first rule applies to the tests that cover new behaviour.
- **No server data changes**: the only server change is the `filters_open` context flag.

## PR #18 review fixes

- [X] T033 Keep `hidden` elements hidden: `[hidden] { display: none !important }`, so the
  fold toggle never shows without JavaScript (test `test_phone_filters_without_javascript`).
- [X] T034 Scope the one-line row layout to My books (`.reading-list`); the series page gets
  `.series-list` with its number badge first, and summary history wraps in full (test
  `test_series_and_summary_lists_keep_their_layout`).
- [X] T035 Move the fold from `app.js` to a blocking `static/js/fold.js` in `<head>`, so
  `html.js` is set before first paint and the fold works if `app.js` fails (test
  `test_js_flag_set_before_first_paint`).
- [X] T036 Phone-only rules use `not all and (min-width: 40em)`; the two-column filter grid
  (search + toggle) applies only under `html.js`.
- [X] T037 `test_my_books_one_line_per_book`: check every displayed cell against the title's
  line, instead of skipping zero-height cells.
