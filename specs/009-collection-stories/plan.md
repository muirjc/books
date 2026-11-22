# Implementation Plan: Stories in Collections

**Branch**: `009-collection-stories` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

## Summary

Add stories to the shared catalog: each story has a title, ordered authors, a series and a
number, and is contained in one or more books.

- **Migration 0004** adds `story`, `story_author` and `book_story`
  ([data-model.md](data-model.md)).
- **Persistence and service**:
  - read a story, and list a book's, a series' or an author's stories;
  - add a new story to a book, or add an existing one;
  - edit a story;
  - remove a story from a book, deleting it with its last link (research R2).
- **Pages**:
  - a Stories section on Edit book, with Add, Edit and Remove story pages;
  - a read-only list on the entry page;
  - story rows, "Contains", and story progress on the series page (research R3, R4).
- **Search and spec 008**: story-title matches in book search (R7), and spec 008's "has
  works" rule (R8).
- **API**: new endpoints under `/books/{id}/stories` and `/stories` (research R9,
  [contracts/api-stories.md](contracts/api-stories.md)).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX
(no new dependency)

**Storage**: PostgreSQL 16+, with three new tables

**Testing**:
- pytest with testcontainers;
- openapi-core contract tests;
- Playwright with axe (`a11y`);
- `perf`.

**Performance Goals**: SC-002.
- The series page adds one query for the series' stories, using
  `story_series_number_uq (series_id, …)`, with authors and books loaded by selectin.
- It adds one per-member entries query for the containing books.

**Constraints**:
- works without JavaScript;
- WCAG 2.2 AA;
- spec 003 layouts;
- spec 005 new-name prompts;
- Principle I: only the viewer's entries.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | Story statuses come from the new `ReadingEntryRepository.list_books`, which is user-bound. A cross-user test checks that another member's Finished entry never shows on a story row (AC-15), and a unit-level repository test checks the method returns only the bound user's entries. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Stories and links are catalog data; nothing personal is stored (spec Data Ownership). A story in two books is one row. A lookup by series and number, and by title, comes before any create (FR-005), and the unique index enforces it. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-26 each get a `009/AC-xx` test, seen failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | NOT NULL series and number, the range CHECK, the unique (series, number) index, and RESTRICT foreign keys to series and author. "At least one book" isn't declarative; it is enforced by the atomic conditional delete (research R2). Migration 0004 is reversible and tested upgrade → downgrade → upgrade. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `StoryAdd` and `StoryUpdate` use the existing `Title`, `SeriesNumberIn` and author-id types. Forms go through `parse_add_book` plus the story checks. The endpoints are added to `openapi.yaml` and the generated baseline, with contract tests. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. There are no triggers (research R2). |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | None stored. Log lines hold ids only. |

### Coverage-critical modules

Unchanged list. `persistence/readings.py` (already critical) gains `list_books`, which
needs 100% coverage there.

### Migrations

`0004_collection_stories` creates three tables. Its downgrade drops them along with their
data, so take a backup first in production (as for 0003). The deploy runs the migration on
app start, as usual.

## Project Structure

```text
specs/009-collection-stories/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md
├── checklists/requirements.md
└── contracts/{ui-stories.md, api-stories.md}

migrations/versions/0004_collection_stories.py
src/book_tracker/
├── domain/models.py              # BookRef, Story
├── persistence/models.py         # Story, StoryAuthor, BookStory
├── persistence/mappers.py        # to_story
├── persistence/catalog.py        # story reads/writes, search by story title, _has_no_works
├── persistence/readings.py       # list_books (user-bound)
├── services/catalog.py           # story use cases, story_number_taken conflict
├── services/readings.py          # series_rows with stories
├── schemas/catalog.py, mappers.py# Story, BookRef, StoryAdd, StoryUpdate
├── api/stories.py, api/books.py  # endpoints
└── web/
    ├── forms.py                  # parse_story, story_form
    ├── routes/stories.py         # add / edit / remove story pages
    ├── routes/catalog.py         # Edit book and Edit author sections
    ├── routes/readings.py        # entry page stories; series page
    ├── routes/suggest.py         # kind=stories; book "contains" detail
    └── templates/{pages/add_story,edit_story,confirm_remove_story}.html,
        partials/story_fields.html, edits to edit_book, entry, series, edit_author

tests/
├── integration/test_stories.py, test_series_stories.py
├── unit/test_series_rows_stories.py
├── contract/test_stories_contract.py
├── a11y/test_stories_a11y.py
└── perf (series page with 100 stories)
```

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| "Story in at least one book" enforced in code, not a constraint | PostgreSQL has no declarative "at least one child" constraint | A deferred constraint trigger: the first trigger in the schema, which is more to review and test, for a rule that has a single write path |
