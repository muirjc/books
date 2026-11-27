# Implementation Plan: Stories Without a Series

**Branch**: `019-optional-story-series` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/019-optional-story-series/spec.md`

## Summary

- **Schema** (migration `0007`): a story's series and number become optional, both or
  neither (a CHECK). `book_story` gains `position`, the order a story was added to the book.
  The downgrade is refused while any story has no series.
- **Order**: a book lists stories with a series by series name and number, then stories
  without one by position.
- **Forms**: on Add a book's story rows, a blank number and series make a story without a
  series, and a number with a blank series still takes the book's series. Add a story and
  Edit story allow clearing both.
- **Display**: a story without a series shows its title (and authors) only, and is on no
  series page.
- **API**: story schemas make the series pair optional and nullable.

Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX (none new)

**Storage**: PostgreSQL 16+; one reversible migration (R1)

**Testing**: pytest (integration, contract, migrations), Playwright + axe (a11y), perf suite

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI and a JSON API (one deployable)

**Performance Goals**: book, entry and series pages with stories under 1 s (p95) at 5,000
books; the book's story list stays one query.

**Constraints**:
- Every existing story keeps its series and number (AC-14).
- The forms work without JavaScript.
- No change to which stories a series page shows, other than leaving out stories without a
  series.

**Scale/Scope**: One family: about 2–10 users and a few thousand books.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | No new personal data. Story statuses still come from the viewer's own entries (spec 009); the existing cross-user tests stay. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec, Data Ownership. A story is still stored once; `position` is catalog data on the book-story link. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-16 each get an `ac("019/AC-xx")` test, written failing first. Spec 009 and 013 tests of changed rules are rewritten (spec, "Amended specs"). |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | `story_series_both_or_neither` CHECK; the unique (series, number) index stays. `0007` has a downgrade, refused with a message while a story has no series, tested both ways. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `StoryAdd`, `StoryUpdate`, `NewBookStory` and the entry `stories` validator enforce both-or-neither. The regenerated OpenAPI baseline and contract tests cover the nullable fields (R6). |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | None. |

### Coverage-critical modules (Principle V)

No coverage-critical module changes. (`persistence/readings.py` is untouched: story
statuses are worked out in the services from the viewer's own entries.)

### New dependencies (Principle VIII)

None.

### Migrations (Principle VI)

- **Schema changes**: `story.series_id`, `story.series_number` nullable; CHECK
  `story_series_both_or_neither`; `book_story.position` integer NOT NULL, filled per book by
  series name then number.
- **Destructive changes**: none. The downgrade refuses rather than inventing series.

## Project Structure

### Documentation (this feature)

```text
specs/019-optional-story-series/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/{ui-stories.md, api-stories.md}
└── tasks.md
```

### Source Code (repository root)

```text
migrations/versions/0007_optional_story_series.py      # new
src/book_tracker/persistence/models.py                 # Story nullable pair + CHECK; BookStory.position
src/book_tracker/persistence/catalog.py                # book_stories order, link_story position, story_matches order, create/update
src/book_tracker/persistence/mappers.py                # to_story with no series
src/book_tracker/domain/models.py                      # Story.series / series_number optional
src/book_tracker/services/catalog.py                   # story_label; add/update rules; duplicate checks only with a series
src/book_tracker/services/readings.py                  # series views skip stories without a series (type-level)
src/book_tracker/schemas/catalog.py                    # StoryAdd, StoryUpdate, NewBookStory, Story output
src/book_tracker/schemas/readings.py                   # entry stories validator
src/book_tracker/schemas/mappers.py                    # nullable series in the Story response
src/book_tracker/web/forms.py, web/anthology.py        # story rows rules (R5)
src/book_tracker/web/routes/stories.py                 # Add a story, Edit story
src/book_tracker/web/templates/partials/{book_stories,story_rows}.html
src/book_tracker/web/templates/pages/{author,edit_story,add_story,edit_book}.html
specs/001-family-reading-list/contracts/openapi.generated.json   # regenerated
tests/integration/test_story_series_optional.py        # new
tests/integration/test_migrations.py                   # 0007 up/down
tests/contract/ (story and anthology contract tests)    # no-series cases
tests/a11y/test_story_series_optional_a11y.py          # new
tests/perf/test_story_series_optional_perf.py          # new
```

**Structure Decision**: no new pages or modules. The change runs from the schema up through
the existing story code, with mypy --strict finding every place that assumed a series.

## Complexity Tracking

None: every Constitution Check row is Yes.
