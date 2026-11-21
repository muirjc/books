---
description: "Task list for spec 005, confirm new author and series names"
---

# Tasks: Confirm New Author and Series Names

**Input**: Design documents from `/specs/005-confirm-new-names/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-new-names.md, quickstart.md

**Tests**: REQUIRED (Constitution Principle V). Acceptance tests are tagged
`@pytest.mark.ac("005/AC-xx")`.
- Each test task comes before the code it covers, and is seen failing first.
- **guard** marks a test that pins behaviour which already holds.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Create `tests/integration/test_confirm_new_names.py` with:
  - `alice`/`member` fixtures;
  - a `robb` fixture: J.D. Robb (real name Nora Roberts), the series "In Death", and Jim
    Butcher with the series "The Dresden Files";
  - a `counts(factory)` helper returning (authors, series, books, entries);
  - a `field_error(page, field)` helper.
- [ ] T002 [P] Create `tests/unit/test_similar_names.py`.
- [ ] T003 [P] Create `tests/a11y/test_confirm_new_names_a11y.py` (`a11y` marker, reusing
  spec 003/004 helpers).

## Phase 2: Foundational (blocking)

- [ ] T004 [P] Unit tests in `tests/unit/test_similar_names.py` (R3):
  - `loose_name_key`: punctuation, spacing, capitals, NFKC and a leading "The" removed;
  - `similar_names`: ranking, the 0.75 cutoff, ties by name, limit 3, and matching on an
    author's real name;
  - the SC-002 table: at least 10 typos, each with its intended name among the three
    offered, and "J DM Robb" giving "J.D. Robb" first;
  - genuinely new names give no suggestions.
- [ ] T005 Implement `loose_name_key` and `similar_names` in
  `src/book_tracker/domain/values.py`. T004 passes.
- [ ] T006 Integration test `test_similar_authors_and_series_from_catalog` in
  `tests/integration/test_confirm_new_names.py`: `services.catalog.similar_authors(db,
  "J DM Robb")` returns J.D. Robb first, `similar_series(db, "Dresdin Files")` returns The
  Dresden Files, and typing "Nora Roberts" offers J.D. Robb (real name).
- [ ] T007 Implement `author_names`, `series_names` (`persistence/catalog.py`) and
  `similar_authors`, `similar_series` (`services/catalog.py`). T006 passes.
- [ ] T008 Parse the new fields in `src/book_tracker/web/forms.py` (data-model.md):
  - `AuthorRow.confirmed` and `AuthorRow.use_id`;
  - `AddBookForm.series_confirmed` and `AddBookForm.use_series_id`;
  - unit tests in `tests/unit/test_similar_names.py`: a bad UUID is ignored, and
    confirmation text is normalized like names.

## Phase 3: User Story 1 - A new name needs a yes (P1) 🎯 MVP

### Tests (integration, Add a book)

- [ ] T009 [US1] `test_new_author_prompts_and_saves_nothing` (AC-01): with author "J DM
  Robb":
  - the response is 409, and `counts` are unchanged;
  - the field error "“J DM Robb” is not in the family catalog yet" is shown and listed in
    the error summary;
  - the typed values are kept.
- [ ] T010 [US1] `test_use_similar_author` (AC-02):
  - the prompt offers "Use “J.D. Robb”" first (at most 3 choices);
  - posting `use_author_0=<id>` returns 303, and the book is saved with J.D. Robb and no
    new author;
  - a `use_author_0` naming no catalog author (a random UUID, or junk) is ignored, and the
    prompt shows again.
- [ ] T011 [US1] `test_confirm_new_author` (AC-03): posting `confirm_author_0="J DM Robb"`
  returns 303, and the author J DM Robb exists.
  - **Added meanwhile (edge case):** if another member adds "J DM Robb" between the prompt
    and the confirmation, the confirmation gives the existing "Already in the catalog"
    choice, and no duplicate is created.
- [ ] T012 [US1] `test_new_series_prompt_use_and_confirm` (AC-04): with "Dresdin Files",
  the prompt offers "Use “The Dresden Files”"; `use_series` saves to it, and
  `confirm_series` creates the new series.
- [ ] T013 [US1] `test_several_new_names_on_one_page` (AC-05):
  - two new authors and a new series give three prompts, and nothing is created;
  - confirming one keeps it as a hidden field and still prompts for the other two;
  - once all are settled the book is saved, with authors in their row order.
- [ ] T014 [US1] `test_confirmation_is_for_the_exact_name` (AC-06): confirming "J DM Robb"
  and then posting author "J D M Robb" prompts again, and nothing is saved.
- [ ] T015 [US1] **guard** `test_picked_and_exact_names_unchanged` (AC-07):
  - picked ids give no prompt;
  - an exact typed match in other capitals gives the existing "Use existing author"
    conflict, not a prompt.

### Implementation

- [ ] T016 [US1] In `src/book_tracker/web/routes/readings.py`:
  - a `NewName` dataclass;
  - `new_name_prompts(db, form) -> list[NewName]`, read-only (R1 steps 1–5 without
    creating);
  - `resolve_authors` and `resolve_series` handle `use_*` ids and create only confirmed
    names; an exact match keeps today's conflict;
  - the prompts are added to `form.errors` as field errors (R4).
- [ ] T017 [US1] In `add_book`:
  - compute the prompts on every save;
  - with field errors, answer 422 with the prompts;
  - with prompts, answer 409 with the prompts and any conflicts;
  - otherwise save as today.
- [ ] T018 [US1] Templates:
  - a new `partials/new_name.html` (field notice, "Use" buttons, "Add … as a new …"
    button);
  - `partials/book_fields.html` includes it per author row and for the series, renders a
    hidden `confirm_*` for each confirmed name, and passes `new_names` through from the add,
    entry and edit-book pages.
  - T009–T015 pass.

## Phase 4: User Story 2 - A book's page and Edit book (P1)

### Tests

- [ ] T019 [US2] `test_book_page_new_author_waits_for_confirmation` (AC-08):
  - on `POST /entries/{id}`, a typed new author plus a notes change gives 409 with the
    prompt; neither the book's authors nor the entry's notes change;
  - confirming saves both.
- [ ] T020 [US2] `test_edit_book_new_series_prompt` (AC-09): on `POST
  /catalog/books/{id}/edit` with a new series name, the prompt appears; "Use" and confirm
  both work.
- [ ] T021 [US2] **guard** `test_unchanged_names_no_prompt` (AC-10): saving the book's page
  and Edit book with its current authors and series and other changes gives 303 with no
  prompt.

### Implementation

- [ ] T022 [US2] Add `new_names` to `BookSaveProblem`, and have `save_book_details` return
  409 with the prompts. The entry page renderer (`readings.py`) and the edit-book renderer
  (`catalog.py`) pass `new_names` to their templates. T019–T021 pass.

## Phase 5: User Story 3 - Works with the rest of the form (P2)

- [ ] T023 [US3] `test_prompt_with_field_errors` (AC-11): a missing title plus a new author
  gives 422, both errors are shown, and nothing is saved.
- [ ] T024 [US3] `test_add_another_keeps_choice_and_carries_new_author` (AC-12):
  - with `then=another`, confirm a new author: the redirect goes to the next-book form;
  - that form has the new author chosen (with its id);
  - saving the next book gives no prompt.
- [ ] T025 [P] [US3] Browser test `test_confirm_flow_without_js` (AC-13), with JavaScript
  off:
  - type "J DM Robb" and save;
  - click "Use “J.D. Robb”" and land on My books;
  - repeat with a new name and click "Add … as a new author".
- [ ] T026 [P] [US3] Browser test `test_prompt_accessibility` (AC-14):
  - the error summary links to the author field;
  - the buttons are at least 44 × 44, with no sideways scroll at 360, 390, 820, 1,024 and
    1,440;
  - axe passes at phone, tablet and laptop widths with the prompt showing.
- [ ] T027 [US3] Make T023–T026 pass. Expected: a fix in the 422 path of `add_book`, plus
  CSS for the button stack in `.conflict` if a test needs it.

## Phase 6: Polish

- [ ] T028 Amend the `/books/add`, `/entries/{id}` and `/catalog/books/{id}/edit` rows in
  `specs/001-family-reading-list/contracts/ui-routes.md` to point to
  `contracts/ui-new-names.md`.
- [ ] T029 Run every gate in CLAUDE.md:
  - ruff, ruff format, `mypy --strict`;
  - the full pytest suite with coverage and `scripts/check_coverage.py`;
  - `-m a11y`, `-m perf` and `pip-audit`;
  - the OpenAPI contract check, which should show no JSON API change.

  FR-009: the spec 002 import tests in the full suite pin that import is unchanged.
- [ ] T030 Walk through quickstart.md with screenshots at 390 and 1,440 px, then set the
  spec status to Implemented.

## Dependencies

- **Order:** Setup, then Foundational (T004–T008), then US1 (T009–T018), then US2
  (T019–T022), then US3 (T023–T027), then Polish.
- **US2:** reuses US1's `new_name_prompts` and template partial.
- **US3:** needs US1 and US2.

## Implementation Strategy

- **MVP:** US1 on Add a book, which stops new typos where most books are entered.
- **Then:** US2 for the book's page and Edit book, then US3, then the gates.
- **Delivery:** one PR.
