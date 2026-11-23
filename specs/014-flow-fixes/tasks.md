# Tasks: Flow Fixes (spec 014)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[contracts/](contracts/)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("014/AC-xx")`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Baseline: on `014-flow-fixes`, check that the suite, ruff and mypy are green.

## Phase 2: Foundational

- [X] T002 Write a failing test, then add `entry_for_book(db, user_id, book_id)` to
  `src/book_tracker/services/readings.py` (via `ReadingEntryRepository`). Another member's
  entry is never returned.

## Phase 3: User Story 1 – Stories from an entry page (P1) 🎯 MVP

- [X] T003 [US1] Write failing tests in `tests/integration/test_flow_fixes.py` for
  AC-01 to AC-05:
  - the entry page's Stories section, with and without stories;
  - the new `stories_not_added` text, with Add a story on the page;
  - **Add and add another**: saves, then a fresh form with the "Added …" notice, autofocus
    on the title, and the book's series and authors;
  - `from=entry:` returns on save and cancel, and is ignored when it is another member's,
    malformed or for another book;
  - the Edit book jump link and hint.
- [X] T004 [US1] Implement:
  - `src/book_tracker/web/templates/pages/entry.html`: the Stories section always shows;
  - `src/book_tracker/web/routes/stories.py`: `from`, `then=another` and `added`;
  - `add_story.html`: the second button and the hidden `from`;
  - `edit_book.html`: the jump link and hint;
  - the message text in `src/book_tracker/web/routes/readings.py`.

## Phase 4: User Story 2 – Back links and navigation (P1)

- [X] T005 [US2] Write failing tests for:
  - AC-06 to AC-09: the back links on Edit book, Summary, Edit series and Edit story,
    including another member's entry (no link to it) and `from=book:`;
  - AC-10: walk every page and check `aria-current`, and the "Import" label;
  - AC-11: the Catalog link on Books added.
- [X] T006 [US2] Implement:
  - in `src/book_tracker/web/routes/catalog.py`, `stories.py`, `authors.py`,
    `readings.py` and `imports.py`: `active` values, and the entry lookups for back links;
  - the templates: `edit_book`, `summary`, `edit_series`, `edit_story`,
    `book_stories.html` (`from=book:` on edit links), `import_summary` and `base.html`;
  - `.back-link` styles.

## Phase 5: User Story 3 – Quicker ways to add (P2)

- [X] T007 [US3] Write failing tests for:
  - AC-12: `SeriesView.next_number` (unit, in `tests/unit/test_series_rows.py`): stories
    count, a fraction rounds down, None at 999 or with nothing numbered. The series page
    row and its link;
  - AC-13: the collection link, with the box ticked and the series filled in on the form;
  - AC-14: the author link and the `author=` prefill, with an unknown or malformed id
    ignored.
- [X] T008 [US3] Implement:
  - `next_number` in `src/book_tracker/services/readings.py`;
  - `series.html` and `author.html`;
  - `author_start_form` in `src/book_tracker/web/forms.py`, and the `anthology` / `author`
    values in `add_book_form`.

## Phase 6: User Story 4 – Account safety (P2)

- [X] T009 [US4] Write failing tests in `tests/integration/test_flow_fixes_admin.py` for:
  - AC-15: the Change password link for a member and for an admin;
  - AC-16: Deactivate and Make Admin show a confirmation that changes nothing; Confirm
    applies it; Cancel goes back; Reactivate and Make Member are one step; a refused
    action shows today's error after Confirm;
  - AC-17: the reset confirmation without the password in its text; invalid passwords get
    today's 422; Confirm resets.
- [X] T010 [US4] Implement:
  - in `src/book_tracker/web/routes/admin.py`, the confirm step;
  - `src/book_tracker/web/templates/admin/confirm_action.html`;
  - `base.html`: Change password.

## Phase 7: User Story 5 – Long pages (P3)

- [X] T011 [US5] Write failing tests for:
  - AC-18: the favorites link right after the Author field, inside `#filter-extra`;
  - AC-19: the entry page's jump links.

  Implement them in `list.html` and `entry.html`, with `.jump-links` styles.

## Phase 8: User Story 6 – Usable everywhere (P2)

- [X] T012 [US6] Write `tests/a11y/test_flow_fixes_a11y.py` for AC-20 and AC-21:
  - every changed page at every spec 003 width, with axe;
  - JavaScript off: add two stories from an entry page with Add and add another; confirm a
    Deactivate; follow the series page's Add #next.

  Fix whatever fails.

## Phase 9: Polish

- [X] T013 Update `specs/001-family-reading-list/contracts/ui-routes.md`.
- [X] T014 Run every gate (ruff, mypy, the full suite with coverage, critical modules,
  a11y, perf, pip-audit), then work through [quickstart.md](quickstart.md).

## Notes from implementation

- **Tests first:** every test was written before its code and seen failing. The exceptions:
  - four "ignore a foreign `from`" cases already matched today's behaviour;
  - the Change password link and the one-step Reactivate and Make Member;
  - both a11y tests, which passed when first run.
- **Navigation:** `render()` derives `active` from the template name (`ACTIVE_TABS` in
  `web/rendering.py`) unless a route sets it. This replaces editing every route.
- **Old tests updated** for intended changes:
  - the spec 013 AC-20 message;
  - the series rows now end with Add #next (before books with no number);
  - Edit book's story links carry `?from=book:`;
  - an entry page always has a Stories section;
  - admin Deactivate, Make Admin and Reset password now post `confirm=yes`.
- **Layout:** the favorites link sits inside the Author field. As its own item, it wrapped
  the laptop filter row (spec 003 AC test).
- **Accounts:** `services/accounts.get_account` was added for the confirmation page, and is
  covered to 100%.
- **Gates:** 943 passed; a11y and perf 78; ruff and mypy clean; 8 critical modules at 100%;
  pip-audit clean.

## Dependencies

- T002 comes before US1 and US2.
- US1 and US2 touch some of the same templates, so do them in order.
- US3, US4 and US5 are independent of each other.
- US6 and Polish come last.
