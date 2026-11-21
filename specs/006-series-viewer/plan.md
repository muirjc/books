# Implementation Plan: Series Viewer

**Branch**: `006-series-viewer` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-series-viewer/spec.md`

## Summary

`GET /series/{id}` keeps its URL, and now shows the whole series:

- **Reads:** two reads, both existing:
  - the catalog books in the series (`catalog.list_series_books`, added in books-cay);
  - the viewer's own entries in the series (`ReadingEntryRepository(db, user_id).list_series`,
    owner-filtered).
- **Rows:** a pure function `series_rows(books, entries)` merges them into rows (book with my
  entry, book not on my list, gap) and a finished count. It's unit-tested for ordering,
  gaps and collapsing.
- **Add links** go to Add a book with new query parameters:
  - `?book=<book_id>&from_series=<series_id>`: that catalog book chosen, status Want to
    read;
  - `?series=<series_id>&number=<n>&from_series=<series_id>`: series and number filled in.
- **Return:** a hidden `from_series` field carries the return through error, conflict and
  new-name pages. On a successful **Add to my list** (`then=list`), the redirect is
  `303 /series/<id>?added=<entry_id>`, and the series page confirms the book through the
  owner-filtered `get_entry` (the spec 004 pattern). `then=another` keeps spec 004's
  redirect.

No schema, JSON API or dependency changes. See [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX, httpx

**Storage**: PostgreSQL 16+ (no change)

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL); Playwright (Chromium) +
axe-core for the `a11y` marker; the `perf` marker for SC-002

**Target Platform**: Single container image (Linux); Safari and Chrome, latest two versions

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: SC-002: under 1 s at p95 for a 100-book series in the 5,000-book perf
dataset. Two indexed queries: `book_series_id_idx`, and the entry query filtered by user
and joined on book.

**Constraints**:
- Works without JavaScript: links and plain forms only.
- WCAG 2.2 AA; spec 003 layouts.
- Principle I: no query reads another member's entries.
- The return address is built from a UUID, never echoed (FR-007).

**Scale/Scope**:
- **Services:** `services/readings.py` (`series_view` returns rows, plus a pure `series_rows`).
- **Forms:** `web/forms.py` (`from_series` field; `book_start_form` and `series_start_form`).
- **Routes:** `web/routes/readings.py` (`series_page` `?added=`; `add_book_form`
  `?book=&series=&number=&from_series=`; the `add_book` redirect).
- **Templates and CSS:** `pages/series.html` and `pages/add_book.html`, plus CSS for the
  series rows.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | Entries come only from `ReadingEntryRepository(db, user_id)`, which filters by owner in `persistence/readings.py`. `?added=` uses `service.get_entry` (owner-filtered); another member's id shows no confirmation. Tests: Ben's entries never change Alice's rows or counts, and Ben's entry id in `?added=` shows nothing. `user_id` comes from the session only. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec Data Ownership table; nothing stored. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI involvement. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-19 each get a `006/AC-xx` test, seen failing first. AC-05, AC-10 and AC-13 pin existing behaviour (guards). |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change. Series-number uniqueness stays in the DB, and a gap add that races another member gets today's conflict. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `book`, `series` and `from_series` are parsed as UUIDs, and `number` with the existing series-number validator; invalid values are ignored. No JSON API change. UI contract in `contracts/ui-series-viewer.md`. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Nothing stored or sent. The entry id in `?added=` is the member's own. |

### Coverage-critical modules (Principle V)

- `persistence/readings.py` is unchanged (its `list_series` is reused). `series_rows` is new,
  pure and fully unit-tested.

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| None | | | |

### Migrations (Principle VI)

- **Schema changes**: None
- **Destructive changes**: None

## Project Structure

### Documentation (this feature)

```text
specs/006-series-viewer/
├── plan.md                    # This file
├── research.md                # Decisions R1–R6
├── data-model.md              # No data changes; the row model and start forms
├── quickstart.md              # Checks by hand and the test commands
├── contracts/
│   └── ui-series-viewer.md    # GET /series/{id}, /books/add parameters, markup
└── tasks.md                   # /speckit-tasks
```

### Source Code (repository root)

```text
src/book_tracker/
├── services/readings.py            # SeriesRow, series_rows(), series_view() → rows
└── web/
    ├── forms.py                    # from_series; book_start_form(); series_start_form()
    ├── routes/readings.py          # series_page ?added=; add_book_form params; redirect
    ├── static/css/app.css          # .series-rows layout (phone stacks)
    └── templates/pages/
        ├── series.html             # rows, progress, gap rows, Add links, confirmation
        └── add_book.html           # hidden from_series

tests/
├── unit/test_series_rows.py                 # ordering, gaps, collapsing, counts
├── integration/test_series_viewer.py        # page, privacy, add flows, return, guards
├── a11y/test_series_viewer_a11y.py          # widths, targets, axe, reading order, no-JS
└── perf/test_list_performance.py           # + series page budget (SC-002)
```

**Structure Decision**: the existing single deployable. Row logic goes in the service layer
as a pure function; the web layer only renders it.

## Complexity Tracking

No Constitution Check row is "No"; nothing to justify.
