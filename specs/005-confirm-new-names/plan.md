# Implementation Plan: Confirm New Author and Series Names

**Branch**: `005-confirm-new-names` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-confirm-new-names/spec.md`

## Summary

The three page forms that type authors and series (Add a book, a book's page, Edit book)
all go through `resolve_authors` and `resolve_series` in `web/routes/readings.py`. Today
those create any typed name that isn't picked; after this change they create a name only
when the form carries a confirmation for that exact name.

- **Exact match:** an unpicked, unconfirmed name that matches a catalog name (any capitals)
  gives today's "Already in the catalog" choice, unchanged.
- **Otherwise:** it becomes a **new-name prompt**:
  - a field error, so it is listed in the error summary with a link;
  - a notice with up to three similar catalog names as "Use “…”" buttons;
  - an "Add “…” as a new author/series" button.
- **Nothing saved:** the page answers 409 (or 422 when there are also field errors), so
  the request's transaction rolls back and nothing is saved. That includes any authors
  created earlier in the same request. Prompts are found by a read-only
  `new_name_prompts`, so they show alongside field errors.

Two kinds of form field carry the choices (no JavaScript needed):

- **`confirm_author_<i>` / `confirm_series`** (the confirmed name): a button sets it, and a
  hidden field keeps it on later re-renders. It counts only while it equals the typed name.
- **`use_author_<i>` / `use_series`** (a catalog id): a "Use “…”" button sets it. The row
  becomes that catalog record, whatever was typed.

Similar names come from a pure function in `domain/values.py`:
- a *loose key* of the name (NFKC, lower case, letters and digits only, leading "the "
  dropped);
- compared with `difflib.SequenceMatcher` against every catalog author (name and real name)
  or series name;
- read by two small read-only catalog queries, which is fine at family scale.

No schema, JSON API, import or dependency changes. See [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX, httpx

**Storage**: PostgreSQL 16+ (no change)

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL); Playwright + axe-core
(`a11y` marker)

**Target Platform**: Single container image (Linux); Safari and Chrome, latest two versions

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: the new-name check runs only on save and only for unpicked names. It
compares with every catalog name (hundreds to a few thousand) in well under 50 ms. Page
budgets are unchanged.

**Constraints**: works without JavaScript; WCAG 2.2 AA and the spec 003 layouts; keeps the
spec 004 `then` choice.

**Scale/Scope**:
- `domain/values.py`: `loose_name_key` and `similar_names`;
- `persistence/catalog.py`: `author_names` and `series_names`, read-only;
- `services/catalog.py`: `similar_authors` and `similar_series`;
- `web/forms.py`: parse the `confirm_*` and `use_*` fields;
- `web/routes/readings.py`: `resolve_authors`, `resolve_series`, `save_book_details`,
  `add_book`, and the entry and edit-book renderers;
- `web/routes/catalog.py`: the edit-book renderer;
- templates: `partials/book_fields.html` and a new `partials/new_name.html`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | No personal data is read for this. Similar names come from catalog authors and series, which every member sees. The book's page still loads the entry through the owner-filtered `get_entry` (existing cross-user tests). |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Strengthens "catalog writes MUST deduplicate": a typed name is checked against the catalog (exact, then similar) before any create. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI involvement. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-14 each get a `005/AC-xx` test, seen failing first. SC-002 gets a typo table test. Tests that pin existing behaviour (AC-07, AC-10) are marked guard. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change. The unique `lower(name)` indexes stay the backstop (the "someone added it meanwhile" edge case). |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | New page fields: `confirm_*` (a string compared exactly with the typed name, never used on its own) and `use_*` (parsed as UUID, looked up in the catalog). No JSON API change; the OpenAPI contract check stays green. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | `difflib` is in the standard library; no `pg_trgm` extension or migration. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Nothing stored or sent. |

### Coverage-critical modules (Principle V)

- None of the listed critical modules change. The new domain and service functions get full
  unit and integration coverage regardless.

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| None (`difflib`, stdlib) | Similar names | `pg_trgm` (needs an extension and migration); `rapidfuzz` (new dependency) | PSF |

### Migrations (Principle VI)

- **Schema changes**: None
- **Destructive changes**: None

## Project Structure

### Documentation (this feature)

```text
specs/005-confirm-new-names/
├── plan.md                 # This file
├── research.md             # Decisions R1–R7
├── data-model.md           # No schema change; the form fields and the prompt
├── quickstart.md           # Checks by hand and the test commands
├── contracts/
│   └── ui-new-names.md     # Form fields, status codes, markup
└── tasks.md                # /speckit-tasks
```

### Source Code (repository root)

```text
src/book_tracker/
├── domain/values.py              # loose_name_key, similar_names (pure)
├── persistence/catalog.py        # author_names(), series_names() (read-only)
├── services/catalog.py           # similar_authors(), similar_series()
└── web/
    ├── forms.py                  # AuthorRow.confirmed / use_id; series confirm / use
    ├── routes/readings.py        # NewName; resolve_* check; BookSaveProblem.new_names
    ├── routes/catalog.py         # edit book passes new_names to the template
    └── templates/partials/
        ├── book_fields.html      # include new_name.html per author row and series
        └── new_name.html         # notice, Use “…” buttons, Add as new button, hidden confirm

tests/
├── unit/test_similar_names.py              # loose key, ranking, SC-002 typo table
├── integration/test_confirm_new_names.py   # three pages, choices, rollback, combinations
└── a11y/test_confirm_new_names_a11y.py     # no-JS flow, error summary, targets, axe
```

**Structure Decision**: the single deployable stays. Matching is a pure domain function so
it is unit-testable. Catalog reads go through persistence, and the web layer decides when to
prompt.

## Complexity Tracking

No Constitution Check row is "No"; nothing to justify.
