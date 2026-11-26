# Tasks: Consistent Navigation (spec 018)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/ui-navigation.md](contracts/ui-navigation.md)

**Tests**: required (Constitution V). Write each test first and see it fail. Tag tests
`@pytest.mark.ac("018/AC-xx")`.

## Phase 1: Setup

- [X] T001 Baseline: main is green at 054b120. Run `uv run pytest -q` on branch
  `018-navigation-model` before any change.

## Phase 2: Foundational (blocks US1 and US3)

- [X] T002 Write failing repository tests in `tests/integration/test_navigation.py`:
  - `FavoriteAuthorRepository.author_condition()` selects only the bound user's
    favorites;
  - `ReadingEntryRepository.finished_counts_by_series(ids)` counts the bound user's
    Finished books per series, ignores other statuses and other members, and returns {}
    for an empty list.
- [X] T003 Implement:
  - `author_condition()` in `src/book_tracker/persistence/favorites.py`;
  - `finished_counts_by_series` in `src/book_tracker/persistence/readings.py`;
  - `AuthorsQuery` and `SeriesQuery` (bad values fall back to the defaults) in
    `src/book_tracker/schemas/catalog.py`.

## Phase 3: User Story 1 – Find any author (Priority: P1) 🎯 MVP

**Goal**: an Authors menu item and page that replaces My favorite authors.
**Independent Test**: open Authors from the menu, search, filter to favorites, star an
author, and open an author's page.

- [X] T004 [US1] Write failing tests in `tests/integration/test_navigation.py` for:
  - AC-01, the menu:
    - two lists, places then actions, in order, with Accounts only for Admins;
    - `aria-current` on the right item for `/`, `/catalog`, `/catalog/series`,
      `/series/<id>`, `/books/<id>`, `/authors`, `/authors/<id>` and `/upcoming`;
  - AC-02: the rows' order (favorites first, then by sort name), the name link,
    "pen name of …", "N books · M read" with singular and plural forms, the star and its
    state, and an author with no books shown as "0 books";
  - AC-03: search on name, sort name and real name, ignoring case; `%` and `_` taken
    literally; HTMX gets only the list; no matches shows "No authors match “…”." with
    Clear search;
  - AC-04: Favorites only, with and without favorites (the spec 017 empty text and
    **Browse the Catalog**). The checkbox carries the HTMX change trigger, and without
    JavaScript **Apply** submits;
  - AC-05: a star posted from `/authors?q=…&favorites=1&page=2` returns to that address
    with `favorited` and `#favorite-notice`, and the notice shows;
  - AC-06: 51 authors give two pages, with Previous and Next keeping `q` and
    `favorites`;
  - AC-07: `/authors/favorites` redirects with 302 to `/authors?favorites=1`, and no
    template still links to `/authors/favorites`;
  - AC-08: "Authors with no books (n)" is on the Authors page and not on My books.
- [X] T005 [US1] Implement:
  - `browse_authors` in `src/book_tracker/persistence/catalog.py`;
  - `authors_index` in `src/book_tracker/services/authors.py`;
  - `GET /authors` and the `/favorites` redirect in
    `src/book_tracker/web/routes/authors.py`;
  - `/authors` in `_BACK` in `src/book_tracker/web/favorites.py`;
  - the templates `pages/authors.html`, `partials/authors_list.html` and
    `partials/no_favorites.html`;
  - the menu in `base.html`, with `ACTIVE_TABS` in `src/book_tracker/web/rendering.py`.

  Delete `pages/favorite_authors.html`. Change links to `/authors/favorites` in
  `pages/author.html` and `pages/list.html`. Update the old tests that use the removed
  page (`tests/integration/test_favorite_authors.py`, `test_favorite_shortcuts.py`,
  `test_flow_fixes.py`, and `tests/a11y/test_author_a11y.py`,
  `test_favorite_shortcuts_a11y.py`, `test_layout_003.py`) to the new address and
  behaviour. A test keeps its old `ac` tag only where that criterion still holds (spec
  018, "Amended specs"). A test of the removed page is re-tagged `018/AC-xx`.

## Phase 4: User Story 2 – One place for what's coming and what's new (Priority: P1)

**Goal**: Upcoming is the only place for upcoming and newly-out books.
**Independent Test**: one of my books out last week, one of mine coming, and a catalog
book coming: Upcoming shows all three in order. My books has no checkbox and shows the
pointer.

- [X] T006 [US2] Write failing tests in `tests/integration/test_navigation.py` for:
  - AC-09: My books has no `upcoming` checkbox, no "My favorite authors" link, and keeps
    the Author filter's favorites choice;
  - AC-10: `/?upcoming=1` (with other filters too) redirects with 302 to `/upcoming`;
  - AC-11 and AC-13: Upcoming shows `#now-out` first, then On my list, then Also coming;
    there's no Now out section without such books; another member's Now out books never
    show;
  - AC-12: the My books line ("1 book you want to read is now out" / "2 books you want to
    read are now out"), linking to
    `/upcoming#now-out`, nothing when there are none, and no Now out box.
- [X] T007 [US2] Implement:
  - in `src/book_tracker/web/routes/readings.py`: `my_list` redirects on `upcoming=1`,
    drops the upcoming filter, and passes the Now out count; `upcoming_page` adds
    `now_out`;
  - the templates `pages/list.html`, `pages/upcoming.html` and
    `partials/now_out_pointer.html`.

  Rewrite the spec 007 tests of the removed filter and box
  (`tests/integration/test_upcoming_books.py`, `tests/a11y/test_upcoming_a11y.py`,
  `tests/a11y/test_layout_003.py`, `tests/integration/test_book_page.py`, and the Now
  out case in `tests/perf/test_list_performance.py`) to the new places.
  - **Keep the old tag** where the criterion still holds: 007/AC-14 to AC-18 (the Now out
    rules, now checked on Upcoming), 007/AC-12 and AC-13, and the JSON API's 007/AC-10 in
    `tests/contract/test_upcoming_contract.py`.
  - **Re-tag `018/AC-09`, `018/AC-10` or `018/AC-12`** the tests of the removed checkbox
    and box (007/AC-10's My books part, AC-11).
  - `tests/unit/test_upcoming.py` (the date rules) stays.

## Phase 5: User Story 3 – Browse series from the Catalog (Priority: P2)

**Goal**: a Series view in the Catalog.
**Independent Test**: switch to Series, search, and open a series.

- [X] T008 [US3] Write failing tests in `tests/integration/test_navigation.py` for:
  - AC-14: the "Books | Series" switch on both views, with `aria-current`;
  - AC-15: the rows by name, the name link, "N books · M read", and a stories-only
    series shown as "0 books";
  - AC-16: search (with `%` taken literally), no matches, 51 series giving two pages,
    and HTMX getting only the list.
- [X] T009 [US3] Implement:
  - `browse_series` in `src/book_tracker/persistence/catalog.py`;
  - `series_index` in the services;
  - `GET /catalog/series` in `src/book_tracker/web/routes/catalog.py`;
  - the templates `pages/catalog_series.html`, `partials/series_list.html` and
    `partials/catalog_switch.html`, with the switch included in `pages/catalog.html`.

## Phase 6: User Story 4 – Private, accessible and fast (Priority: P2)

- [X] T010 [US4] Write failing AC-17 tests in `tests/integration/test_navigation.py`.
  Another member's favorites and finished books never change:
  - my stars, my favorites-first order, or the Favorites only list;
  - "M read" on the Authors page and in the Series view;
  - Now out.
- [X] T011 [P] [US4] Write `tests/a11y/test_navigation_a11y.py` for AC-18:
  - the menu as a member and as an Admin at every spec 003 width, at most two rows at
    360 px;
  - the Authors page with results, with no matches, and with Favorites only empty;
  - the Series view;
  - Upcoming with all three sections;
  - My books with the Now out line.

  Check no sideways scroll, 44 px targets, axe, and that search works with JavaScript
  off. SC-001 is a keyboard journey from any page: menu → Authors → type a name → the
  author's page, in three steps. Fix whatever fails in `src/book_tracker/web/static/css/app.css`.
- [X] T012 [P] [US4] Write `tests/perf/test_navigation_perf.py` for AC-19:
  - the Authors page (the first page, a search, Favorites only), the Series view, and
    Upcoming with Now out;
  - each under 1 s p95 at 5,000 books and 1,500 authors.

  If the Authors page is slow, check `book_author`'s indexes and add a reversible
  migration (research R5). (Not needed: every page measured under 0.25 s p95.)

## Phase 7: Polish

- [X] T013 The spec 007, 011 and 017 acceptance criteria were marked during analysis
  (spec 018, "Amended specs"). Check they still match what was built. Add dated notes
  pointing to spec 018 to the spec 007, 010, 011 and 017 contracts (`specs/007-upcoming-books/contracts/`, `specs/010-catalog-page/contracts/`,
  `specs/011-author-page/contracts/ui-authors.md`,
  `specs/017-favorite-author-shortcuts/contracts/ui-favorites.md`), and update
  `specs/001-family-reading-list/contracts/ui-routes.md`.
- [X] T014 Run every gate (ruff, mypy, pytest with coverage, check_coverage, a11y, perf,
  pip-audit, the OpenAPI export check), then the quickstart.

## Dependencies

- T001, then Foundational (T002 → T003).
- **US1** (T004 → T005) carries the menu, which every later story's `aria-current`
  checks rely on.
- **US2** is independent of US1's Authors page, but `list.html` is edited by both. Do it
  after US1.
- **US3** needs T003 (`SeriesQuery`, `finished_counts_by_series`) and US1's menu.
- **US4** needs US1–US3.
- Polish comes last.

**Parallel**: T011 and T012 touch different files.

## Implementation strategy

- **MVP**: US1, the Authors menu item and page. It answers the user's first question on
  its own.
- **US2**: removes the Upcoming duplication, the second question.
- **US3**: gives series a front door.
- **US4**: hardens privacy, layout and speed.
