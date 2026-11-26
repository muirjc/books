# Tasks: Favorite Author Shortcuts (spec 017)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/ui-favorites.md](contracts/ui-favorites.md)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("017/AC-xx")`.

## Phase 1: Setup

- [X] T001 Baseline: main is green at 13c40cc. Run `uv run pytest -q` on branch
  `017-favorite-author-shortcuts` before any change.

## Phase 2: Foundational (blocks US1 and US3)

- [X] T002 Write failing repository tests in `tests/integration/test_favorite_shortcuts.py`:
  - `FavoriteAuthorRepository.among(author_ids)` returns only the bound user's favorites
    among the given ids, and an empty set for an empty list;
  - `ReadingEntryRepository.finished_counts(author_ids)` counts the bound user's Finished
    books per author. It ignores Reading and Want to read, another member's entries, and
    story authors. A re-read counts once.
- [X] T003 Implement `among` in `src/book_tracker/persistence/favorites.py` and
  `finished_counts` in `src/book_tracker/persistence/readings.py` (research R3). Each is
  one query. Add the service wrappers `favorite_ids` and `finish_offers(db, user_id,
  book_id)` in `src/book_tracker/services/authors.py`:
  - `finish_offers` returns `[(Author, count)]`, but only when my entry for the book is
    Finished;
  - each author it returns is one of the book's authors, isn't my favorite, and has a
    count of 2 or more.
- [X] T004 Add `FavoriteNoticeQuery` to `src/book_tracker/schemas/catalog.py`: optional
  UUIDs `finished`, `favorited` and `unfavorited`, where an invalid value becomes None
  (Constitution VII). Create `src/book_tracker/web/favorites.py` (research R2), reading
  those keys only through that model:
  - `after_favorite(db, auth, author_id, back, kind) -> str`: the return-address
    allow-list, the my-own-entry check through `ReadingEntryRepository.get`, dropping the
    one-time keys, and adding `favorited` / `unfavorited` with `#favorite-notice`. The
    fallback is `/authors/<id>?msg=…`.
  - `notice(request, db) -> tuple[str, Author] | None`.
  - `offer(request, db, auth) -> list[tuple[Author, int]]`: reads `finished=<book>`.

  Add the file to `scripts/check_coverage.py` (100%). Add `finished`, `favorited` and
  `unfavorited` to `DROPPED_KEYS` in `src/book_tracker/web/quick.py`.

## Phase 3: User Story 1 – Star an author where I'm looking at their book (P1) 🎯 MVP

**Goal**: one-tap stars on the book page and my entry page.
**Independent Test**: star and unstar an author of a two-author book on both pages.

- [X] T005 [US1] Write failing tests in `tests/integration/test_favorite_shortcuts.py` for:
  - AC-01: the book page byline has a star form per author after the author link (☆ when
    not a favorite, ★ when one), and the name still links to `/authors/<id>`;
  - AC-02: the entry page's "All books by" lines have the same forms;
  - AC-03: posting `favorite=yes` with `back=/books/<id>` redirects to
    `/books/<id>?favorited=<author>#favorite-notice`. The page then shows "Added <author>
    to your favorite authors." and ★. The same for removing, and from `/entries/<id>`;
  - AC-04: the hidden button text "Add <author> to my favorite authors" / "Remove <author>
    from my favorite authors", and a decorative star (`aria-hidden`);
  - AC-05: accepted and refused `back` values:
    - another site, `//evil`, another member's entry, an unknown entry and
      `/catalog/books/<id>/edit` fall back to `/authors/<id>?msg=…`;
    - with no `back`, the spec 011 behaviour is unchanged;
    - an unknown author is 404;
    - the query on an accepted `back` is kept, minus one-time keys;
    - an invalid `favorited` / `unfavorited` value shows the page without a notice;
  - edge cases:
    - a pen-name author's star favorites the pen name;
    - a star post for an author who was removed from the book meanwhile still changes
      the favorite and returns to the book page.
- [X] T006 [US1] Implement:
  - `FavoriteForm.back` (optional, at most 2,000 characters) in
    `src/book_tracker/schemas/catalog.py`;
  - `set_favorite` in `src/book_tracker/web/routes/authors.py`, using
    `favorites.after_favorite`;
  - a `star_button(author, is_favorite, back, csrf_token)` macro in
    `src/book_tracker/web/templates/macros.html`;
  - `partials/favorite_notice.html` (`id="favorite-notice"`, `role="status"`);
  - the stars and notice in `pages/book.html` (byline) and `pages/entry.html` (More);
  - `favorite_ids` and `favorites.notice` in the book page and entry page contexts in
    `src/book_tracker/web/routes/readings.py`;
  - `.star-button` and the nowrap author-and-star pair in
    `src/book_tracker/web/static/css/app.css` (research R6).

## Phase 4: User Story 2 – A way forward from no favorites (P2)

**Goal**: the empty My favorite authors page leads somewhere.
**Independent Test**: as a member with no favorites, open the page and follow the link.

- [X] T007 [US2] Write a failing AC-06 test in `tests/integration/test_favorite_shortcuts.py`:
  - the empty page has the new text and a **Browse the Catalog** link to `/catalog`;
  - with favorites, the page is unchanged.
- [X] T008 [US2] Update `src/book_tracker/web/templates/pages/favorite_authors.html`
  (research R5).

## Phase 5: User Story 3 – Offer an author after a second finished book (P2)

**Goal**: a finishing save offers authors I've now finished twice.
**Independent Test**: finish a second book by a non-favorite author, then accept the
offer.

- [X] T009 [US3] Write failing tests in `tests/integration/test_favorite_shortcuts.py` for:
  - AC-07: changing my entry to Finished redirects with `finished=<book>`, and the entry
    page shows "You've finished 2 books by <author>." with the button;
  - AC-08: a two-author book where both qualify gives two buttons, and only qualifying
    authors are named;
  - AC-09, no offer:
    - for a first finished book;
    - for a favorite;
    - when saving an already-finished entry;
    - when changing to Reading;
    - when opening the entry page without `finished`;
    - for a `finished=` naming a book that isn't finished on my list;
    - for an invalid `finished` (validated by `FavoriteNoticeQuery`, no error page);
    - after a re-read is finished again (the count stays 1 for that book);
    - and a reload of the same address shows the offer again only while it's still
      true;
  - AC-10: accepting posts the rendered offer form (with its CSRF token, and `back` = the
    current page) and returns with the notice. A post without the token is refused. The
    accepted author is no longer offered, and another qualifying author still is;
  - AC-11: ignoring stores nothing, and finishing a third book offers again;
  - AC-12: Add a book with status Finished shows the offer on each landing page: My books
    (`/?msg=added&finished=…`), a series page (`from_series`), Add another
    (`then=another`) and the `stories_not_added` entry page. The HTMX list partial has no
    offer, and an import never adds `finished`.
- [X] T010 [US3] Implement:
  - adding `finished=<book_id>` on the finishing redirects in `add_book` and
    `update_entry` in `src/book_tracker/web/routes/readings.py` (research R4), keeping
    `anthology.with_stories`;
  - `partials/favorite_offer.html`, one form per author, each with the CSRF field;
  - `favorites.offer` and `favorites.notice` in the contexts and templates of
    `pages/entry.html`, `pages/list.html`, `pages/series.html` and `pages/add_book.html`
    (only with `after=`).

## Phase 6: User Story 4 – Private, accessible and fast (P2)

- [X] T011 [US4] Write failing AC-13 tests in `tests/integration/test_favorite_shortcuts.py`:
  another member's favorite never fills my star, and their finished books never count
  towards my offer.
- [X] T012 [P] [US4] Write `tests/a11y/test_favorite_shortcuts_a11y.py` for AC-14, at every
  spec 003 width:
  - the book page with two authors (one starred), the entry page More section, the empty
    favorites page, and the entry page with an offer;
  - no sideways scroll, 44 px stars and offer buttons, and axe;
  - Tab reaches each star right after its author link;
  - a star and its author name never wrap apart;
  - a JavaScript-off star tap.

  Fix whatever fails in `src/book_tracker/web/static/css/app.css`.
- [X] T013 [P] [US4] Add AC-15 perf tests in `tests/perf/`, each under 1 s p95 at 5,000
  books:
  - the book page and the entry page with stars;
  - a finishing entry save followed by its landing page with an offer.

## Phase 7: Polish

- [X] T014 Update `specs/001-family-reading-list/contracts/ui-routes.md` (the favorite route's
  `back`, the `finished` / `favorited` keys). In
  `specs/011-author-page/contracts/ui-authors.md`, point the empty-page text at spec 017.
- [X] T015 Run every gate (ruff, mypy, pytest with coverage, check_coverage, a11y, perf,
  pip-audit, the OpenAPI export check), then the quickstart.

## Dependencies

- T001, then Foundational (T002 → T003, T004).
- **US1** needs T003 (`favorite_ids`) and T004 (`after_favorite`, `notice`).
- **US3** needs T003 (`finish_offers`), T004 (`offer`) and US1's notice partial and
  `back` handling, because accepting the offer uses them.
- **US2** is independent and can go any time after T001.
- **US4** needs US1–US3.
- Polish comes last.

**Parallel**: T007 and T008 (US2) can run alongside US1. T012 and T013 touch different
files.

## Implementation strategy

- **MVP**: US1, the stars on the book and entry pages. It's usable on its own.
- **US2**: a one-template change.
- **US3**: adds the offer, which reuses US1's route and notice.
- **US4**: hardens privacy, layout and speed.

## PR #42 review (7 findings, all fixed with failing tests first)

1. **Sideways scroll on a phone (important):** each name-and-star pair is now an inline
   flex box. The pair moves to a new line as one, and a long name wraps inside it. The
   a11y test adds a 45-character author name at every width.
2. **Notice missing after some returns:** an author page as `back` now gets the spec 011
   `?msg=` address. My books, series pages and Add another always show the notice.
3. **`stories_not_added` was dropped:** that warning is kept; other `msg` codes are still
   dropped.
4. **A star lost the other offers:** stars post the page's own address, keeping
   `finished`.
5. **Unencoded query characters:** the offer's and stars' `back` is re-encoded
   (`favorites.page_back`), so `,` `(` `!` are accepted.
6. **False notices:** "Added" / "Removed" show only when they match my favorites now.
7. **The book page worked out an offer it never shows:** it skips the offer now. A test
   counts its SQL statements with and without `finished`.

Also: my entry page's More list uses `link-list` (44 px links). With stars on its lines,
axe flagged the Edit author links.

## Notes from implementation

- **Tests first:** the T002, T005, T007, T009 and T011 tests were written first.
  - 17 of 30 failed, as expected.
  - The 13 that passed guard things that already held: refused return addresses (9
    cases), no `back`, an invalid notice value, and no offer.
  - The a11y and perf tests were written after the pages existed.
- **The byline is now a `div`.** A `<form>` can't sit inside a `<p>`: the browser closes
  the paragraph, so the star broke the byline's layout. The first a11y run caught it.
  `.book-byline` gets the paragraph margin.
- **Pen names:** the star comes straight after the name, before "(pen name of …)". The
  name and star never wrap apart, and the note can wrap (research R1, R6).
- **`after` and `finished` are kept** when a favorite returns to a page: they say which
  Add another page and which offer this is. All other one-time keys are dropped.
- **Older tests:** 8 integration and 5 a11y assertions compared exact redirect addresses.
  They now strip `finished=` with `tests.conftest.without_finished`. `after_id` in
  `test_add_another.py` accepts it.
- **Perf at 5,000 books (p95):**
  - book page with stars: 23 ms;
  - entry page with stars and the offer: 23 ms;
  - finishing save plus its landing page: 54 ms.
- **Imports (AC-12)** are untouched. Their routes never build a `finished` address.
- **Gates:**
  - 1,029 tests passed, and 95 a11y and perf tests passed;
  - ruff and mypy are clean;
  - all 9 coverage-critical modules are at 100%, including `web/favorites.py`;
  - pip-audit is clean;
  - the OpenAPI export is unchanged.
