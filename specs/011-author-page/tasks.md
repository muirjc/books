# Tasks: Author Page and Favorite Authors (spec 011)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: required (Constitution V). Each test is written first and seen failing. Tests are
tagged `@pytest.mark.ac("011/AC-xx")`.

## Phase 1: Setup

- [X] T001 Amend `.specify/memory/constitution.md` to 2.0.0: the Principle I exception and
  the Sync Impact Report.
- [X] T002 Add `favorite_author` to the tests' table list in `tests/conftest.py`, add
  `Factory.favorite(user, author_id)`, and add `TABLES_0005` to
  `tests/integration/test_migrations.py`.

## Phase 2: Foundational

- [X] T003 Write a failing migration test (AC-11) in `tests/integration/test_migrations.py`
  and `tests/integration/test_favorite_authors.py`: the primary key, CASCADE on user,
  RESTRICT on author, and upgrade → downgrade → upgrade.
- [X] T004 Add `migrations/versions/0005_favorite_authors.py` and `FavoriteAuthor` in
  `src/book_tracker/persistence/models.py`.
- [X] T005 Write a failing test for, then add, `FavoriteAuthorRepository` in
  `src/book_tracker/persistence/favorites.py` (research R1), and add it to
  `scripts/check_coverage.py`.

## Phase 3: User Story 1 - See an author's books (P1)

- [X] T006 [US1] Write failing tests for AC-01 to AC-07 in
  `tests/integration/test_author_page.py`.
- [X] T007 [US1] Add `author_view` in `src/book_tracker/services/authors.py` (research R2).
- [X] T008 [US1] Add `GET /authors/{id}` in `src/book_tracker/web/routes/authors.py`, the
  template `pages/author.html`, the `author_links` macro and its uses, and the author links
  on the entry page and Edit book. Register the router in `main.py`.

## Phase 4: User Story 2 - Mark a favorite author (P1)

- [X] T009 [US2] Write failing tests for AC-08 and AC-09 (pages) and AC-10 (API, including
  contract tests in `tests/contract/test_favorites_contract.py`).
- [X] T010 [US2] Add `add_favorite`, `remove_favorite` and `favorite_authors` to the
  service; `FavoriteForm`; `POST /authors/{id}/favorite`; and `api/favorites.py`. Add them
  to `openapi.yaml` and regenerate the baseline.

## Phase 5: User Story 3 - Use my favorites (P2)

- [X] T011 [US3] Write failing tests for AC-12 and AC-13 (page, filter, API parameter, and
  cross-user).
- [X] T012 [US3] Add `GET /authors/favorites` and `pages/favorite_authors.html`; the
  `extra` condition in `ReadingEntryRepository.list`; `author_id=favorites` on My books;
  and `favorite_authors` on `/api/v1/me/readings`.

## Phase 6: User Story 4 - Favorites and deleting unused authors (P2)

- [X] T013 [US4] Write failing tests for AC-14 to AC-17, including the race between confirm
  and delete, the API 409, and a check that the refusal names no member.
- [X] T014 [US4] Add `_deletable` and `author_favorited` in `persistence/catalog.py`; the
  `author_is_favorite` conflict; the Edit author messages; and the unused list and count.

## Phase 7: Polish

- [X] T015 [P] Add `tests/a11y/test_author_a11y.py` (AC-18): layouts and axe at five
  widths, no-JS favoriting, and the keyboard journey. Then add the CSS.
- [X] T016 [P] Add perf budgets (SC-001) in `tests/perf/test_list_performance.py`: an
  author with 300 books, My favorite authors, and the favorites filter.
- [X] T017 [P] Amend `specs/001-family-reading-list/contracts/ui-routes.md`.
- [X] T018 Run all the gates.

## Implementation notes

- **T008**: the page shows its message through the base template's `#messages` region,
  like every other page, not a copy of its own. An early draft printed it twice; the a11y
  test caught it.
- **T010**: `PUT` and `DELETE` are idempotent. Only an unknown author returns 404.
- **T014**:
  - `services.catalog.delete_author` reads the classification fresh after a refused delete.
    If no works list the author and any favorite exists, it raises `author_is_favorite`.
    This covers the RESTRICT foreign-key race (tested with a favorite committed by another
    session mid-delete).
  - Edit author shows the "mine" or "other" message instead of **Delete author**.
- **T016**: p95 was 249 ms for the 300-book author page, 17 ms for My favorite authors, and
  174 ms for the favorites filter.
- **T015**: author names in book rows link to the Author page. On My books at phone width, axe saw that link alone in a grid cell, not as inline text, and flagged it as a 19 px target. Links in row details now get the 24 px WCAG minimum (`.book-meta a`). The spec 007 Upcoming check of 44 px targets now covers each row's own targets, not the inline author links.

## PR #30 review fixes

- **Delete retry**: `delete_author` classifies with EXISTS checks (`author_has_works`,
  `author_favorited`), not by loading lists. If nothing blocks the delete by the time it is
  classified, it tries the delete once more, instead of answering `author_has_books` for an
  author with no books.
- **Refusal message**: a refusal for a favorite always says why. If the favorite is gone
  again, the page shows the "family member" reason.
- **User binding**: the My books favorites condition is built inside
  `ReadingEntryRepository` (`favorite_authors: bool`) from its own bound user. The
  repository no longer accepts an arbitrary condition.
- **API cross-user test**: Ben's PUT and DELETE leave Alice's favorites unchanged.
- **Constitution 2.0.0 wording**: the exception covers leaving a favorited author out of
  the deletable-authors list and count (AC-15), not only the refusal.
- **Fewer queries**: Edit author looks up favorites only for an author with no works.
