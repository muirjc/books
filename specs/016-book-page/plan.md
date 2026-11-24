# Implementation Plan: Read-only Book Page

**Branch**: `016-book-page` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-book-page/spec.md`

## Summary

- **The book page:** a new `GET /books/{book_id}` shows a catalog book read-only, using only
  existing services: `catalog.get_book`, `book_stories`, `imports.source_ref`, and
  `readings.entry_for_book` for the viewer's own entry.
- **"Also in":** each story already carries the books that contain it (`Story.books`), so
  this needs no new query.
- **Title links:** they change in the shared `book_row` macro and in the series, Edit
  author and Edit series templates. My books is untouched.
- **Return addresses:** the spec 015 quick-add allow-list gains `/books/<id>`. Add a story
  gains a `from=page` origin that returns to the book page.

Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Jinja2 + HTMX (none new)

**Storage**: PostgreSQL 16+; no schema change

**Testing**: pytest (integration), Playwright + axe (a11y), perf suite

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: The book page under 1 s (p95) at 5,000 books with 50 stories, in
five queries or fewer. The list pages keep their budgets (only link targets change).

**Constraints**:
- Read-only: no form on the page changes the catalog.
- No open redirect: return addresses stay allow-listed (R3).
- Works without JavaScript.

**Scale/Scope**: One family: about 2–10 users and a few thousand books.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | My status comes from `entry_for_book(db, session user, book)`, which uses `ReadingEntryRepository` filtered by user. An AC-13 test gives another member an entry with notes, a rating and a status, and checks none of it shows. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | The page reads catalog data in place (spec, Data Ownership). Nothing is copied. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No new AI. **Draft with AI** posts to the existing spec 012 draft route, which stores nothing until it's accepted. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-15 each get an `ac("016/AC-xx")` test, written failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change. The quick add keeps relying on the unique (user, book) entry constraint. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | The book id is a UUID path parameter (an invalid one is refused). No JSON API change; `GET /api/v1/books/{id}` already exists. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | None stored or sent. |

### Coverage-critical modules (Principle V)

- `src/book_tracker/persistence/readings.py` is unchanged and stays at 100%. It is reached
  through `entry_for_book`.

### New dependencies (Principle VIII)

None.

### Migrations (Principle VI)

- **Schema changes**: None.
- **Destructive changes**: None.

## Project Structure

### Documentation (this feature)

```text
specs/016-book-page/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ui-book-page.md
└── tasks.md
```

### Source Code (repository root)

```text
src/book_tracker/web/routes/readings.py       # GET /books/{book_id} (the book page)
src/book_tracker/web/routes/stories.py        # from=page: Add a story returns to the book page
src/book_tracker/web/quick.py                 # allow /books/<id> as a quick-add return address
src/book_tracker/web/rendering.py             # ACTIVE_TABS entry for the new template
src/book_tracker/web/templates/pages/book.html            # new
src/book_tracker/web/templates/macros.html                # book_row title → book page
src/book_tracker/web/templates/pages/{series,edit_author,edit_series,entry,edit_book}.html
src/book_tracker/web/templates/partials/book_stories.html # optional "Also in" (R4)
src/book_tracker/web/static/css/app.css                   # small additions, if any
tests/integration/test_book_page.py                       # new
tests/a11y/test_book_page_a11y.py                         # new
tests/perf/                                               # book page budget
```

**Structure Decision**: one new page and route in the existing web layer. Everything else
is link targets in templates and two small return-address changes.

## Complexity Tracking

None: every Constitution Check row is Yes.
