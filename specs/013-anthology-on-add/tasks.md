# Tasks: Anthology Stories on Add a Book (spec 013)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("013/AC-xx")`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [ ] T001 Check the baseline. On `013-anthology-on-add`, run `uv run pytest -q`, ruff and
  mypy. All must be green before any change.

## Phase 2: Foundational

- [ ] T002 [P] Write failing unit tests in `tests/unit/test_story_rows.py` for parsing story
  rows in `src/book_tracker/web/forms.py`:
  - the `anthology` checkbox;
  - rows 0–49 read in order and renumbered, with gaps ignored and rows past 49 dropped;
  - `is_blank`;
  - row field errors keyed `story_title_{i}` / `story_number_{i}`, worded "Story N: …";
  - number range (0–999.99);
  - AC-11: no series on the row or the book;
  - AC-12: repeated (series, number) pairs, where a blank series means the book's series
    name, and both rows are marked;
  - AC-08: the box is unticked but a row has text;
  - `story_id_{i}` rows.

  Then add `StoryRow`, `AddBookForm.anthology` / `.stories` and the parser to make them
  pass.
- [ ] T003 Add `StoryNumberTaken(ConflictError)` with `index` and `story` to
  `src/book_tracker/services/errors.py`. Add the `BookStory` values (new or existing) to
  `src/book_tracker/services/catalog.py`.
- [ ] T004 Write failing service tests in `tests/integration/test_anthology_service.py`
  for `services/readings.add_entry(..., stories=...)`:
  - new stories default to the book's series and authors;
  - an existing story is linked, not copied;
  - a story-number conflict raises `StoryNumberTaken` with the right index;
  - a deleted story id raises `ValidationFailed` with `stories.{i}.story_id`;
  - `stories` with `book_id` is refused;
  - after any failure, nothing remains once the transaction rolls back.

  Then implement it in `src/book_tracker/services/readings.py` and
  `src/book_tracker/services/catalog.py`.

## Phase 3: User Story 1 – Record a collection's stories while adding it (P1) 🎯 MVP

- [ ] T005 [US1] Write failing tests in `tests/integration/test_anthology_add.py` for
  AC-01 to AC-07 and AC-09:
  - the checkbox and section render;
  - a save with three rows creates the book, the entry and three stories, using the book's
    series and authors;
  - the redirect carries `stories=3` and the notice says "with 3 stories";
  - **Add another story** and **Remove story N** redraw with everything kept, write
    nothing (row counts unchanged) and put `autofocus` on the right element;
  - no add button at 50 rows;
  - blank rows are ignored;
  - from a series gap (spec 006), a blank row series is that series.
- [ ] T006 [US1] Add `src/book_tracker/web/templates/partials/story_rows.html` and the
  checkbox and section in `src/book_tracker/web/templates/pages/add_book.html`. Follow the
  ui contract: fieldsets named "Story N", hints, and comboboxes for series and author.
- [ ] T007 [US1] In `src/book_tracker/web/routes/readings.py`:
  - handle `action=add_story` and `remove_story:{i}` (redraw, 200, no writes);
  - on save, resolve each row's names and build `BookStory` items for `add_entry`;
  - add `stories=N` to the three success redirects.

  Show the count in the notices on My books, Add a book (`after`) and the series page.
- [ ] T008 [US1] Add the `[data-anthology-toggle]` handler to
  `src/book_tracker/web/static/js/app.js` (hide `#stories` when unticked on load; toggle on
  change; never clear). Add the row layout styles to `src/book_tracker/web/static/css/app.css`.

## Phase 4: User Story 2 – Mistakes are caught before anything is saved (P1)

- [ ] T009 [US2] Write failing tests in `tests/integration/test_anthology_checks.py` for:
  - AC-08: unticked box with rows that have text;
  - AC-10: blank title, missing number, out-of-range number. Messages sit beside each
    field and in the summary, and nothing is saved (counts of book, story, author, series
    and entry unchanged);
  - AC-11: no series anywhere;
  - AC-12: a repeated pair;
  - AC-13: a taken number shows the existing story and its books. **Use that story** turns
    the row into that story, and the next save links it;
  - AC-14: a number shared with a book is allowed;
  - AC-16: a race, where the story appears between the pre-check and the insert (patch
    `story_at`), shows the AC-13 choice on that row;
  - AC-17: a failure after the book is created leaves no book, story or entry behind.
- [ ] T010 [US2] Implement the pre-check and the `use_story_{i}` action, mapping
  `StoryNumberTaken` to its row, in `src/book_tracker/web/routes/readings.py`. Add the
  taken-row message and the read-only existing-story row in `story_rows.html`.
- [ ] T011 [US2] Write failing tests in `tests/integration/test_anthology_names.py` for
  AC-15:
  - new author and series names on rows get the spec 005 prompt beside the first field
    with each name;
  - a name typed on the book and on two rows gives one prompt;
  - confirming creates it once and it is used everywhere;
  - "Use <similar>" applies to every field with that name;
  - picked or existing names need no prompt;
  - nothing is saved while prompts are open.
- [ ] T012 [US2] Generalize `new_name_prompts`, `resolve_authors` and `resolve_series` in
  `src/book_tracker/web/routes/readings.py` (and `web/forms.py` for the row
  `confirm_story_*` / `use_story_*` fields) to walk the book's fields and then the rows,
  grouped by lower-cased name (research R6). Spec 005 and spec 009 tests must stay green.

## Phase 5: User Story 3 – Fits the rest of Add a book (P2)

- [ ] T013 [US3] Write failing tests, added to `tests/integration/test_anthology_add.py`:
  - AC-18: with a chosen catalog book there is no checkbox, and the note shows;
  - AC-19: **Draft summary with AI** and **Regenerate** (with `FakeSummaryGenerator`), a
    field error, and a new-name prompt all keep the checkbox and every row;
  - AC-20: the duplicate-book conflict, adding the existing book instead, leads to the
    entry page with `msg=stories_not_added` and an Edit book link, and no stories are
    saved;
  - AC-21: **Add and add another** gives an unticked box and no rows.
- [ ] T014 [US3] Implement AC-18, AC-19, AC-20 (the `dropped_stories` hidden field and the
  message) and AC-21 in `add_book.html`, `entry.html` and
  `src/book_tracker/web/routes/readings.py`.

## Phase 6: User Story 4 – JSON API (P2)

- [ ] T015 [P] [US4] Write failing contract tests in
  `tests/contract/test_anthology_contract.py` for AC-22 to AC-27:
  - 201 with stories, read back via `GET /api/v1/books/{id}/stories`;
  - 422 for more than 50 items, a missing title or number, no series, a repeated pair, a
    repeated story id, or `stories` with `book_id`;
  - 409 `story_number_taken` with `existing_id`;
  - nothing saved on any error;
  - unchanged behaviour without `stories`.

  Every response is checked with `assert_matches_contract`.
- [ ] T016 [US4] Add `NewBookStory` to `src/book_tracker/schemas/catalog.py`, and
  `ReadingEntryCreate.stories` with its validators to
  `src/book_tracker/schemas/readings.py`. Pass the stories through in
  `src/book_tracker/api/readings.py`. Regenerate `openapi.yaml`, the generated JSON and
  the baseline in `specs/001-family-reading-list/contracts/` (additive change).

## Phase 7: User Story 5 – Usable everywhere (P2)

- [ ] T017 [US5] Write `tests/a11y/test_anthology_a11y.py` for AC-28 to AC-30:
  - the section open, rows with errors, the taken-number choice and new-name prompts, at
    every spec 003 width, checked with axe and the layout checks;
  - with JavaScript, the toggle shows and hides without a page load;
  - with JavaScript off, a full keyboard journey: tick, add, remove, fill in, save;
  - "Story N" group names, "Remove story N" button names, and focus after add and remove.

  Fix whatever fails.
- [ ] T018 [US5] Add a perf test in `tests/perf/` for SC-002: a 50-row save in the 5,000-book
  catalog, p95 under 1 s, plus an **Add another story** redraw at 49 rows.

## Phase 8: Polish

- [ ] T019 Update the `specs/001-family-reading-list/contracts/ui-routes.md` rows for
  `/books/add` (the new actions and redirects). Note in the spec 009 Assumptions that
  stories can now also be added on Add a book.
- [ ] T020 Run every gate:
  - `uv run ruff check . && uv run ruff format --check .`
  - `uv run mypy --strict src`
  - `uv run pytest --cov`, then `scripts/check_coverage.py`
  - `pytest -m a11y`
  - `pytest -m perf`
  - `pip-audit`
  - check that the OpenAPI export is current

  Then work through [quickstart.md](quickstart.md) by hand.

## Dependencies

- T002–T004 come before every story phase.
- US1 (T005–T008) comes before US2 and US3, which add to its route and templates.
- US4 (T015–T016) needs only T003–T004 and can run in parallel with US1–US3.
- US5 and the Polish phase come last.

## Parallel opportunities

- T002 can run alongside T003.
- T015 and T016 (API) can run alongside the web phases.
- T011 can be written alongside T009.

## Implementation strategy

The MVP is Phases 1–3: stories saved with the book. Each later phase is independently
testable. Ship as one PR.
