---
description: "Task list for spec 006, series viewer"
---

# Tasks: Series Viewer

**Input**: Design documents from `/specs/006-series-viewer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-series-viewer.md, quickstart.md

**Tests**: REQUIRED (Constitution Principle V). Acceptance tests are tagged
`@pytest.mark.ac("006/AC-xx")`.
- Each test task comes before the code it covers, and is seen failing first.
- **guard** marks a test that pins behaviour which already holds.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Create `tests/integration/test_series_viewer.py` with:
  - `alice`/`ben` fixtures;
  - a `dresden` fixture: the series "The Dresden Files", author Jim Butcher, and catalog
    books #1, #2, #3, #4, #5, #6.5 and one unnumbered ("Side Jobs");
  - Alice's entries: #1 Finished (with date), #2 Finished, #5 Reading;
  - Ben's entries: #4 Finished.
- [ ] T002 [P] Create `tests/unit/test_series_rows.py` with small `Book`/`ReadingEntry`
  builders.
- [ ] T003 [P] Create `tests/a11y/test_series_viewer_a11y.py` (`a11y` marker, reusing the
  spec 003/004 helpers).

## Phase 2: Foundational (blocking)

- [ ] T004 Unit tests in `tests/unit/test_series_rows.py` (R2):
  - books keep catalog order, and each is matched to its entry or none;
  - the finished count, and a total that excludes gaps;
  - gaps: none for an unnumbered-only series (AC-15); 1, 2, 4, 6.5 gives #3, #5 and #6,
    with #6 before #6.5 (AC-14);
  - a run of three stays three rows, and a run of four collapses (AC-16);
  - a top of #500 gives one row "#8–#499";
  - a series starting at #3 gives gaps #1 and #2.
- [ ] T005 Implement `SeriesRow`, `SeriesView` and `series_rows` in
  `src/book_tracker/services/readings.py`. T004 passes.
- [ ] T006 Change `series_view` to return `(series, SeriesView)`, reading
  `catalog_service.series_books` and the owner-filtered `list_series` (R1).

## Phase 3: User Story 1 - See the whole series (P1) 🎯 MVP

### Tests

- [ ] T007 [US1] `test_every_catalog_book_in_order` (AC-01): Alice's page lists all seven
  books in the order #1…#5, #6.5, then Side Jobs.
- [ ] T008 [US1] `test_my_status_and_link` (AC-02): the #1 row shows "Finished" and its
  date, and the title links to her entry; #5 shows "Reading".
- [ ] T009 [US1] `test_others_reading_is_private` (AC-03, SC-003):
  - #4 (on Ben's list only) shows "Not on my list" for Alice;
  - nothing of Ben's appears (no "Ben", no date of his, no counts);
  - Ben's page shows his #4 as Finished and Alice's books as Not on my list.
- [ ] T010 [US1] `test_progress_line` (AC-04): "You've finished 2 of 7 books in this
  series."
- [ ] T011 [US1] **guard** `test_unknown_series_404` (AC-05): a random UUID gives 404, and a
  malformed id gives 404 or 422 as today (whichever today's route returns).
- [ ] T012 [US1] `test_empty_series` (AC-06): a series with no books shows the empty text
  and the "Add a book to this series" link.

### Implementation

- [ ] T013 [US1] Rewrite `templates/pages/series.html` (R5): the progress line,
  `<ol class="series-rows" role="list">`, the book rows, the empty state, and the edit
  link. Add `.series-rows` CSS to `static/css/app.css`. T007–T012 pass.

## Phase 4: User Story 2 - Add from the series page (P1)

### Tests

- [ ] T014 [US2] `test_add_link_starts_from_the_book` (AC-07):
  - the row's link is `/books/add?book=<id>&from_series=<id>`;
  - GET shows the title, authors, series and number filled in, the hidden `book_id`, and
    status Want to read selected.
- [ ] T015 [US2] `test_save_returns_to_series` (AC-08):
  - POST with `book_id`, `from_series` and `then=list` gives
    `303 /series/<id>?added=<entry>`;
  - that page shows "Added “Summer Knight” to your list." and the row shows Want to read;
  - Alice's counts are unchanged otherwise, and no new book is created.
- [ ] T016 [US2] `test_gap_add` (AC-09):
  - the gap link is `/books/add?series=<id>&number=3&from_series=<id>` (in a fixture with
    #3 missing);
  - the form has the series and number 3;
  - saving a new title with a picked author returns to the series, where #3 shows the book.
- [ ] T017 [US2] `test_return_survives_errors_and_prompts` (AC-10):
  - a missing title gives 422, a typed new author gives 409 (spec 005), and both pages
    carry the hidden `from_series`;
  - after confirming, the save returns to the series.
- [ ] T018 [US2] `test_add_another_keeps_spec_004` (AC-11): with `from_series` and
  `then=another`, the redirect is `/books/add?after=`.
- [ ] T019 [US2] `test_bad_parameters_ignored` (AC-12):
  - `book` or `series` set to junk, or an unknown UUID, gives the plain form;
  - `from_series` set to junk or an unknown UUID is not rendered;
  - POST with a bad or unknown `from_series` redirects to `/?msg=added`;
  - `?added=` with Ben's entry id shows no message on Alice's series page.
- [ ] T020 [US2] **guard** `test_already_on_my_list` (AC-13): posting `book_id` for a book
  already on Alice's list gives today's "already on your list" handling and no duplicate.

### Implementation

- [ ] T021 [US2] `web/forms.py`:
  - `AddBookForm.from_series` parsed as a UUID;
  - `book_start_form(book)` and `series_start_form(series, number)` (data-model.md);
  - unit tests for both in `tests/unit/test_series_rows.py` (or a forms test module).
- [ ] T022 [US2] `web/routes/readings.py`:
  - `add_book_form`: the `book`, `series`, `number` and `from_series` parameters, with
    `after` taking precedence;
  - `add_book`: the `from_series` redirect;
  - `series_page`: the `?added=` confirmation via `service.get_entry`.
- [ ] T023 [US2] Templates:
  - `add_book.html`: a hidden `from_series` next to `then`, in the main form and the ISBN
    conflict form;
  - `series.html`: the Add links (with visually-hidden titles) and the confirmation in a
    status region.
  - T014–T020 pass.

## Phase 5: User Story 3 - Gaps (P2)

- [ ] T024 [US3] Integration `test_gap_rows_on_page` (AC-14 to AC-16): the fixture's #6.5
  gives a "#6 · Not in the family catalog yet" row before it, with "Add #6"; and a series
  with a book at #500 shows one "#… – #499" row.
- [ ] T025 [US3] Gap rows in `series.html`. T024 passes.

## Phase 6: User Story 4 - Usable everywhere (P2)

- [ ] T026 [P] [US4] Browser `test_series_page_layout` (AC-17): at 360, 390, 820, 1,024 and
  1,440 there is no sideways scroll and every link is at least 44 × 44; axe passes at
  phone, tablet and laptop widths.
- [ ] T027 [P] [US4] Browser `test_row_reading_order` (AC-18): each row's text reads number,
  title, authors, status, and the status is text.
- [ ] T028 [P] [US4] Browser `test_flow_without_js` (AC-19): with JavaScript off, open the
  series, choose Add to my list, save, and land back on the series with the confirmation.
- [ ] T029 [US4] CSS fixes as the tests need. T026–T028 pass.
- [ ] T030 [P] Perf `test_series_page_budget` (SC-002) in
  `tests/perf/test_list_performance.py`: a 100-book series in the 5,000-book dataset, p95
  under 1 s.

## Phase 7: Polish

- [ ] T031 Amend the `/series/{id}` and `/books/add` rows in
  `specs/001-family-reading-list/contracts/ui-routes.md` to point to
  `contracts/ui-series-viewer.md`.
- [ ] T032 Run every gate in CLAUDE.md:
  - ruff, ruff format, `mypy --strict`;
  - the full pytest suite with coverage and `scripts/check_coverage.py`;
  - `-m a11y`, `-m perf` and `pip-audit`;
  - the OpenAPI contract check (no change).
- [ ] T033 Walk through quickstart.md with screenshots at 390 and 1,440 px, then set the
  spec status to Implemented.

## Dependencies

- **Order:** Setup, then Foundational (T004–T006), then US1 (T007–T013), then US2
  (T014–T023), then US3 (T024–T025), then US4 (T026–T030), then Polish.
- **US3:** reuses the rows from Phase 2 and only adds markup.
- **US4:** needs US1–US3.

## Implementation Strategy

- **MVP:** US1, the whole series with my status.
- **Then:** US2 (add and return), US3 (gaps), US4, then the gates.
- **Delivery:** one PR.
