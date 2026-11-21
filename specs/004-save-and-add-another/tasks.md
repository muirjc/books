---
description: "Task list for spec 004, save and add another"
---

# Tasks: Save and Add Another

**Input**: Design documents from `/specs/004-save-and-add-another/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-add-another.md, quickstart.md

**Tests**: REQUIRED (Constitution Principle V). Every acceptance test is tagged
`@pytest.mark.ac("004/AC-xx")`.
- Each test task comes before the change it covers and must be seen failing first.
- Tests marked **guard** pin behaviour that already holds for **Add to my list** and must
  keep holding.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- File paths are relative to the repository root

---

## Phase 1: Setup

- [X] T001 Create `tests/integration/test_add_another.py`:
  - `alice`, `member` fixtures (as in `tests/integration/test_series_number_conflict.py`);
  - a `dresden` fixture: Jim Butcher, The Dresden Files;
  - a `form(**overrides)` helper building the add-book POST data.
- [X] T002 [P] Create `tests/unit/test_add_another_forms.py` (no database).
- [X] T003 [P] Create `tests/a11y/test_add_another_a11y.py` with the `a11y` marker, reusing
  `UI`, `seeded`, `size`, `box`, the width constants and `check` from
  `tests/a11y/test_layout_003.py` and `tests/a11y/test_responsive.py`.

---

## Phase 2: Foundational (blocking)

**Purpose**: the `then` choice reaches the route, and the next number rule exists.

- [X] T004 [P] Unit tests in `tests/unit/test_add_another_forms.py` for
  `next_series_number`: 3 → 4, 4.5 → 5, 0 → 1, 12.25 → 13, `None` → `None`; the result
  renders as "4", not "4.0" (R4, AC-09).
- [X] T005 Implement `next_series_number(n: Decimal | None) -> Decimal | None` in
  `src/book_tracker/web/forms.py`. T004 passes.
- [X] T006 Integration test `test_then_choice_last_value_wins` in
  `tests/integration/test_add_another.py`: POST with `then` sent twice in both orders
  (`another` then `list`, and the reverse); the redirect follows the last value, and any
  other value means `list` (R2).
- [X] T007 Add `then: Literal["list", "another"]` to `AddBookForm`, parsed in
  `parse_add_book` in `src/book_tracker/web/forms.py` (anything other than `another` →
  `list`). Pass `then` to `_add_form` in `src/book_tracker/web/routes/readings.py`.

**Checkpoint**: the route knows which button was used; no visible change yet.

---

## Phase 3: User Story 1 - Add a book and go straight to the next one (P1) 🎯 MVP

**Goal**: **Add and add another** saves the book and shows a fresh Add a book form with a
confirmation and focus in Title.

**Independent Test**: fill in Add a book, choose **Add and add another**; the book is on
the list and the page is a fresh form with the confirmation.

### Tests

- [X] T008 [US1] `test_add_and_add_another_redirects_to_fresh_form` in
  `tests/integration/test_add_another.py`: the `then=another` POST adds the entry (as
  `then=list` would) and answers `303 /books/add?after=<entry_id>` (AC-01).
- [X] T009 [US1] `test_confirmation_names_the_book` in
  `tests/integration/test_add_another.py`:
  - GET `?after=` shows `#added-notice` with `role="status"`, "Added “Grave Peril” to your
    list." and a link to `/entries/<id>`;
  - Title has `autofocus`, and its `aria-describedby` contains `added-notice`;
  - the plain `GET /books/add` has neither (AC-02, AC-03).
- [X] T010 [P] [US1] **guard** `test_add_to_my_list_unchanged` in
  `tests/integration/test_add_another.py`: `then=list` and a missing `then` both answer
  `303 /?msg=added` (AC-04).
- [X] T011 [US1] `test_reload_does_not_add_again` in `tests/integration/test_add_another.py`:
  GET the `after` page twice, and the entry count is unchanged (AC-05).
- [X] T012 [US1] `test_after_other_members_entry_is_a_plain_form` in
  `tests/integration/test_add_another.py`: with Ben's entry id, a removed entry's id and
  `after=not-a-uuid`, Alice gets the plain empty form, with no confirmation and no title,
  author or series of Ben's book (FR-009, Principle I cross-user test).
- [X] T013 [P] [US1] Browser test `test_add_another_flow_with_and_without_js` in
  `tests/a11y/test_add_another_a11y.py`, run with JavaScript on and off:
  - click **Add and add another** and land on Add a book with the confirmation;
  - `document.activeElement` is Title;
  - pressing Enter in Title on the next form goes to My books (AC-03, AC-06, FR-010).

### Implementation

- [X] T014 [US1] In `add_book` (`src/book_tracker/web/routes/readings.py`), keep the entry
  `service.add_entry` returns in both branches; when `form.then == "another"`, redirect
  `303 /books/add?after={entry.id}`, otherwise `/?msg=added`.
- [X] T015 [US1] In `add_book_form`, read `after` as a UUID and load the entry with
  `service.get_entry(db, auth.account.id, after)`. Catch `NotFoundError` (and a bad UUID):
  plain form. Pass `added=entry` to `_add_form`.
- [X] T016 [US1] Templates:
  - `pages/add_book.html`:
    - the hidden `then` right after `csrf_token`;
    - the `#added-notice` confirmation when `added`;
    - the buttons in `.form-actions`: `then=list` **Add to my list** (primary) first, then
      `then=another` **Add and add another**;
    - the hidden `then` in the ISBN-conflict form too.
  - `partials/combobox.html`: optional `autofocus` and `describedby_extra`, merged with
    `described()`.
  - `partials/book_fields.html`: when `added`, pass both to the Title combobox.
- [X] T017 [US1] Add `.form-actions` (wrapping flex row, 0.75rem gap) to
  `src/book_tracker/web/static/css/app.css`. T008–T013 pass.

**Checkpoint**: US1 works end to end; the next form is empty apart from the confirmation.

---

## Phase 4: User Story 2 - The next form is filled in for the next book (P1)

**Goal**: authors, series, next number and status carry over; everything else is empty.

**Independent Test**: add "Grave Peril" #3 with **Add and add another**, then check the next
form has Jim Butcher, The Dresden Files, 4 and Finished, and nothing else.

### Tests

- [X] T018 [P] [US2] Unit tests for `carry_over_form(entry)` in
  `tests/unit/test_add_another_forms.py`, built from domain objects:
  - two authors in order, with ids;
  - series with id and next number;
  - no series, and series without a number;
  - status;
  - no `book_id`, title, `isbn_13`, `finished_on`, `summary` or `notes` keys
  - (AC-07, AC-08, AC-09, AC-10).
- [X] T019 [US2] `test_next_form_carries_author_series_number_status` in
  `tests/integration/test_add_another.py`:
  - after adding Grave Peril #3 (Finished, with ISBN, date, summary and notes), the next
    form has the author name and id, series name and id, `series_number` value "4" and
    status `finished` selected;
  - title, ISBN, date finished, summary and notes are empty (AC-07, AC-08, AC-09, AC-10).
- [X] T020 [US2] `test_carried_values_are_editable` in
  `tests/integration/test_add_another.py`: post the next form with a changed series number
  and an author cleared, and the book saves with what was entered. Saving the carried form
  as is creates no new author or series rows (AC-11, Principle II).
- [X] T021 [US2] `test_carry_over_from_picked_catalog_book` in
  `tests/integration/test_add_another.py`: add an existing catalog book through `book_id`,
  and the next form carries that book's authors, series and next number (AC-12).
- [X] T022 [US2] `test_suggested_number_taken_shows_usual_conflict` in
  `tests/integration/test_add_another.py`:
  - the suggested number is held by another book;
  - saving gives 409 with "Another book already has this number in the series" and the
    books-cay link;
  - nothing is saved (AC-13).
- [X] T023 [US2] `test_carry_over_shows_current_names` in
  `tests/integration/test_add_another.py`: rename the author and series between the two
  steps, and the next form shows the new names (edge case).

### Implementation

- [X] T024 [US2] Implement `carry_over_form(entry: ReadingEntry) -> AddBookForm` in
  `src/book_tracker/web/forms.py` (R5, data-model.md). Use it in `add_book_form` when
  `added` is set. T018–T023 pass.

**Checkpoint**: adding a run of books in a series needs only titles (SC-001).

---

## Phase 5: User Story 3 - Errors and conflicts work the same with either button (P2)

**Goal**: the same messages and choices; a conflict's own buttons keep the chosen button.

### Tests

- [X] T025 [US3] `test_errors_and_conflicts_same_for_both_buttons` in
  `tests/integration/test_add_another.py`. Each case is posted with `then=list` and
  `then=another`:
  - missing title (422);
  - new author with an existing name (409 author choice);
  - existing series name (409);
  - existing ISBN (409);
  - number taken (409);
  - already on the list (409).

  Each case gives the same status and messages either way, nothing is saved, and the page
  carries the hidden `then` matching the button used (AC-14, AC-16).
- [X] T026 [US3] `test_conflict_choice_keeps_add_another` in
  `tests/integration/test_add_another.py`:
  - from the author-conflict page reached with `then=another`, post the form as the "Use
    existing author" button sends it (hidden `then=another`, no button `then`), and the
    redirect is `/books/add?after=…`;
  - the same through the ISBN form's "Add … to my list instead";
  - with hidden `then=another` plus the **Add to my list** button, it goes to My books
    (AC-15).
- [X] T027 [P] [US3] Browser test `test_conflict_button_keeps_choice` in
  `tests/a11y/test_add_another_a11y.py`:
  - trigger an author conflict with **Add and add another**;
  - click the real "Use existing author" button;
  - land on the fresh form with the confirmation (AC-15, R2 tree-order check).

### Implementation

- [X] T028 [US3] Render the hidden `then` from `form.then` on every add-book page, including
  error and conflict pages and the ISBN form (T016 placed it). Confirm that no route change
  is needed beyond T014; T025–T027 pass.

---

## Phase 6: User Story 4 - Fits every screen and stays accessible (P2)

- [X] T029 [P] [US4] Browser test `test_buttons_fit_every_width` in
  `tests/a11y/test_add_another_a11y.py`, on the carry-over form after adding a book with a
  long title, at 360, 390, 820, 1,024 and 1,440, and at 200% text (a 640 × 450 viewport at
  device scale 2, as in spec 003 AC-22; FR-012):
  - both buttons are visible with no sideways scroll (`check`);
  - each is at least 44 × 44;
  - **Add to my list** is before **Add and add another** in Tab order (AC-17).
- [X] T030 [P] [US4] Browser test `test_axe_add_another` in
  `tests/a11y/test_add_another_a11y.py`: the plain form and the carry-over form at phone,
  tablet and laptop widths pass `assert_no_axe_violations` (AC-18).
- [X] T031 [US4] **guard** Run `tests/a11y/test_layout_003.py`: the book form tests
  (`test_book_forms_by_size`, `test_book_form_focus_order_and_rotation`) still pass with the
  new buttons and notice (AC-18). Adjust `.form-actions` CSS if any fail.

---

## Phase 7: Polish & cross-cutting

- [X] T032 Amend the `GET, POST /books/add` row in
  `specs/001-family-reading-list/contracts/ui-routes.md` to point to
  `contracts/ui-add-another.md`.
- [X] T033 Run every gate in CLAUDE.md:
  - ruff, ruff format, `mypy --strict`;
  - the full pytest suite with coverage and `scripts/check_coverage.py`;
  - `-m a11y`, `-m perf` and `pip-audit`.

  SC-004 has no new perf test: carry-over adds one read of the member's entry by its ID to
  Add a book, which the existing page budget easily covers (analysis C2).
- [X] T034 Walk through quickstart.md by hand at 390 and 1,440 px (screenshots in the
  scratchpad); set spec status to Implemented.

---

## Dependencies & Execution Order

- **Setup** (T001–T003), then **Foundational** (T004–T007), then **US1** (T008–T017).
- **US2** (T018–T024) needs US1's GET `?after=` handler (T015).
- **US3** (T025–T028) needs T007 and T016.
- **US4** (T029–T031) needs T016–T017.
- **Polish** last.
- Within each phase, tests come before implementation, and are seen failing first except
  **guard** tests.

### Parallel opportunities

- T002 and T003 alongside T001.
- T004 alongside T006.
- T010 and T013 alongside the other US1 tests.
- T018 alongside the US2 integration tests.
- T027, T029 and T030, which are browser tests in one file, can be written together.

## Implementation Strategy

- **MVP:** Phase 1 to Phase 3 (US1), the second button and a fresh form.
- **Then:** US2 for the carry-over, which delivers most of the time saved (SC-001).
- **Finally:** US3 and US4, then the gates.
- The whole feature ships as one PR.
