# Implementation Plan: Consistent Navigation

**Branch**: `018-navigation-model` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-navigation-model/spec.md`

## Summary

- **Menu**:
  - It becomes two lists: places (My books, Catalog, Authors, Upcoming) and actions (Add
    a book, Import, Accounts).
  - The current place is marked, with author pages under Authors and series and book
    pages under Catalog.
- **Authors page** (`GET /authors`):
  - search, Favorites only, favorites first, "N books · M read", a star per row, and 50
    per page;
  - it takes three queries, reusing spec 017's `among` and `finished_counts`;
  - `/authors/favorites` redirects to it.
- **Upcoming**:
  - My books loses the Upcoming checkbox, and `upcoming=1` redirects to `/upcoming`;
  - Now out moves to the top of Upcoming, with a one-line pointer on My books.
- **Series view** (`GET /catalog/series`): a "Books | Series" switch on the Catalog, and
  a searchable list of series with counts.

Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Jinja2 + HTMX (none new)

**Storage**: PostgreSQL 16+; no schema change planned (an index only if perf needs it, R5)

**Testing**: pytest (integration), Playwright + axe (a11y), perf suite

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**:
- The Authors page and the Series view are under 1 s (p95) at 5,000 books and 1,500
  authors, in three queries or fewer each.
- My books, Upcoming and the Catalog keep their budgets.

**Constraints**:
- Works without JavaScript; HTMX only speeds up search.
- The menu is at most two rows at 360 px.
- No open redirect: the new `/authors` return address is allow-listed (spec 017 R2).

**Scale/Scope**: One family: about 2–10 users and a few thousand books.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | The favorites-first order and the Favorites only filter come from `FavoriteAuthorRepository.author_condition()`, bound to the session user. Read counts come from `ReadingEntryRepository.finished_counts` and `finished_counts_by_series`, and Now out from `list_now_out`, all user-bound. AC-17 tests give another member favorites and finished books and check they never show. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec, Data Ownership. Counts are worked out when a page shows, and nothing is stored. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-19 each get an `ac("018/AC-xx")` test, written failing first. Spec 007, 011 and 017 tests of removed behaviour are rewritten to the new behaviour. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change. If R5 adds an index, it's a reversible migration. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `AuthorsQuery` and `SeriesQuery` validate the new pages' queries. Bad values fall back to the defaults, as `CatalogQuery` does. No JSON API change. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | None stored or sent. |

### Coverage-critical modules (Principle V)

These are already listed and stay at 100%:
- `src/book_tracker/persistence/favorites.py` gains `author_condition`;
- `src/book_tracker/persistence/readings.py` gains `finished_counts_by_series`;
- `src/book_tracker/web/favorites.py` gains `/authors` in `_BACK`.

### New dependencies (Principle VIII)

None.

### Migrations (Principle VI)

- **Schema changes**: none planned. If R5 finds `book_author` has no index starting with
  `author_id`, a reversible migration adds `ix_book_author_author_id`.
- **Destructive changes**: none.

## Project Structure

### Documentation (this feature)

```text
specs/018-navigation-model/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ui-navigation.md
└── tasks.md
```

### Source Code (repository root)

```text
src/book_tracker/persistence/catalog.py      # browse_authors, browse_series
src/book_tracker/persistence/favorites.py    # author_condition()
src/book_tracker/persistence/readings.py     # finished_counts_by_series
src/book_tracker/services/authors.py         # authors_index
src/book_tracker/services/catalog.py         # series_index (or readings.py, beside catalog_view)
src/book_tracker/schemas/catalog.py          # AuthorsQuery, SeriesQuery
src/book_tracker/web/favorites.py            # _BACK accepts /authors
src/book_tracker/web/rendering.py            # ACTIVE_TABS
src/book_tracker/web/routes/authors.py       # GET /authors; /favorites redirect
src/book_tracker/web/routes/catalog.py       # GET /catalog/series
src/book_tracker/web/routes/readings.py      # my_list: upcoming redirect, Now out pointer; upcoming_page: Now out
src/book_tracker/web/templates/base.html                       # the menu
src/book_tracker/web/templates/pages/{authors,catalog_series}.html          # new
src/book_tracker/web/templates/partials/{authors_list,series_list,catalog_switch,no_favorites,now_out_pointer}.html  # new
src/book_tracker/web/templates/pages/{list,upcoming,catalog,author,favorite_authors}.html  # changed; favorite_authors removed
src/book_tracker/web/static/css/app.css
tests/integration/test_navigation.py                           # new
tests/a11y/test_navigation_a11y.py                             # new
tests/perf/test_navigation_perf.py                             # new
tests/ (spec 007, 011, 017 tests of removed behaviour)         # rewritten
```

**Structure Decision**: two new pages in the existing web layer, built on catalog
queries plus the user-bound repositories. Everything else is templates and two
redirects.

## Complexity Tracking

None: every Constitution Check row is Yes.
