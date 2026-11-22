---
description: "Task list for spec 009, stories in collections"
---

# Tasks: Stories in Collections

**Tests**: REQUIRED (Principle V). Acceptance tests are tagged
`@pytest.mark.ac("009/AC-xx")`. Each test task comes before its code and is seen failing
first.

## Phase 1: Setup

- [X] T001 Migrations test first: `tests/integration/test_migrations.py` gains
  `TABLES_0004`, which checks that `story`, `story_author` and `book_story` exist after
  upgrade and are gone after downgrade to 0003. Seen failing.
- [X] T002 `migrations/versions/0004_collection_stories.py` and the ORM models in
  `persistence/models.py` (`Story`, `StoryAuthor`, `BookStory`), per data-model.md. T001
  passes.
- [X] T003 Fixtures: `Factory.story(title, actor, series_id, number, author_ids=, book_ids=)`
  in `tests/conftest.py`.

## Phase 2: Foundational (domain, persistence, service)

- [X] T004 Constraint tests in `tests/integration/test_stories.py`:
  - a second story at the same series and number is refused by the database (SC-004);
  - the number is in range; the series is NOT NULL;
  - a story and a book may share a number (AC-06, database level);
  - an author with a story can't be deleted (foreign key).
- [X] T005 `domain/models.py` (`BookRef`, `Story`), `persistence/mappers.py` (`to_story`),
  and `persistence/catalog.py`:
  - reads: `get_story`, `book_stories`, `series_stories`, `author_stories`,
    `find_story_by_series_number`;
  - writes: `create_story`, `link_story`, `unlink_story` (research R2), `update_story`.
- [X] T006 Service tests (`tests/integration/test_stories.py`):
  - `add_new_story`: links to the book; conflict `story_number_taken` with existing
    id/label; unknown book → not found;
  - `add_existing_story`: added vs already there; a story deleted meanwhile → not found;
  - `update_story`: conflict; a stale or deleted story → not found;
  - `remove_story`: kept when in another book, deleted with its last link; not in this book
    → not found.
- [X] T007 `services/catalog.py` story use cases. T004 and T006 pass.

## Phase 3: User Story 1 - Record stories (P1) 🎯 MVP

- [X] T008 [US1] Tests (`tests/integration/test_stories.py`):
  - `test_edit_book_lists_stories` (AC-01);
  - `test_add_story_form_defaults` (AC-02);
  - `test_add_story` (AC-03): message only for a story in this book;
  - `test_add_story_errors` (AC-04);
  - `test_number_held_by_story` (AC-05): nothing saved, the choice is offered, **Add that
    story to this book** links it, and the race on the unique index gives the same page;
  - `test_number_shared_with_book` (AC-06);
  - `test_story_new_names` (AC-07): spec 005 prompts, then confirm;
  - `test_entry_page_lists_stories` (AC-08).
- [X] T009 [US1] `web/forms.py` (`parse_story`, `story_form`, `story_start_form`),
  `web/routes/stories.py` (add story), and the Edit book section and entry page list.
  Templates: `add_story.html`, `partials/story_fields.html`, `edit_book.html`,
  `entry.html`. T008 passes.

## Phase 4: User Story 2 - Series page (P1)

- [X] T010 [P] [US2] Unit tests `tests/unit/test_series_rows_stories.py`:
  - order with books and stories, book first at the same number (AC-09, AC-10);
  - derived status precedence and date (AC-11);
  - gaps filled by whole-number stories, and runs ended by fractional ones (AC-12);
  - progress counts (AC-13);
  - "contains" numbers (AC-14).
- [X] T011 [US2] Integration tests `tests/integration/test_series_stories.py`:
  - the page for the spec example (AC-09 to AC-14);
  - `test_other_members_reading_never_shows` (AC-15, cross-user).

  In `persistence/readings.py` tests: `list_books` returns only the bound user's entries.
- [X] T012 [US2] `persistence/readings.py` `list_books`; `services/readings.py`
  `series_rows`/`whole_series_view` with stories; `series.html` story rows and progress.
  T010 and T011 pass.

## Phase 5: User Story 3 - Edit, link, remove (P2)

- [X] T013 [US3] Tests:
  - `test_edit_story` (AC-16): saved for every book; the number is taken by another story;
  - `test_add_existing_story_by_suggestion` (AC-17): a title suggestion's `story_id`, a
    stale id with edited title ignored, already in the book;
  - `test_remove_story_kept_elsewhere` (AC-18);
  - `test_remove_last_link_deletes` (AC-19);
  - `test_author_with_only_stories` (AC-20): not deletable, not unused, listed on Edit
    author;
  - `test_story_not_found` (AC-21).
- [X] T014 [US3] Edit story and remove routes, with templates `edit_story.html` and
  `confirm_remove_story.html`; `/suggest/stories`; spec 008 changes in
  `persistence/catalog.py` and `edit_author.html`. T013 passes.

## Phase 6: User Story 4 - Find by story title (P3)

- [X] T015 [US4] Test `test_book_suggested_by_story_title` (AC-22), on both `/suggest/books`
  and the API search.
- [X] T016 [US4] `search_books` story condition and `story_matches`; the suggest detail.
  T015 passes.

## Phase 7: User Story 5 - API, accessibility, performance (P2)

- [X] T017 [P] [US5] `tests/contract/test_stories_contract.py` (AC-26): every endpoint and
  status in contracts/api-stories.md.
- [X] T018 [US5] `schemas/catalog.py` (`BookRef`, `Story`, `StoryAdd`, `StoryUpdate`),
  `schemas/mappers.py`, `api/stories.py`, `api/books.py`, `main.py`; `openapi.yaml` and
  the regenerated baseline; check with oasdiff. T017 passes.
- [X] T019 [P] [US5] `tests/a11y/test_stories_a11y.py` (AC-23, AC-24, AC-25): axe and the
  three widths on add story, edit story, the remove confirmation, Edit book with stories,
  and the series page; the story row's reading order; everything without JavaScript.
  `tests/a11y/test_layout_003.py` if row layouts change. CSS in `static/app.css`.
- [X] T020 [P] [US5] Perf test (SC-002): a series page with 100 books and 100 stories in
  the 5,000-book catalog, and Edit book with 50 stories.

## Phase 8: Polish

- [X] T021 Amend spec 001 `contracts/ui-routes.md` with the routes in
  contracts/ui-stories.md.
- [X] T022 Run the full gates: ruff, format, mypy --strict, pytest with coverage,
  check_coverage, a11y, perf, pip-audit, export_openapi plus oasdiff.

## Dependencies

- Phase 1 comes before Phase 2, which comes before every story.
- US1 comes before US3 (the forms are reused).
- US2 needs only Phase 2.
- US4 and US5 come after US1.
- T017 and T018 can run alongside US2 and US3.

## Implementation notes

- The Add a story form reuses `AddBookForm` / `parse_add_book`, so the spec 005 prompts
  and conflict handling are unchanged. The author rows and series fields moved out of
  `book_fields.html` into `partials/author_rows.html` and `partials/series_fields.html`;
  the book form includes them as before.
- Without JavaScript, a typed catalog series name on Add a story gives today's "Use
  existing series" choice (spec 005), the same as on Add a book. The existing-story check
  (AC-05) runs once a catalog series is chosen.
- Spec 008's API 409 keeps `author_has_books` / "This author has books" for an author
  with only stories (research R8); the pages say "now has a story".
- Perf (SC-002), on the development machine: series page 182 ms p95, Edit book with 50
  stories 33 ms, book type-ahead 56 ms.
