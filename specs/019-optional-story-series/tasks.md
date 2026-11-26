# Tasks: Stories Without a Series (spec 019)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/ui-stories.md](contracts/ui-stories.md),
[contracts/api-stories.md](contracts/api-stories.md)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("019/AC-xx")`.

## Phase 1: Setup

- [X] T001 Baseline: run `uv run pytest -q` on branch `019-optional-story-series` before any
  change. (Branched from main at 4fcbee9, green in CI after PR #43.) (The two Docker-dependent `tests/unit/test_pi_deploy.py` tests fail locally while
  Docker Desktop's engine is unreachable; they pass in CI.)

## Phase 2: Foundational (blocks every story)

- [X] T002 Write failing migration tests in `tests/integration/test_migrations.py` (AC-14):
  - after `0007`, a story with no series and no number saves; one with only a series, or
    only a number, is refused by `story_series_both_or_neither`; two stories without a
    series may share a title; the unique (series, number) rule still holds;
  - existing stories keep their series and number, and existing `book_story` rows get
    positions per book in series-name-then-number order;
  - the downgrade succeeds when every story has a series, and is refused with a clear
    message while one doesn't.
- [X] T003 Implement `migrations/versions/0007_optional_story_series.py` and the models in
  `src/book_tracker/persistence/models.py` (`Story.series_id` / `series_number` nullable,
  the CHECK; `BookStory.position`) (research R1).
- [X] T004 Make `domain.Story.series` `SeriesRef | None` and `series_number`
  `Decimal | None` in `src/book_tracker/domain/models.py`; update `to_story` in
  `src/book_tracker/persistence/mappers.py`, `story_label` in
  `src/book_tracker/services/catalog.py` (title only without a series, with a unit test in
  `tests/unit/`), and every place mypy --strict then reports, without changing behaviour for
  stories with a series.
- [X] T005 Write failing repository tests in `tests/integration/test_story_series_optional.py`
  (AC-09, research R2, R3):
  - each new link sorts after the book's earlier links (the position sequence);
  - `book_stories` lists stories with a series by series name then number, then stories
    without a series by position;
  - `series_stories` never returns a story without a series.
- [X] T006 Implement `create_story` / `update_story` with an optional pair, and the `book_stories` and `story_matches` order in
  `src/book_tracker/persistence/catalog.py`.

## Phase 3: User Story 1 – Record a book of unrelated stories (Priority: P1) 🎯 MVP

**Goal**: stories with no series and no number can be saved from every form.
**Independent Test**: add an anthology with three stories and no series or numbers; the
book page lists the three with their authors and no numbers.

- [X] T007 [US1] Write failing tests in `tests/integration/test_story_series_optional.py`:
  - AC-01: Add a book's story rows with no number and no series save stories without a
    series, in row order, whether or not the book has a series; the hint text;
  - AC-02: a number with a blank series takes the book's series;
  - AC-03: a series with no number is refused with the row message; nothing is saved and
    everything typed is kept;
  - AC-07: a number with a blank series and a book with no series is refused with the
    reworded message;
  - duplicate checks (spec 013 AC-12, AC-13) skip rows without a series;
  - AC-04: Add a story (series prefilled) with the series cleared and no number adds a story
    without a series; series-only and number-only are refused beside the field;
  - AC-05: Edit story clears both, and gives both (with the spec 009 AC-16 refusal when the
    pair is taken);
  - AC-06: two stories without a series may share a title, and choosing one from the title
    suggestions adds it to a second book (not a copy).
- [X] T008 [US1] Implement:
  - the story rows' rules in `src/book_tracker/web/forms.py` and
    `src/book_tracker/web/anthology.py`, and `add_book_stories` / `_check_story_references`
    in `src/book_tracker/services/catalog.py` (research R5);
  - Add a story and Edit story in `src/book_tracker/web/routes/stories.py` and
    `add_new_story` / `update_story` in the service;
  - the story title suggestions in `src/book_tracker/web/routes/suggest.py`: a story
    without a series is labelled "in “Book”" only (analysis C1; T007 checks it);
  - the hints in `partials/story_rows.html`, `pages/add_story.html` and
    `pages/edit_book.html`.

  Rewrite the old tests of the changed rules (spec 009 AC-04 in
  `tests/integration/test_stories.py`; spec 013 AC-02, AC-10 and AC-11 in
  `tests/integration/test_anthology_add.py` and `tests/integration/test_anthology_checks.py`).
  A test keeps its old tag only where that criterion still holds (spec, "Amended specs");
  tests of the changed rules are tagged `019/AC-xx`.

## Phase 4: User Story 2 – See stories without a series in their books (Priority: P1)

**Goal**: such stories show by title and authors, in the agreed order.
**Independent Test**: an anthology with two stories without a series and one with a series,
checked on the book page, entry page, Edit book, the author page and Edit author.

- [X] T009 [US2] Write failing tests in `tests/integration/test_story_series_optional.py`:
  - AC-08: on the book page, entry page, Edit book, the author page's Stories list, Edit
    author and Edit story, a story without a series shows its title (and authors) with no
    "#", no series name, no empty link and no "All of" link; stories with a series as today;
  - AC-09: the order on the book page and Edit book (with a series by name then number, then
    the rest as added; a story added to a second book goes last there);
  - AC-10: "Also in “X”" on the book page for a story without a series in two books.
- [X] T010 [US2] Implement the templates: `partials/book_stories.html`, `pages/author.html`,
  `pages/edit_story.html` (research R4, contract ui-stories).

## Phase 5: User Story 3 – Series pages stay about series (Priority: P2)

- [X] T011 [US3] Write failing tests in `tests/integration/test_story_series_optional.py` for
  AC-11 (a series page, its progress counts and its Add #next row leave out stories without
  a series; a collection in the series still shows) and AC-12 (a story whose series is
  cleared leaves that series page). Fix whatever fails in
  `src/book_tracker/services/readings.py`.

## Phase 6: User Story 4 – The JSON API, access and speed (Priority: P2)

- [X] T012 [P] [US4] Write failing contract and integration tests for AC-13 in
  `tests/contract/test_stories_contract.py` and `tests/contract/test_anthology_contract.py`:
  - `StoryAdd` with no pair creates a story without a series; one of the pair alone → 422;
  - `StoryUpdate` sets both to null; one alone → 422;
  - `NewBookStory` / entry `stories`: no number and no `series_id` → no series; a number
    with no `series_id` takes the book's series, and 422 when the book has none;
    `series_id` with no number → 422; duplicate checks only with a series;
  - responses give `series` and `series_number` as null; `GET /books/{id}/stories` order;
    `GET /stories?series_id=` leaves stories without a series out.
- [X] T013 [US4] Implement the schemas in `src/book_tracker/schemas/catalog.py`,
  `src/book_tracker/schemas/readings.py` and `src/book_tracker/schemas/mappers.py`, and the
  API routes' handling in `src/book_tracker/api/stories.py` and
  `src/book_tracker/api/readings.py` (research R6). Regenerate
  `specs/001-family-reading-list/contracts/openapi.generated.json` with
  `uv run python -m book_tracker.export_openapi`.
- [X] T014 [P] [US4] Write `tests/a11y/test_story_series_optional_a11y.py` for AC-15: the
  story rows with a row error, Add a story and Edit story with a field error, and the book
  page, entry page and Edit book listing stories without a series, at every spec 003 width
  (no sideways scroll, 44 px targets, axe), and the AC-01 and AC-04 flows with JavaScript
  off. Fix whatever fails in `src/book_tracker/web/static/css/app.css`.
- [X] T015 [P] [US4] Write `tests/perf/test_story_series_optional_perf.py` for AC-16: the
  book page and entry page of a 30-story anthology with no series, and a series page with
  stories, under 1 s p95 at 5,000 books.

## Phase 7: Polish

- [X] T016 Add dated notes pointing to spec 019 to spec 009 (AC-01, AC-04) and spec 013
  (AC-02, AC-10, AC-11), and to their contracts
  (`specs/009-collection-stories/contracts/{ui,api}-stories.md`,
  `specs/013-anthology-on-add/contracts/{ui,api}-anthology.md`).
- [X] T017 Run every gate (ruff, mypy, pytest with coverage, check_coverage, a11y, perf,
  pip-audit, the OpenAPI export check), then the quickstart.

## Dependencies

- T001, then Foundational (T002 → T003 → T004; T005 → T006). Everything else needs it.
- **US1** (T007 → T008) and **US2** (T009 → T010) both need Phase 2; US2's checks are
  easiest with US1's forms, so do US1 first.
- **US3** needs Phase 2 only.
- **US4**: T012 → T013 needs Phase 2; T014 needs US1 and US2; T015 needs Phase 2 and US2.
- Polish comes last.

**Parallel**: T012, T014 and T015 touch different files.

## Implementation strategy

- **MVP**: Phase 2 + US1 + US2. A member can record and see an anthology of unrelated
  stories.
- **US3**: confirms series pages are unaffected.
- **US4**: the API, accessibility and speed.
