# Implementation Plan: Upcoming Books

**Branch**: `007-upcoming-books` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-upcoming-books/spec.md`

## Summary

- **Columns (migration `0003_upcoming_books`):**
  - `book.release_date DATE NULL` on the catalog, with a partial index;
  - `reading_entry.pre_ordered BOOLEAN NOT NULL DEFAULT false` on personal entries.
- **Domain:** `is_upcoming` and `is_now_out` take an explicit `today` (the existing app
  clock, R3).
- **Owner-bound repository** (`ReadingEntryRepository`), with three changes:
  - `list(upcoming_after=today)`: the My books filter;
  - `list_upcoming(today)`: the Upcoming page's "On my list";
  - `list_now_out(today)`: the notice.
- **Catalog:** `upcoming_books(today)` for "Also coming". My own books are removed through
  the owner-filtered `book_ids_on_list`, so no query reads another member's entries.
- **UI:**
  - the new page `/upcoming`, and the Upcoming only checkbox on My books;
  - the Now out notice on the full My books page;
  - the Release date field and the Pre-ordered checkbox in the shared form partials;
  - a `release_label` macro used on every list.
- **JSON API:** additive fields and an `upcoming` query flag (R8).

Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX, httpx

**Storage**: PostgreSQL 16+, with two new columns and one partial index

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL), openapi-core contract
tests, Playwright (Chromium) + axe-core (`a11y`), `perf` marker

**Target Platform**: Single container image (Linux arm64 on the Pi); Safari and Chrome, latest two

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: SC-002 sets under 1 s at p95, with 5,000 books, 5,000 viewer entries
and 200 upcoming books. Range queries use `book_release_date_idx`; the owner filter uses
the existing `reading_entry` user index.

**Constraints**:
- No JavaScript is needed (a checkbox in a GET form; links).
- WCAG 2.2 AA; spec 003 layouts.
- Principle I: no query reads another member's entries.
- "Today" comes from the app clock, and tests pin it.

**Scale/Scope**:
- **Database:** `migrations/versions/0003_upcoming_books.py`.
- **Domain:** `persistence/models.py`, `persistence/mappers.py`, `domain/models.py` and
  `domain/values.py`.
- **Persistence:** `persistence/readings.py` and `persistence/catalog.py`.
- **Services:** `services/readings.py` and `services/catalog.py`.
- **API:** `schemas/catalog.py`, `schemas/readings.py`, `schemas/types.py`,
  `schemas/mappers.py` and `api/readings.py`.
- **Web code:** `web/forms.py`, `web/rendering.py`, `web/routes/readings.py` and
  `web/routes/catalog.py`.
- **Templates:**
  - `pages/list.html`, `partials/reading_list.html` and `pages/upcoming.html` (new);
  - `pages/series.html`, `pages/entry.html` and `pages/add_book.html`;
  - `partials/book_fields.html` and `partials/entry_fields.html`;
  - `macros.html` and `base.html`.
- **Styles:** `app.css`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | New entry reads (`list` with `upcoming_after`, `list_upcoming`, `list_now_out`) are `ReadingEntryRepository` methods built on `_owned()`. "Also coming" uses catalog books minus my owner-filtered `book_ids_on_list`. Pre-ordered is written only through the owner-filtered `update`/`add`. Cross-user tests: Ben's entries, pre-orders and now-out books never appear for Alice (AC-09, AC-18, SC-003); Ben's entry id still 404s; the API filter returns only mine. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Release date is on `book` only; Pre-ordered on `reading_entry` only (spec Data Ownership). |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI involvement. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources; dates are typed by hand. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-21 each get a `007/AC-xx` test, seen failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | `pre_ordered` is `NOT NULL DEFAULT false`; `release_date` is a `DATE` (the DB rejects non-dates). Migration 0003 has a working downgrade, covered by `test_migrations.py` (upgrade → downgrade → upgrade). |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | Form and API input go through `ReleaseDateIn`, `BookCreate`/`BookUpdate` and `ReadingEntryCreate`/`ReadingEntryUpdate`. Contract changes are in `contracts/api-upcoming.md`, applied to the spec 001 `openapi.yaml` and the generated baseline, and checked by contract tests. UI contract: `contracts/ui-upcoming.md`. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | One boolean per entry; nothing is sent out. |

### Coverage-critical modules (Principle V)

- `persistence/readings.py` (already listed in `scripts/check_coverage.py`) gains three
  queries. All of them are covered to 100% by integration tests, including cross-user
  cases.

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| None | | | |

### Migrations (Principle VI)

- **Schema changes:** `0003_upcoming_books` adds `book.release_date`,
  `reading_entry.pre_ordered` and `book_release_date_idx`.
- **Destructive changes:** the downgrade drops both columns, losing release dates and
  pre-order ticks. **Backup step:** the Pi deploy already runs
  `systemctl start books-backup.service` before `docker compose up` (the app runs
  `alembic upgrade head` on start). A downgrade in production needs that backup checked
  first, as in the 0002 docstring.

## Project Structure

### Documentation (this feature)

```text
specs/007-upcoming-books/
├── plan.md               # This file
├── research.md           # Decisions R1–R9
├── data-model.md         # Columns, domain, views, forms
├── quickstart.md         # Checks by hand and test commands
├── contracts/
│   ├── ui-upcoming.md    # /upcoming, My books filter and notice, form fields
│   └── api-upcoming.md   # Additive OpenAPI changes
└── tasks.md              # /speckit-tasks
```

### Source Code (repository root)

```text
migrations/versions/0003_upcoming_books.py
src/book_tracker/
├── domain/{models,values}.py          # release_date, pre_ordered; is_upcoming, is_now_out
├── persistence/{models,mappers,readings,catalog}.py
├── services/{readings,catalog}.py     # upcoming_view, now_out; release_date on create/update
├── schemas/{catalog,readings,types,mappers}.py
├── api/readings.py                    # ?upcoming=
└── web/
    ├── forms.py  rendering.py         # fields; `today` in every template
    ├── routes/readings.py             # /, /upcoming, add/entry saves
    ├── routes/catalog.py              # edit book saves release_date
    ├── static/css/app.css
    └── templates/ …                   # see Scale/Scope

tests/
├── unit/test_upcoming.py                     # is_upcoming/is_now_out boundaries, form parsing
├── integration/test_upcoming_books.py        # pages, filter, notice, privacy, saves
├── integration/test_migrations.py            # + 0003 columns
├── contract/test_upcoming_contract.py        # API fields and filter
├── a11y/test_upcoming_a11y.py                # widths, targets, axe, no-JS, status
└── perf/test_list_performance.py             # + upcoming page and filter budgets
```

**Structure Decision**: the existing single deployable. Date rules are pure domain
functions; queries stay in the owner-bound repository.

## Complexity Tracking

No Constitution Check row is "No"; nothing to justify.
