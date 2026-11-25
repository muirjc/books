# Implementation Plan: Flow Fixes

**Branch**: `014-flow-fixes` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-flow-fixes/spec.md`

## Summary

Small template and route fixes from the 2026-11-23 UI review:
- every entry page gets a Stories section with Add a story;
- Add a story gets Add and add another, and returns to where it was opened from;
- back links on Edit book, Edit series, Edit story and Summary;
- the main navigation marks the related tab, and the import tab reads "Import";
- series pages get Add #next and Add a collection;
- author pages get Add a book by this author;
- a Catalog link after an import;
- a Change password link on every page;
- admin confirmation pages for Deactivate, Make Admin and Reset password;
- the favorites link moves next to the Author filter (books-349: then to its own line
  after Apply);
- jump links on the entry page and Edit book.

Nothing new is stored. Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX,
httpx (none new)

**Storage**: PostgreSQL 16+; no schema change

**Testing**: pytest (integration on PostgreSQL), Playwright + axe for a11y

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: The pages stay under 1 s (p95) at 5,000 books. The only new reads
are one entry lookup by book (indexed) and the series' highest number, which is computed
from rows already loaded.

**Constraints**:
- Works without JavaScript.
- No open redirects: return targets are built from ids only.
- CSRF protection on every POST.

**Scale/Scope**: One family: about 2–10 users and a few thousand books.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | Back links and the `from=entry:` return read the viewer's own entry through `ReadingEntryRepository(db, user_id)`. Tests show another member's entry id is ignored (no link, no redirect to it). |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Nothing new is stored. Stories added from an entry page are catalog data, as in spec 009. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI involvement. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | Each AC-01 to AC-21 gets an `ac("014/AC-xx")` test written failing first: integration for links, redirects and confirmations; a11y for layouts and no-JS. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change. Admin rules are unchanged; confirmation only adds a step before them. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | New query and form values (`from`, `author`, `anthology`, `confirm`, `then`) are parsed as UUIDs or fixed literals. No JSON API change. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | None. The reset password stays out of the page text (AC-17). |

### Coverage-critical modules (Principle V)

- `src/book_tracker/persistence/readings.py`: used through `get_by_book`, unchanged, and
  stays at 100%.
- `src/book_tracker/services/accounts.py`: unchanged, because confirmation is a web-layer
  step. Stays at 100%.

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| None | | | |

### Migrations (Principle VI)

- **Schema changes**: None.
- **Destructive changes**: None.

## Project Structure

### Documentation (this feature)

```text
specs/014-flow-fixes/
├── plan.md
├── research.md
├── quickstart.md
├── contracts/ui-flow-fixes.md
└── tasks.md
```

### Source Code (repository root)

```text
src/book_tracker/
├── services/readings.py          # entry_for_book; SeriesView.next_number
├── web/forms.py                  # author_start_form
├── web/routes/readings.py        # entry Stories always; add form anthology/author; messages; active
├── web/routes/stories.py         # from=…, then=another, added=…, active
├── web/routes/catalog.py         # back-link entry lookups; active on edit, summary and unused pages
├── web/routes/authors.py         # active
├── web/routes/admin.py           # confirm step
├── web/templates/base.html       # Import label; Change password
├── web/templates/pages/*.html    # entry, edit_book, edit_series, edit_story, summary,
│                                 #   add_story, series, author, import_summary, list
├── web/templates/admin/confirm_action.html  # new
└── web/static/css/app.css        # back-link, jump-links

tests/integration/test_flow_fixes.py, test_flow_fixes_admin.py
tests/a11y/test_flow_fixes_a11y.py
specs/001-family-reading-list/contracts/ui-routes.md   # rows for the changed routes
```

**Structure Decision**: these are edits to existing routes and templates. The only new
template is the admin confirmation page.

## Complexity Tracking

No violations.
