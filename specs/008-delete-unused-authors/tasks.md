---
description: "Task list for spec 008, delete an author with no books"
---

# Tasks: Delete an Author With No Books

**Tests**: REQUIRED (Principle V). Acceptance tests are tagged `@pytest.mark.ac("008/AC-xx")`.
Each test task comes before its code and is seen failing first.

## Phase 1: Setup

- [ ] T001 Create `tests/integration/test_delete_author.py` with:
  - `alice`/`ben` fixtures;
  - "J.D. Robb" with two books, and "J DM Robb" and "Nobody Writes" with none.

## Phase 2: User Story 1 - Find and delete (P1) 🎯 MVP

- [ ] T002 [US1] Tests (they fail first):
  - `test_my_books_links_unused_authors` (AC-01): the count is shown, and the link is
    absent when there are none or in the HTMX partial;
  - `test_unused_authors_page` (AC-02): order and links, plus the empty text;
  - `test_delete_asks_first` (AC-03): a POST without `confirm` shows the question and
    deletes nothing;
  - `test_delete_author` (AC-04):
    - `303` to the list with the message;
    - the author is gone from the database and the type-ahead;
    - its Edit author page gives 404;
    - the name is escaped in the message;
  - `test_cancel` (AC-05): the Cancel link points to Edit author.
- [ ] T003 [US1] `persistence/catalog.py`: `author_books`, `unused_authors`,
  `unused_author_count` and `delete_unused_author`. `services/catalog.py`:
  `delete_author`, `author_books`, `unused_authors` and `unused_author_count`.
- [ ] T004 [US1] `web/routes/catalog.py`: the unused page and the delete route. My books
  gets the count. Templates: `unused_authors.html`, `confirm_delete_author.html`,
  `edit_author.html` (books, Delete) and `list.html` (the link). T002 passes.

## Phase 3: User Story 2 - Authors with books (P1)

- [ ] T005 [US2] Tests:
  - `test_author_with_books_lists_them` (AC-06): the books are listed with links, the
    message is shown, and there is no Delete form;
  - `test_book_added_meanwhile` (AC-07): a `confirm=yes` POST for J.D. Robb gives 409,
    the message, and the author is kept;
  - `test_delete_unknown_author` (AC-08): a random id gives 404, and a second delete gives
    404;
  - a signed-out POST is refused.
- [ ] T006 [US2] Contract `tests/contract/test_delete_author_contract.py` (FR-004, FR-005):
  `DELETE` returns 204, then 404, and 409 for J.D. Robb, each matching `openapi.yaml`.
- [ ] T007 [US2] `api/authors.py`: the DELETE endpoint. `openapi.yaml`: the new operation.
  Regenerate `openapi.generated.json`. T005–T006 pass.

## Phase 4: User Story 3 - Usable everywhere (P2)

- [ ] T008 [P] [US3] Browser `tests/a11y/test_delete_author_a11y.py` (AC-09):
  - the pages: the unused list, Edit author with and without books, and confirm;
  - at 360, 390, 820, 1,024 and 1,440: no sideways scroll, and 44 px targets;
  - axe at phone, tablet and laptop widths;
  - the no-JS delete flow.
- [ ] T009 [P] Perf (SC-003): the unused page and My books with 1,500 authors, where some
  have no books.

## Phase 5: Polish

- [ ] T010 Amend `specs/001-family-reading-list/contracts/ui-routes.md`.
- [ ] T011 Run every gate in CLAUDE.md; take screenshots at 390 and 1,440 px; set the spec
  to Implemented.
