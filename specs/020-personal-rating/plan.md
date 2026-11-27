# Implementation Plan: Personal Rating

**Branch**: `020-personal-rating` | **Date**: 2026-11-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/020-personal-rating/spec.md`

## Summary

- **Schema** (migration `0008`): `reading_entry.rating`, a nullable smallint with a 1–5
  CHECK. The downgrade drops it.
- **Forms**: a "Rating (optional)" select in the shared entry fields, so the entry page and
  Add a book both get it.
- **Display**: "Rated N out of 5" as text on My books rows and the book page (the
  viewer's own entry only).
- **My books**: "Highest rated" and "Lowest rated" sorts (unrated last) and a Rating filter
  ("N and up", Rated, Not rated).
- **API**: an optional, nullable `rating` on entry create, update and read; `sort=±rating`,
  `min_rating` and `rated` on the list. Not breaking.

Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX (none new)

**Storage**: PostgreSQL 16+; one reversible migration (R1)

**Testing**: pytest (unit, integration, contract, migrations), Playwright + axe (a11y), perf suite

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI and a JSON API (one deployable)

**Performance Goals**: My books sorted or filtered by rating under 1 s (p95) at 5,000
books, with no new index (R1).

**Constraints**:
- The rating is read and written only through the session user's entries (Principle I).
- The forms and the filter work without JavaScript.
- The rating is never shown by symbols or colour alone.

**Scale/Scope**: One family: about 2–10 users and a few thousand books.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | The rating is a column of `reading_entry`, read and written only through `ReadingEntryRepository`, bound to the session user. New cross-user tests: Ben's rated entry is 404 to Alice; the book, series and author pages, the catalog, Upcoming and the catalog API never show Ben's rating to Alice (R7, AC-12). |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec, Data Ownership: the rating is personal, on the entry only; no catalog record gets one. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-15 each get an `ac("020/AC-xx")` test, written failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | CHECK `reading_entry_rating_check` (1–5). `0008` has a downgrade, tested up and down. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `rating` is `int | None` with `ge=1, le=5` on create and update; `min_rating` and `rated` are typed query parameters. `openapi.yaml` and the generated baseline are updated; contract tests cover them. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | One optional number per entry, set only by the member. Nothing is sent anywhere. |

### Coverage-critical modules (Principle V)

- `src/book_tracker/persistence/readings.py`: the rating sort and filter. Stays at 100%.

### New dependencies (Principle VIII)

None.

### Migrations (Principle VI)

- **Schema changes**: `reading_entry.rating smallint NULL`, CHECK `rating BETWEEN 1 AND 5`.
- **Destructive changes**: the downgrade drops the column and its ratings. The backup taken
  before every deploy keeps them (spec Clarifications).

## Project Structure

### Documentation (this feature)

```text
specs/020-personal-rating/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/{ui-rating.md, api-rating.md}
└── tasks.md
```

### Source Code (repository root)

```text
migrations/versions/0008_personal_rating.py            # new
src/book_tracker/persistence/models.py                 # ReadingEntry.rating + CHECK
src/book_tracker/persistence/readings.py               # SORTS, _order, min_rating / rated filter, create/update
src/book_tracker/persistence/mappers.py                # to_reading_entry
src/book_tracker/domain/models.py                      # ReadingEntry.rating
src/book_tracker/services/readings.py                  # list_entries pass-through; create with rating
src/book_tracker/schemas/readings.py                   # Create / Update / ReadingEntry rating
src/book_tracker/schemas/mappers.py                    # rating in the response
src/book_tracker/api/readings.py                       # Sort literal, min_rating, rated
src/book_tracker/web/forms.py                          # parse_entry_update, parse_add_book
src/book_tracker/web/routes/readings.py                # SORT_OPTIONS, rating filter, ENTRY_FIELDS, add book
src/book_tracker/web/templates/macros.html             # rating_text
src/book_tracker/web/templates/partials/{entry_fields,reading_list}.html
src/book_tracker/web/templates/pages/{list,entry,book}.html
specs/001-family-reading-list/contracts/openapi.yaml           # rating, sort, min_rating, rated
specs/001-family-reading-list/contracts/openapi.generated.json # regenerated
tests/integration/test_personal_rating.py              # new
tests/integration/test_migrations.py                   # 0008 up/down
tests/contract/test_personal_rating_contract.py        # new
tests/a11y/test_personal_rating_a11y.py                # new
tests/perf/test_personal_rating_perf.py                # new
```

**Structure Decision**: no new pages or modules. The rating follows the path of the existing
entry fields (times read, notes) from the column up to the templates.

## Complexity Tracking

None: every Constitution Check row is Yes.
