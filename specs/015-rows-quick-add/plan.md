# Implementation Plan: Consistent Book Rows and Quick Want to read

**Branch**: `015-rows-quick-add` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

## Summary

- **Quick add:** a new `POST /books/{id}/want-to-read` adds a book to my list as Want to
  read through the existing `add_entry`. It redirects back to an allow-listed page (with
  its query) at the book's row, with a notice.
- **One row layout:** a shared `book_row` macro gives the Catalog, author pages and
  Upcoming one layout, with my status as a badge linking to my entry.
- **Series pages:** they keep their layout, and gain the badge and the two actions.

Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Jinja2 + HTMX (none new)

**Storage**: PostgreSQL 16+; no schema change

**Testing**: pytest (integration), Playwright + axe (a11y), perf suite

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: The pages stay under 1 s (p95) at 5,000 books. The quick add is one
insert and a redirect.

**Constraints**:
- No open redirect (research R2).
- Works without JavaScript.
- CSRF protection on the new POST.

**Scale/Scope**: One family.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | The quick add uses `add_entry` with the session user (`ReadingEntryRepository`). Notices and badges use only my entries; tests show another member's entry never shows or blocks. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | The entry references the catalog book; nothing is copied. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-14 each get an `ac("015/AC-xx")` test written failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | The unique (user, book) entry constraint guards double taps (AC-03). No migration. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | The book id is a UUID path parameter; `back` is checked against an allow-list. No JSON API change. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Only the entry the member asks for. |

### Coverage-critical modules (Principle V)

- `src/book_tracker/persistence/readings.py`: unchanged, and stays at 100%.

### New dependencies (Principle VIII)

None.

### Migrations (Principle VI)

None.

## Project Structure

```text
src/book_tracker/web/routes/readings.py     # want-to-read route, safe_back, notices (upcoming, series)
src/book_tracker/web/routes/catalog.py      # notice on the Catalog
src/book_tracker/web/routes/authors.py      # notice on author pages
src/book_tracker/web/templates/macros.html  # book_row, status_badge, quick_add
src/book_tracker/web/templates/partials/{catalog_list,quick_notice}.html
src/book_tracker/web/templates/pages/{author,upcoming,series}.html
src/book_tracker/web/static/css/app.css
tests/integration/test_quick_add.py, test_book_rows.py; tests/a11y/test_rows_a11y.py; perf
```

## Complexity Tracking

No violations.
