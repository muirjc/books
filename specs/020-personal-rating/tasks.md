# Tasks: Personal Rating (spec 020)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/ui-rating.md](contracts/ui-rating.md),
[contracts/api-rating.md](contracts/api-rating.md)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("020/AC-xx")`.

## Phase 1: Setup

- [X] T001 Baseline: run `uv run pytest -q` on branch `020-personal-rating` before any
  change (branched from main at abf73a3).

## Phase 2: Foundational (blocks every story)

- [X] T002 Write failing migration tests in `tests/integration/test_migrations.py` (AC-13):
  - after `0008`, every existing entry has `rating` NULL and is otherwise unchanged;
  - ratings 1 and 5 save; 0 and 6 are refused by `reading_entry_rating_check`;
  - the downgrade succeeds with rated entries, drops the column, and the entries remain.
- [X] T003 Implement `migrations/versions/0008_personal_rating.py` and
  `ReadingEntry.rating` with the CHECK in `src/book_tracker/persistence/models.py` (R1).
- [X] T004 Add `rating: int | None` to `domain.ReadingEntry` in
  `src/book_tracker/domain/models.py` and map it in `to_reading_entry`
  (`src/book_tracker/persistence/mappers.py`); let the repository's create and update in
  `src/book_tracker/persistence/readings.py` take `rating`; fix whatever mypy --strict
  reports.

## Phase 3: User Story 1 – Rate a book (Priority: P1) 🎯 MVP

**Goal**: a member sets, changes and clears a rating on the entry page and Add a book.
**Independent Test**: rate an entry 4, see it saved; choose No rating, see it cleared.

- [X] T005 [US1] Write failing tests in `tests/integration/test_personal_rating.py`:
  - AC-01: the entry page has the "Rating (optional)" select with "No rating" and the five
    worded options; choosing 4 and saving stores 4; the select shows it selected on reload;
  - AC-02: choosing "No rating" clears it;
  - AC-03: Add a book with a rating stores it, also with Save and add another (spec 004) and
    with the anthology section (spec 013); with none chosen, no rating;
  - AC-04: a tampered value ("6", "x") saves nothing, shows "Choose a rating from 1 to 5, or
    No rating" beside the field, and keeps what was typed;
  - AC-05: a Want to read and a Reading entry can be rated; changing status keeps the
    rating (including Read again, spec 001 FR-029);
  - Edge Cases: an entry added from a quick-add row (spec 015) and one added by import
    (spec 002) have no rating.
- [X] T006 [US1] Implement:
  - the select in `src/book_tracker/web/templates/partials/entry_fields.html` (contract
    ui-rating);
  - `rating` in `parse_entry_update` and `parse_add_book` with the AC-04 message, in
    `src/book_tracker/web/forms.py`;
  - `ENTRY_FIELDS` and the Add a book payload in `src/book_tracker/web/routes/readings.py`;
  - `ReadingEntryCreate.rating` and `ReadingEntryUpdate.rating` in
    `src/book_tracker/schemas/readings.py`;
  - `rating` copied in `update_entry` and passed in `add_entry` in
    `src/book_tracker/services/readings.py` (R5).

## Phase 4: User Story 2 – See my ratings (Priority: P1)

**Goal**: "Rated N out of 5" wherever the member's own entry shows.
**Independent Test**: entries rated 5, 2 and none, checked on My books and book pages.

- [X] T007 [US2] Write failing tests in `tests/integration/test_personal_rating.py`:
  - AC-06: My books rows show "Rated 5 out of 5" / "Rated 2 out of 5" and nothing for the
    unrated entry; no star characters;
  - AC-07: the book page (spec 016) shows "Rated N out of 5" with the status; the book page for a book not on my list shows no rating.
- [X] T008 [US2] Implement the `rating_text` macro in
  `src/book_tracker/web/templates/macros.html` and use it in
  `partials/reading_list.html` and `pages/book.html` (R6).

## Phase 5: User Story 3 – Sort and filter by rating (Priority: P2)

**Goal**: My books sorts by rating and filters by it.
**Independent Test**: entries rated 5, 4, 2 and two unrated; check each sort and filter.

- [X] T009 [US3] Write failing tests in `tests/integration/test_personal_rating.py`:
  - AC-08: "Highest rated" gives 5, 4, 2, then the unrated by title; "Lowest rated" gives 2,
    4, 5, then the unrated by title;
  - AC-09: each filter choice ("5", "4 and up", "3 and up", "2 and up", "Rated", "Not
    rated") lists exactly the matching entries; an unknown value is ignored;
  - AC-10: the rating filter combines with search, status and paging, is kept in the
    address and the paging links, Clear removes it, and it works as a plain GET (no
    JavaScript).
- [X] T010 [US3] Implement `rating` and `-rating` in `SORTS` and `_order`, and the
  `min_rating` / `rated` filter in `ReadingEntryRepository.list`
  (`src/book_tracker/persistence/readings.py`, coverage-critical); pass them through
  `list_entries` in `src/book_tracker/services/readings.py`; add the sort options and the
  Rating filter select in `src/book_tracker/web/routes/readings.py` and
  `src/book_tracker/web/templates/pages/list.html` (R2, R3).

## Phase 6: User Story 4 – The JSON API, privacy, access and speed (Priority: P2)

- [X] T011 [P] [US4] Write failing contract tests in
  `tests/contract/test_personal_rating_contract.py` (AC-11): create with a rating and
  without; update to a rating, to null, and with `rating` left out (kept); 0, 6 and "4.5"
  → 422; responses carry `rating`; `GET /me/readings` with `sort=-rating`, `sort=rating`,
  `min_rating=4`, `rated=true`, `rated=false`; every response matches the contract.
- [X] T012 [US4] Implement the API: the `ReadingEntry.rating` output in
  `src/book_tracker/schemas/readings.py` and `src/book_tracker/schemas/mappers.py`; the
  `Sort` literal, `min_rating` and `rated` in `src/book_tracker/api/readings.py`; the
  hand-written `specs/001-family-reading-list/contracts/openapi.yaml`; regenerate
  `specs/001-family-reading-list/contracts/openapi.generated.json` with
  `uv run python -m book_tracker.export_openapi`.
- [X] T013 [US4] Write cross-user tests in `tests/integration/test_personal_rating.py`
  (AC-12): with Ben's entry rated 5, Alice gets 404 for it by page and API (read, update);
  Alice's book page, series page, author page, catalog, Upcoming, story and title
  suggestions, and the catalog API for that book never contain Ben's rating. With Ben's
  entries rated 5, Alice's list filtered `rated=true` and `min_rating=4` and sorted
  `-rating`, by API and on My books, holds only her own entries. Fix whatever fails.
- [X] T014 [P] [US4] Write `tests/a11y/test_personal_rating_a11y.py` for AC-14: the entry
  page with the Rating field (and with its error), Add a book, and My books with ratings,
  the rating sort and filter, at every spec 003 width (no sideways scroll, 44 px targets,
  axe), and rating, sorting and filtering with JavaScript off. Fix whatever fails in
  `src/book_tracker/web/static/css/app.css`.
- [X] T015 [P] [US4] Write `tests/perf/test_personal_rating_perf.py` for AC-15: My books
  sorted by `-rating` and filtered by `4` and by `unrated`, at 5,000 books with mixed
  ratings, under 1 s p95.

## Phase 7: Polish

- [X] T016 Add a dated note to the product specification
  (`docs/Family Book Tracker – Specification.md`, FR-17) that spec 020 builds the rating.
- [X] T017 Run every gate (ruff, mypy, pytest with coverage, check_coverage, a11y, perf,
  pip-audit, the OpenAPI export check), then the quickstart.

## Dependencies

- T001, then Foundational (T002 → T003 → T004). Everything else needs it.
- **US1** (T005 → T006) first: US2–US4 test with ratings saved through it.
- **US2** (T007 → T008) and **US3** (T009 → T010) need US1; they touch different templates
  except `reading_list.html` (US2) and `list.html` (US3), so either order works.
- **US4**: T011 → T012 needs Phase 2 and T006's schemas; T013 needs US2; T014 needs US1–US3;
  T015 needs US3.
- Polish comes last.

**Parallel**: T011, T014 and T015 touch different files.

## Implementation strategy

- **MVP**: Phase 2 + US1 + US2. A member can rate books and see their ratings.
- **US3**: sorting and filtering.
- **US4**: the API, privacy checks, accessibility and speed.
