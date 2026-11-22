---
description: "Task list for spec 008, delete an author with no books"
---

# Tasks: Delete an Author With No Books

**Tests**: REQUIRED (Principle V). Acceptance tests are tagged `@pytest.mark.ac("008/AC-xx")`.
Each test task comes before its code and is seen failing first.

## Phase 1: Setup

- [X] T001 Create `tests/integration/test_delete_author.py` with:
  - `alice`/`ben` fixtures;
  - "J.D. Robb" with two books, and "J DM Robb" and "Nobody Writes" with none.

## Phase 2: User Story 1 - Find and delete (P1) 🎯 MVP

- [X] T002 [US1] Tests (they fail first):
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
- [X] T003 [US1] `persistence/catalog.py`: `author_books`, `unused_authors`,
  `unused_author_count` and `delete_unused_author`. `services/catalog.py`:
  `delete_author`, `author_books`, `unused_authors` and `unused_author_count`.
- [X] T004 [US1] `web/routes/catalog.py`: the unused page and the delete route. My books
  gets the count. Templates: `unused_authors.html`, `confirm_delete_author.html`,
  `edit_author.html` (books, Delete) and `list.html` (the link). T002 passes.

## Phase 3: User Story 2 - Authors with books (P1)

- [X] T005 [US2] Tests:
  - `test_author_with_books_lists_them` (AC-06): the books are listed with links, the
    message is shown, and there is no Delete form;
  - `test_book_added_meanwhile` (AC-07): a `confirm=yes` POST for J.D. Robb gives 409,
    the message, and the author is kept;
  - `test_delete_unknown_author` (AC-08): a random id gives 404, and a second delete gives
    404;
  - a signed-out POST is refused.
- [X] T006 [US2] Contract `tests/contract/test_delete_author_contract.py` (FR-004, FR-005):
  `DELETE` returns 204, then 404, and 409 for J.D. Robb, each matching `openapi.yaml`.
- [X] T007 [US2] `api/authors.py`: the DELETE endpoint. `openapi.yaml`: the new operation.
  Regenerate `openapi.generated.json`. T005–T006 pass.

## Phase 4: User Story 3 - Usable everywhere (P2)

- [X] T008 [P] [US3] Browser `tests/a11y/test_delete_author_a11y.py` (AC-09):
  - the pages: the unused list, Edit author with and without books, and confirm;
  - at 360, 390, 820, 1,024 and 1,440: no sideways scroll, and 44 px targets;
  - axe at phone, tablet and laptop widths;
  - the no-JS delete flow.
- [X] T009 [P] Perf (SC-003): the unused page and My books with 1,500 authors, where some
  have no books.

## Phase 5: Polish

- [X] T010 Amend `specs/001-family-reading-list/contracts/ui-routes.md`.
- [X] T011 Run every gate in CLAUDE.md; take screenshots at 390 and 1,440 px; set the spec
  to Implemented.

## Implementation notes

- **One-statement delete:** `DELETE FROM author WHERE id = :id AND NOT EXISTS (book_author
  …) RETURNING id`. When it deletes nothing, the service says why: the author is gone (404)
  or has books (409). The RESTRICT foreign key stays as the backstop.
- **The deleted name** is passed in the redirect's query (`author=`) and shown escaped,
  capped at 200 characters, only with `msg=deleted`.
- **Short titles:** list links get a 44 × 44 px minimum, so a one-word title such as "Mort"
  meets the target size.
- **SC-003:** with 200 unused authors beside the 1,500-author dataset, p95 is 16 ms for
  the list and 155 ms for My books with the link.
- **PR #24 review fixes:**
  - **Saving an author deleted meanwhile:** gives 404, not 500. `update_author` returns
    the updated row, or None.
  - **Adding or editing a book whose author was deleted meanwhile:** the
    `book_author_author_id_fkey` violation becomes a field error ("An author you chose was
    just deleted from the catalog. Choose the author again."), not a 500.
  - **The confirm step re-checks:** if a book now lists the author, it shows the 409
    explanation instead of claiming there are none.
  - **The "Deleted" message is signed:**
    - the redirect carries an HMAC of the name;
    - a crafted link shows no message.
  - **The API's 409** is a plain Problem with code `author_has_books`, without
    `existing_id`, matching the generated document.
  - **The foreign-key backstop** is covered by a test, and the pragma is removed.
  - **Fewer queries:** the author's books are loaded only when a page is shown again, and
    the delete no longer looks the author up twice.
