# Implementation Plan: Catalog Page

**Branch**: `010-catalog-page` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

## Summary

Add a **Catalog** page at `/catalog`, linked from the main navigation. It lists every
catalog book, 50 per page, and offers search, sort and a **Not on my list** filter. It works
without JavaScript and updates in place with HTMX, as My books does. Each row shows **On my
list** (a link to the viewer's entry) or **Add to my list** (`/books/add?book=<id>`, spec
006).

- **Persistence**:
  - `catalog.browse_books` pages, sorts and searches catalog books. It shares its matching
    with `search_books` (research R1, R2).
  - The **Not on my list** filter is a condition built by the user-bound
    `ReadingEntryRepository` (research R3).
  - The on-my-list markers come from the existing user-bound `list_books`.
- **Service**: `readings.catalog_view` puts the page together as `CatalogPage` rows of
  (book, my entry or none).
- **Web**:
  - `GET /catalog`, which returns the full page, or for HTMX just the list;
  - `pages/catalog.html` and `partials/catalog_list.html`;
  - a nav link, and CSS for the row layout (research R4, R5).
- **No migration, no API change.**

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Jinja2 + HTMX (no new dependency)

**Storage**: PostgreSQL 16+. No schema change (research R6).

**Testing**:
- pytest integration and unit tests;
- Playwright with axe (`a11y`), including the spec 003 layout checks;
- `perf`, using the existing 5,000-book seed.

**Performance Goals**: SC-001, p95 under 1 s. The page makes at most three queries: a
count, a page of 50 books (authors and series loaded by selectin), and my entries for those
50.

**Constraints**:
- works without JavaScript;
- WCAG 2.2 AA;
- spec 003 layouts, including the nav on one line at tablet and laptop widths;
- Principle I: only the viewer's entries are read.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | The page reads entries only through `ReadingEntryRepository`, which is bound to the session user: `list_books` for the markers, and the new `not_on_list()` condition for the filter. Cross-user tests check that another member's entry never shows **On my list**, never changes the filter, and never puts their status, rating or notes in the response (AC-10, AC-14). |
| II | Catalog vs personal data placement is stated; no duplication | Yes | The page only reads: catalog books, plus the viewer's own entries (spec Data Ownership). Nothing is stored. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-16 each get a `010/AC-xx` test, seen failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No new rules or migration. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | No JSON API change. The page's query parameters are checked by hand and fall back to defaults, as on My books (`q` cut to 200 characters, sort from a fixed set, page a positive integer, `not_mine` only "1"). |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | None stored or sent. |

### Coverage-critical modules

The list is unchanged. `persistence/readings.py` is already on it and gains `not_on_list`,
which needs 100% coverage there. `persistence/catalog.py` (`browse_books`) isn't on the
list, but its new code is still covered by the integration tests.

## Project Structure

```text
specs/010-catalog-page/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md
├── checklists/requirements.md
└── contracts/ui-catalog.md

src/book_tracker/
├── persistence/catalog.py        # _book_matches (shared), browse_books, CATALOG_SORTS
├── persistence/readings.py       # ReadingEntryRepository.not_on_list()
├── services/readings.py          # CatalogRow, CatalogPage, catalog_view
└── web/
    ├── routes/catalog.py         # GET /catalog
    ├── templates/base.html       # nav link
    ├── templates/pages/catalog.html, partials/catalog_list.html
    └── static/css/app.css        # .catalog-list rows

tests/
├── integration/test_catalog_page.py
├── unit/ (none needed; parameter parsing is covered through the route)
├── a11y/test_catalog_a11y.py
└── perf/test_list_performance.py (catalog page budgets)
```

## Complexity Tracking

None.
