# Implementation Plan: Save and Add Another

**Branch**: `004-save-and-add-another` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-save-and-add-another/spec.md`

## Summary

Add a second submit button, **Add and add another**, to Add a book. Both buttons post the
same form to `POST /books/add`; the button's value (`then=list` or `then=another`) only
changes where a successful save redirects:

- `then=list` (or missing): `303 /?msg=added`, as today.
- `then=another`: `303 /books/add?after=<entry_id>`.

`GET /books/add?after=<entry_id>` loads the signed-in member's own entry through the
existing owner-filtered `service.get_entry`. It renders a fresh form pre-filled from that
entry's catalog book (authors with ids, series with id, next whole number) and the entry's
status, with a confirmation linking to the entry, and `autofocus` on Title. Any other
entry id (another member's, removed, malformed) gives the plain empty form (Principle I).

A hidden `then` field at the top of the form remembers the chosen button across error and
conflict pages, so a conflict's own submit buttons ("Use existing author", "Add … instead")
keep the original choice; either main button, later in the form, overrides it. No schema,
service, JSON API or dependency changes. See [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX, httpx

**Storage**: PostgreSQL 16+ (no change)

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL); Playwright (Chromium) +
axe-core for the `a11y` marker

**Target Platform**: Single container image (Linux); Safari and Chrome, latest two versions

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: Add a book within the existing page budget (SC-004). The carry-over
adds one owner-filtered entry read by primary key.

**Constraints**:
- Works without JavaScript (FR-011): plain submit buttons with `name`/`value`, `autofocus`.
- WCAG 2.2 AA; spec 003 layouts (phone, tablet, laptop; 200% text).
- Post/Redirect/Get, so reload never re-adds (FR-008).

**Scale/Scope**: One route module (`web/routes/readings.py`: `add_book_form`, `add_book`,
`_add_form`), one form helper (carry-over form from an entry), templates `add_book.html`,
`partials/book_fields.html`, `partials/combobox.html`, and a few CSS lines for the button
row.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | Carry-over reads the entry with the existing `service.get_entry(db, user_id, entry_id)`, which filters by the session user in `persistence/readings.py`; `NotFoundError` → plain form. A cross-user test proves Ben's entry id gives Alice an empty form with nothing of Ben's in it. `user_id` comes from the session only. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec Data Ownership table; nothing new stored. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI involvement. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | Each AC-01 to AC-18 gets a test tagged `004/AC-xx`, seen failing first. AC-04, AC-13, AC-16 hold today for the existing button; their tests pin them for the new one. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change; the series-number rule stays in the DB (AC-13). |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `then` is a closed choice (`list`/`another`, anything else = `list`); `after` is parsed as a UUID (invalid = ignored). No JSON API change. UI contract in `contracts/ui-add-another.md`. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Nothing stored or sent. The entry id in the redirect URL is the member's own and already appears in their own links. |

### Coverage-critical modules (Principle V)

- `persistence/readings.py` and the authorization modules are unchanged; the new code reuses
  `service.get_entry`.

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
specs/004-save-and-add-another/
├── plan.md                  # This file
├── research.md              # Decisions R1–R7
├── data-model.md            # No data changes; the carry-over mapping
├── quickstart.md            # Checks by hand and the test commands
├── contracts/
│   └── ui-add-another.md    # POST/GET behaviour, form fields, markup contract
└── tasks.md                 # /speckit-tasks
```

### Source Code (repository root)

```text
src/book_tracker/web/
├── forms.py                     # carry_over_form(entry) -> AddBookForm; next_series_number()
├── routes/readings.py           # add_book_form: ?after=; add_book: then=list|another
├── static/css/app.css           # .form-actions button row (wraps on phone)
└── templates/
    ├── pages/add_book.html      # hidden then, confirmation, two buttons, then in ISBN form
    ├── partials/book_fields.html# autofocus + aria-describedby on Title when after an add
    └── partials/combobox.html   # optional autofocus and extra describedby id

tests/
├── unit/test_add_another_forms.py        # next number, carry-over mapping
├── integration/test_add_another.py       # flow, carry-over, PRG, cross-user, conflicts
└── a11y/test_add_another_a11y.py         # widths, targets, focus, no-JS, axe
```

**Structure Decision**: the existing single deployable; changes stay in `web/` (route,
form helper, templates, CSS) and the existing test layers.

## Complexity Tracking

No Constitution Check row is "No"; nothing to justify.
