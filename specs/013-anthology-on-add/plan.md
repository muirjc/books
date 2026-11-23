# Implementation Plan: Anthology Stories on Add a Book

**Branch**: `013-anthology-on-add` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-anthology-on-add/spec.md`

## Summary

Add a book gains a **This book is an anthology or collection** checkbox and a repeatable
set of story rows, each with a title, number, series and author. Rows are numbered form
fields (`story_title_{i}` and so on), parsed into a `StoryRow` list on `AddBookForm`.

**Add another story** and **Remove story N** are submit actions that redraw the form
without writing, like the existing **Draft summary with AI**. The page needs no JavaScript;
`app.js` only shows and hides the section.

On save, the route:
1. validates the book and every row together, including repeated pairs and the
   unticked-box rule;
2. runs one spec 005 new-name pass over the book and the rows, with one prompt per distinct
   name;
3. pre-checks each row's series and number for an existing story, offering **Use that
   story**;
4. calls `services/readings.add_entry(..., stories=[...])`, which creates the book, links
   or creates each story through the spec 009 services, then adds the entry.

Any refusal renders with status ≥ 400, which rolls back the whole request, so the save is
all or nothing. The JSON API's `POST /api/v1/me/readings` gains an optional `stories` list
handled by the same service. Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX,
httpx (no new ones)

**Storage**: PostgreSQL 16+; no schema change

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL), Playwright + axe for a11y,
the perf suite on the seeded 5,000-book catalog

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: Add a book with 50 story rows saves in under 1 s at p95 (SC-002).
Redraw actions write nothing.

**Constraints**:
- Works without JavaScript.
- Saving is all or nothing.
- The spec 009 story rules and the spec 005 name prompts are unchanged.

**Scale/Scope**: One family: about 2–10 users and a few thousand books; up to 50 stories
per save.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | The only personal write is the member's own new entry, through the existing `ReadingEntryRepository(db, user_id)` in `add_entry`. A test shows another member's list is untouched and their entry for the same book is not reported. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Stories stay catalog-only (spec 009 tables). An existing story is linked, never copied (AC-13, FR-006). |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No new AI use. The spec 012 summary draft is unchanged, and story rows are never sent to the AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | Each of AC-01 to AC-30 gets an `ac("013/AC-xx")` test written failing first: unit (row parsing, pairs), integration (web save, names, atomicity, races), contract (API), a11y (layouts, keyboard, no-JS), perf (50 rows). |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | Story uniqueness is the existing `story_series_number_uq`. Book, story and entry creation share one transaction, rolled back on any refusal. No migration. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | New `NewBookStory` model; `ReadingEntryCreate.stories` with validators (R8). `openapi.yaml` regenerated; the change is additive. Form rows are validated with the same `Title` and `SeriesNumberIn` types. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None added. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | No new personal data; nothing sent out. |

### Coverage-critical modules (Principle V)

- `src/book_tracker/persistence/readings.py`: used unchanged by `add_entry`; stays at 100%.
- No other ownership-filtering code is touched.

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
specs/013-anthology-on-add/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api-anthology.md
│   └── ui-anthology.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/book_tracker/
├── api/readings.py              # pass body.stories to add_entry; 409 for StoryNumberTaken
├── schemas/readings.py          # ReadingEntryCreate.stories + validators
├── schemas/catalog.py           # NewBookStory
├── services/catalog.py          # StoryForBook values; story creation for a new book
├── services/errors.py           # StoryNumberTaken(index, story)
├── services/readings.py         # add_entry(..., stories=...)
├── web/forms.py                 # StoryRow, AddBookForm.anthology/stories, parse + row checks
├── web/routes/readings.py       # add_story/remove_story/use_story actions; names over rows;
│                                #   pre-check; save; redirects with stories=N; AC-20
├── web/templates/pages/add_book.html          # checkbox + section; AC-18 note
├── web/templates/partials/story_rows.html     # the rows (new)
├── web/templates/pages/{my_list,series,entry}.html  # "with N stories" / stories_not_added notices
└── web/static/{js/app.js,css/app.css}         # toggle; row layout

specs/001-family-reading-list/contracts/        # openapi.yaml, generated JSON, ui-routes.md

tests/
├── unit/test_story_rows.py                     # parsing, renumbering, pairs, blank rows
├── integration/test_anthology_add.py           # US1, US3 web flows
├── integration/test_anthology_checks.py        # US2: errors, taken numbers, races, atomicity
├── integration/test_anthology_names.py         # AC-15 shared new-name prompts
├── contract/test_anthology_contract.py         # US4
├── a11y/test_anthology_a11y.py                 # US5
└── perf/                                       # 50-row save (SC-002)
```

**Structure Decision**: this is an extension of Add a book. The story rules stay in the
spec 009 services, which the new `add_entry(stories=...)` path calls. No new route or table.

## Complexity Tracking

No violations.
