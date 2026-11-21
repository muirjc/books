---
description: "Task list for spec 007, upcoming books"
---

# Tasks: Upcoming Books

**Input**: Design documents from `/specs/007-upcoming-books/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED (Constitution Principle V). Acceptance tests are tagged
`@pytest.mark.ac("007/AC-xx")`. Each test task comes before the code it covers, and is seen
failing first.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Create `tests/integration/test_upcoming_books.py` with:
  - `alice`/`ben` fixtures, and a fixed clock with today = 2026-11-21 (the app's
    `state.clock`);
  - helpers to create books with release dates and entries.
- [ ] T002 [P] Create `tests/unit/test_upcoming.py`.
- [ ] T003 [P] Create `tests/a11y/test_upcoming_a11y.py` and
  `tests/contract/test_upcoming_contract.py`.

## Phase 2: Foundational (blocking)

- [ ] T004 Test: `tests/integration/test_migrations.py` checks that 0003 adds
  `book.release_date`, `reading_entry.pre_ordered` (not null, default false) and
  `book_release_date_idx`, and that downgrade to `0002_author_import` removes them.
- [ ] T005 Write `migrations/versions/0003_upcoming_books.py`. Update the ORM columns in
  `persistence/models.py`, the domain fields in `domain/models.py` and the mappers
  `persistence/mappers.py` and `schemas/mappers.py`. T004 passes.
- [ ] T006 Unit tests for `is_upcoming` and `is_now_out` in `tests/unit/test_upcoming.py`:
  - tomorrow is upcoming and today isn't;
  - today and today−29 are now out; today−30 and tomorrow aren't;
  - None is neither.
- [ ] T007 Implement `NOW_OUT_DAYS`, `is_upcoming` and `is_now_out` in `domain/values.py`.
  Add `today` to the context in `web/rendering.py`. T006 passes.

## Phase 3: User Story 1 - Release date and "Coming" (P1) 🎯 MVP

### Tests

- [ ] T008 [US1] `test_add_book_with_release_date` (AC-01): the field is blank by default,
  and saving stores the date on the catalog book.
- [ ] T009 [US1] `test_edit_release_date` (AC-02): set, change and clear the date through
  Edit book and through the entry page's book section; Ben sees the change.
- [ ] T010 [US1] `test_bad_release_date` (AC-03): "2027-02-30" gives 422 with an error on
  `release_date`, and nothing is saved, on both Add a book and Edit book.
- [ ] T011 [US1] `test_coming_label_everywhere` (AC-04): "Coming 3 Mar 2027" shows on My
  books, the series page and the entry page.
- [ ] T012 [US1] `test_released_and_undated` (AC-05):
  - a date of today or earlier shows no "Coming";
  - the entry page shows "Released <date>";
  - with no date, neither shows.
- [ ] T013 [US1] `test_chosen_book_shows_coming` (AC-06): `/books/add?book=<id>` shows
  "Coming <date>".

### Implementation

- [ ] T014 [US1] Catalog:
  - `ReleaseDateIn` in `schemas/types.py`;
  - `release_date` on `BookCreate`, `BookUpdate` and the `Book` schema;
  - `NewBook.release_date`;
  - `services/catalog.create_book` and `update_book`, and `persistence/catalog`.
- [ ] T015 [US1] Forms and routes:
  - `AddBookForm.release_date`, parsed in `parse_add_book`;
  - `book_form` and `book_start_form` include it, and `carry_over_form` clears it;
  - `add_book`, `save_book_details` and `_unchanged` pass it;
  - the Edit book route.
- [ ] T016 [US1] Templates:
  - the Release date field in `partials/book_fields.html`;
  - the `release_label` macro;
  - labels in `reading_list.html`, `series.html` and `entry.html` (Coming / Released), and
    in the chosen-book display in `add_book.html`;
  - CSS. T008–T013 pass.

## Phase 4: User Story 2 - Pre-ordered (P2)

### Tests

- [ ] T017 [US2] `test_pre_ordered_saves` (AC-07): tick it on Add a book; untick and tick
  it on the entry page; off by default.
- [ ] T018 [US2] `test_pre_ordered_shown_when_relevant` (AC-08):
  - it is shown with an upcoming book on My books, the entry page and the series page;
  - it is hidden on My books for a book released 40 days ago;
  - the entry form checkbox stays ticked.
- [ ] T019 [US2] `test_pre_ordered_is_private` (AC-09): Alice pre-orders; Ben's My books,
  series page, Upcoming page and the API show nothing of it.

### Implementation

- [ ] T020 [US2] Implement Pre-ordered:
  - `pre_ordered` on `ReadingEntryCreate`/`ReadingEntryUpdate` and the `ReadingEntry`
    schema;
  - `service.add_entry` and `update_entry`, and `repo.add`;
  - `parse_add_book` and `parse_entry_update`;
  - the checkbox in `partials/entry_fields.html`;
  - the `release_label` Pre-ordered part.
  - T017–T019 pass.

## Phase 5: User Story 3 - Upcoming filter and page (P1)

### Tests

- [ ] T021 [US3] `test_upcoming_filter` (AC-10): only future-dated books, soonest first,
  ties by title; the count is right; search, status, author and series still narrow it;
  `sort=-title` is ignored.
- [ ] T022 [US3] `test_upcoming_filter_kept` (AC-11): the paging links keep `upcoming=1`,
  the HTMX partial honours it, and Clear goes to `/`.
- [ ] T023 [US3] `test_upcoming_page` (AC-12):
  - **On my list:** soonest first, with Coming, status and Pre-ordered;
  - **Also coming:** catalog-only and Ben-only future books, but not mine and not past
    ones, with `/books/add?book=` links;
  - the navigation link has `aria-current`.
- [ ] T024 [US3] `test_upcoming_page_empty` (AC-13): both empty texts and Add a book.
- [ ] T025 [US3] Contract `test_upcoming_contract.py` (FR-008):
  - `release_date` and `pre_ordered` round-trip through create, update and read;
  - `GET /api/v1/me/readings?upcoming=true` returns only my upcoming entries, soonest
    first;
  - the responses validate against `openapi.yaml`.

### Implementation

- [ ] T026 [US3] `persistence/readings.py`: `list(upcoming_after=)` and `list_upcoming`.
  `persistence/catalog.py`: `upcoming_books`. `services/readings.py`: `list_entries`
  (`upcoming_after`) and `upcoming_view`.
- [ ] T027 [US3] `web/routes/readings.py`:
  - `my_list` takes `upcoming` (in `kept`);
  - the new `GET /upcoming`;
  - `api/readings.py` takes `upcoming`.
- [ ] T028 [US3] Templates:
  - the checkbox and hint in `list.html`;
  - the new `pages/upcoming.html`;
  - the nav link in `base.html`;
  - CSS.
- [ ] T029 [US3] Update `specs/001-family-reading-list/contracts/openapi.yaml` per
  `contracts/api-upcoming.md`, and regenerate `openapi.generated.json`. T021–T025 pass.

## Phase 6: User Story 4 - Now out (P1)

### Tests

- [ ] T030 [US4] `test_now_out_notice` (AC-14):
  - released today, and 29 days ago, give the notice, most recent first;
  - it links to the entry;
  - "(pre-ordered)" is shown when ticked;
  - it has a status role.
- [ ] T031 [US4] `test_now_out_window` (AC-15): released 30 days ago, or tomorrow, gives no
  notice.
- [ ] T032 [US4] `test_now_out_only_want_to_read` (AC-16): Reading and Finished give no
  notice.
- [ ] T033 [US4] `test_no_notice_when_none` (AC-17): no `#now-out` element; the HTMX
  partial never has it.
- [ ] T034 [US4] `test_now_out_is_private` (AC-18): Ben's newly released book doesn't
  appear for Alice.

### Implementation

- [ ] T035 [US4] Add `list_now_out` to `persistence/readings.py` and `now_out` to
  `services/readings.py`. `my_list` renders the notice on the full page in `list.html`.
  T030–T034 pass.

## Phase 7: User Story 5 - Usable everywhere (P2)

- [ ] T036 [P] [US5] Browser `test_upcoming_layouts` (AC-19):
  - the pages: the Upcoming page, My books with the notice and filter, Add a book and the
    entry page;
  - at 360, 390, 820, 1,024 and 1,440: no sideways scroll, and targets at least 44 × 44;
  - axe at phone, tablet and laptop widths.
- [ ] T037 [P] [US5] Browser `test_upcoming_without_js` (AC-20): with JavaScript off, record
  a date with Pre-ordered, use the filter, and open the Upcoming page.
- [ ] T038 [P] [US5] Browser `test_now_out_is_status_text` (AC-21): the notice has
  `role=status`, and the labels are text.
- [ ] T039 [US5] CSS fixes as the tests need.
- [ ] T040 [P] Perf (SC-002) in `tests/perf/test_list_performance.py`: My books with the
  notice, the Upcoming filter and the Upcoming page, with 200 upcoming books in the
  5,000-book dataset. Each must be under 1 s at p95.

## Phase 8: Polish

- [ ] T041 Amend the `/`, `/series/{id}`, `/entries/{id}`, `/books/add` and Edit book rows,
  and add `/upcoming`, in `specs/001-family-reading-list/contracts/ui-routes.md`, pointing
  to `contracts/ui-upcoming.md`.
- [ ] T042 Run every gate in CLAUDE.md:
  - ruff, ruff format and `mypy --strict`;
  - the full suite with coverage and `scripts/check_coverage.py`;
  - `-m a11y`, `-m perf` and `pip-audit`;
  - the OpenAPI export matching the committed baseline.
- [ ] T043 Walk through quickstart.md with screenshots at 390 and 1,440 px, then set the
  spec status to Implemented.

## Dependencies

- **Order:** Setup, then Foundational (T004–T007), then US1, then US2, then US3, then US4,
  then US5, then Polish.
- **US2–US4 need US1:** books need release dates.
- **US4 uses US2:** its "(pre-ordered)" text.
- **US5 needs all of them.**

## Implementation Strategy

- **MVP:** US1 (dates and Coming labels).
- **Then:** US3 and US4, the views the request is for; then US2, US5 and the gates.
- **Delivery:** one PR.
