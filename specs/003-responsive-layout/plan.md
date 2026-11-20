# Implementation Plan: Responsive Layout for Phone, Tablet and Laptop

**Branch**: `003-responsive-layout` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-responsive-layout/spec.md`

## Summary

Give every page three layouts chosen by window width: phone (under 40em), tablet (40em to
under 64em) and laptop (64em and wider). The work is almost all in the one stylesheet,
`app.css`, plus small template changes:

- **Page width:** wider page on laptop.
- **Header:** fits on one row.
- **My books:** separate cells in each row, so laptop rows can add date finished and times
  read, and phone rows take two lines.
- **Phone filters:** a "Sort and filter" fold on phone, a small progressive enhancement in
  `app.js`.
- **Book forms:** two-column forms on laptop, with short fields paired on tablet.
- **Import:** controls on one row on laptop.

No data, service, route, URL, form field or JSON API changes. The tests are Playwright
layout checks at 360, 390, 768, 820, 1,024 and 1,440 px, plus 200% zoom. Integration tests
cover the server-rendered parts: the new row cells and the fold state.
See [research.md](research.md) for the decisions.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX, httpx

**Storage**: PostgreSQL 16+ (no change)

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL), Playwright (Chromium) +
axe-core for the `a11y` marker (already used by specs 001 and 002)

**Target Platform**: Single container image (Linux); browsers: Safari (iOS/iPadOS/macOS) and
Chrome, latest two versions

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: My books under 1 s at p95 with 5,000 books (SC-006; existing perf
test). The added cells use data the list query already loads.

**Constraints**:
- CSS only, plus one progressive enhancement in `app.js`. Every page must work without
  JavaScript, as the 001 constitution notes and the `app.js` header require.
- WCAG 2.2 AA at all three layouts.
- Breakpoints are in `em`, so they follow the text size (FR-014).

**Scale/Scope**: One family: about 2–10 users and a few thousand books. Pages touched:
- `base.html` (header);
- My books (`list.html`, `partials/reading_list.html`);
- Add a book, a book's page and Edit book (`book_fields.html`, `entry_fields.html`,
  `add_book.html`, `entry.html`);
- the import pages;
- `app.css` and `app.js`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | No data access changes. My books shows two more of the member's own fields (date finished, times read) from the same owner-filtered query; the existing cross-user tests still cover it. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec Data Ownership table; nothing stored. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI involvement. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources touched. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | Each of AC-01 to AC-22 has a test tagged `003/AC-xx`, written and seen failing before its CSS or template change. AC-15, AC-16 and AC-18 already hold today; their tests pin the behaviour and are noted as regression guards in tasks.md. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | No new input and no JSON API change. The UI layout contract is in `contracts/ui-layout.md`. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | No new dependency. Playwright and axe-core are already dev dependencies. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Nothing stored or sent. |

### Coverage-critical modules (Principle V)

- None touched. `persistence/readings.py` and the authorization modules are unchanged.
- The list route passes the same entries to the template.

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
specs/003-responsive-layout/
├── plan.md              # This file
├── research.md          # Decisions R1–R9
├── data-model.md        # No data changes (stated for completeness)
├── quickstart.md        # How to check the layouts by hand and run the tests
├── contracts/
│   └── ui-layout.md     # Per-page layout contract at each size
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/book_tracker/web/
├── static/css/app.css               # breakpoints, container, header, list rows, form grid,
│                                    #   import controls, readable line length
├── static/js/app.js                 # "Sort and filter" fold on phone (progressive)
└── templates/
    ├── base.html                    # header markup classes (no content change)
    ├── pages/list.html              # filters: fold toggle + data-fold state
    ├── partials/reading_list.html   # row cells: title, authors/series, status, finished, times read
    ├── partials/book_fields.html    # series + number wrapped in a paired row
    ├── partials/entry_fields.html   # status + date finished wrapped in a paired row
    ├── pages/add_book.html          # two column groups: book, reading
    ├── pages/entry.html             # two column groups (sections already exist)
    └── pages/import_works.html      # control row class (if needed)

src/book_tracker/web/routes/readings.py   # pass "filters_open" (any non-default sort/filter)

tests/
├── a11y/test_layout_003.py          # Playwright: widths, rows, columns, header rows, zoom, axe
└── integration/test_layout_markup.py # server HTML: row cells, fold state, field order
```

**Structure Decision**:
- The existing single deployable stays as it is.
- Changes are confined to `web/` templates, static assets and one context flag in the list
  route.
- The new tests sit in the existing `a11y` and `integration` layers.

## Complexity Tracking

No Constitution Check row is "No"; nothing to justify.
