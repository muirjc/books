# Tasks: Catalog Page (spec 010)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/ui-catalog.md](contracts/ui-catalog.md)

**Tests**: required (Constitution V). Each test is written first and seen failing. Tests
are tagged `@pytest.mark.ac("010/AC-xx")`.

## Phase 1: Setup

- [X] T001 Add a `catalog_books` helper to `tests/integration/test_catalog_page.py`. It
  seeds books with authors, series, numbers, release dates, ISBNs and stories through
  `Factory`, plus a second member with their own entries.

## Phase 2: Foundational

- [X] T002 Lift `search_books`' match conditions into `_book_matches(q, *, series)` in
  `src/book_tracker/persistence/catalog.py`, without changing type-ahead behaviour. The
  existing type-ahead tests must stay green (research R2).
- [X] T003 Add `ReadingEntryRepository.not_on_list()` in
  `src/book_tracker/persistence/readings.py` (research R3), with a test in
  `tests/integration/test_readings_repository.py` that it excludes only the bound user's
  books.

## Phase 3: User Story 1 - Browse the whole family catalog (P1)

**Independent test**: 120 books; page 1 by title, the count, the links, page 3, signed out
refused.

- [X] T004 [US1] Write failing tests for AC-01 to AC-07 in
  `tests/integration/test_catalog_page.py`: the nav link and its `aria-current`; the
  sign-in redirect and the forced password change; the count and title order; the Coming
  label; the title and series links; paging, a page past the end and an invalid page; the
  empty catalog.
- [X] T005 [US1] Add `browse_books` in `src/book_tracker/persistence/catalog.py`: count,
  clamp, page, with the title sort only for now (research R1).
- [X] T006 [US1] Add `CatalogRow`, `CatalogPage` and `catalog_view` in
  `src/book_tracker/services/readings.py`, with the markers from `list_books`.
- [X] T007 [US1] Add `GET /catalog` in `src/book_tracker/web/routes/catalog.py`, the
  templates `pages/catalog.html` and `partials/catalog_list.html`, and the nav link in
  `templates/base.html`.

## Phase 4: User Story 2 - Add a catalog book to my list (P1)

- [X] T008 [US2] Write failing tests for AC-08 to AC-10 in
  `tests/integration/test_catalog_page.py`:
  - **On my list** links to my entry;
  - **Add to my list** goes to `/books/add?book=`, with its accessible name;
  - another member's Finished, rated and noted entry leaves no trace in the response.
- [X] T009 [US2] Render the row actions in `partials/catalog_list.html`.

## Phase 5: User Story 3 - Search, sort and filter (P2)

- [X] T010 [US3] Write failing tests for AC-11 to AC-16 in
  `tests/integration/test_catalog_page.py`:
  - search by title, author, real name, series and story, plus pattern characters;
  - ISBN first;
  - each sort, and an unknown sort;
  - **Not on my list**, which never reflects another member's entries;
  - no match;
  - the HTMX partial and the kept parameters in the paging links.
- [X] T011 [US3] Add the search, the sorts and `exclude` to `browse_books`; parse `q`,
  `sort`, `not_mine` and `page` in the route; add the form to `pages/catalog.html`.

## Phase 6: Polish & cross-cutting

- [X] T012 [P] Add `tests/a11y/test_catalog_a11y.py`:
  - axe at phone, tablet and desktop widths;
  - a keyboard journey (search, sort, page, Add to my list);
  - no-JS submit;
  - the fold on a phone;
  - every target ≥ 24 px.

  Then add the `.catalog-list` CSS in `src/book_tracker/web/static/css/app.css`.
- [X] T013 Run `tests/a11y/test_layout_003.py` for the nav on one line with the new link,
  and tighten the nav CSS only if it fails (research R5).
- [X] T014 [P] Add `test_catalog_page_under_one_second` to
  `tests/perf/test_list_performance.py`: the plain list, a search, each sort, the filter
  and a late page (SC-001).
- [X] T015 [P] Amend `specs/001-family-reading-list/contracts/ui-routes.md` with the
  `/catalog` row and the navigation.
- [X] T016 Run all the gates: ruff, mypy, pytest with coverage, `check_coverage`, a11y, perf
  and pip-audit.

## Dependencies

T001 → T002/T003 → US1 (T004–T007) → US2 (T008–T009) → US3 (T010–T011) → polish. US2 and
US3 both build on US1's page.

## Implementation notes

- **T002**:
  - `_book_matches` keeps the type-ahead's fields (`series=False`).
  - `first_author_key` moved to `persistence/catalog.py`, so My books' Author sort and the
    Catalog page share it.
  - `services.catalog.as_isbn` became public, for the Catalog service.
- **T012**: the pagination links (a `nav`) were 24 px high, below the 44 px rule for nav
  links. `.pagination a` now has the target size. This fixes My books' pagination too: the
  same gap was there, but no test had reached a second page at phone width.
- **T013**: the spec 003 header tests pass with the new **Catalog** link, so the nav CSS is
  unchanged.
- **T014**: every case has p95 at or under about 125 ms, so no index is needed (research R6).
