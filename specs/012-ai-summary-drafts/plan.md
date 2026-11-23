# Implementation Plan: AI Summary Drafts

**Branch**: `012-ai-summary-drafts` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-ai-summary-drafts/spec.md`

## Summary

A member asks for an AI draft of a book's summary from the Summary page, the entry page or
Add a book. The work happens in `services/drafts.py`:
1. Return a cached draft for the book's key (ISBN, or title and authors) if one is younger
   than 30 days, unless the member asked to regenerate.
2. Otherwise reserve one of the member's 10 daily drafts.
3. Get Open Library's description.
4. Call the `SummaryGenerator`. In production that is Claude Opus 5.5, with web search that
   blocks Amazon and Goodreads, and a strict `submit_summary_draft` tool.
5. Check the result: blocked sites, 60–250 words, no 12-word copy of the description.
6. Store it as a `summary_draft` row, outside the catalog.

The draft is shown unsaved and editable. Saving with its `draft_id` stores origin `ai` or
`ai_edited` with the model and sources. Any other save is `manual`. Failures show plain
messages and leave hand-writing intact. Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX,
httpx; **new:** `anthropic` 2.x (R1)

**Storage**: PostgreSQL 16+; two new tables (`summary_draft`, `ai_draft_usage`)

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL), recorded HTTP fixtures
for Open Library, `FakeSummaryGenerator`, plus unit tests of `ClaudeSummaryGenerator`
against a mocked transport. CI never calls Anthropic or the web.

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: A draft, or a failure message, within 30 s (SC-002). The Summary,
entry and Add a book pages are otherwise unchanged and stay under 1 s.

**Constraints**:
- The key is a secret setting.
- Only book metadata is sent.
- No page waits on the AI except the draft request (AC-14).

**Scale/Scope**: One family: about 2–10 users and a few thousand books; at most 10 AI
requests per member per day.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | The allowance is read and written only through `DraftUsageRepository(db, user_id)`. A test shows one member's use never changes another's (AC-10). No reading-entry data is touched. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Drafts are a catalog cache in their own table. Saved summaries use the existing `book_summary`. The usage count is personal (spec Data Ownership). |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | Draft rows are never read by any summary display. Only a save carrying a valid `draft_id` gets `ai`/`ai_edited` with model and sources. 30 s timeout. Daily limit. Drafts cached 30 days and Open Library descriptions 24 hours, both keyed by ISBN or title + authors. Regenerate bypasses it. Every failure falls back to hand-writing (AC-09). |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | Open Library through `BookSource.describe_book`; Claude through `SummaryGenerator`. Amazon and Goodreads go in `blocked_domains`, and a post-check rejects any draft citing them (R4). There's a 12-word copy check against the description (R5). |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | tasks.md orders tests first. AC-01 – AC-26 are tagged `012/AC-xx`. The fake generator and recorded fixtures mean no live calls. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | Migration 0006 adds both tables: CHECKs on count ≥ 1, the series number range, and non-empty text; the composite primary key; foreign keys. Upgrade → downgrade → upgrade is tested. `book_summary_ai_model_check` already requires a model for AI origins. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `SummaryDraftRequest`, the `SummaryDraft` response, `SummaryCreate.draft_id`, and the page forms `DraftForm`, `SummaryForm` and Add a book's action. Contract in `contracts/api-summary-drafts.md` and openapi.yaml; contract tests. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | One new library (below); no new service or store. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Only a per-day count, deleted after 30 days. The request is built from `BookFacts` alone (a test asserts its fields). The key is a `SecretStr` from the environment, never rendered or logged. |

### Coverage-critical modules (Principle V)

- `src/book_tracker/persistence/draft_usage.py` (new: the per-member allowance)
- The existing seven stay at 100%.

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| `anthropic` (>=2.12,<3) | Official Claude SDK: typed requests, server tools, errors, timeouts. It brings `httpx2`, `jiter`, `docstring-parser`, `opentelemetry-api` and `anyio`. | Raw `httpx` calls (rejected: the Claude API guidance requires the official SDK, and hand-written types would drift) | Apache-2.0 |

### Migrations (Principle VI)

- **Schema changes**: `0006_summary_drafts` adds:
  - `summary_draft`, with a primary key, a check that `text` is non-empty, a check on the
    series number range, and an index on `(draft_key, created_at DESC)`;
  - `ai_draft_usage`, with a `(user_id, day)` primary key, a `user_id` foreign key that
    cascades, and a `count >= 1` check.

  It also widens `source_lookup_cache_kind_check` to allow `book_description`. The
  downgrade deletes those rows first.
- **Destructive changes**: none.

## Project Structure

### Documentation (this feature)

```text
specs/012-ai-summary-drafts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api-summary-drafts.md
│   └── ui-summary-drafts.md
└── tasks.md
```

### Source Code (repository root)

```text
src/book_tracker/
├── settings.py                   # anthropic_api_key, ai_model, ai_daily_draft_limit, ai_timeout_seconds
├── main.py                       # summary_generator wiring; drafts router
├── domain/drafts.py              # BookFacts, draft_key, checks (R4, R5)
├── sources/
│   ├── base.py                   # BookSource.describe_book
│   ├── open_library.py           # describe_book (R3)
│   ├── summary_generator.py      # SummaryGenerator protocol, GeneratedDraft, UnconfiguredGenerator, dependency
│   └── claude.py                 # ClaudeSummaryGenerator (R1, R2)
├── persistence/
│   ├── models.py                 # SummaryDraft, AiDraftUsage
│   ├── drafts.py                 # draft cache rows (R6)
│   ├── draft_usage.py            # DraftUsageRepository (R8), coverage-critical
│   └── catalog.py                # save_summary gains model and source_urls
├── services/
│   ├── errors.py                 # AiNotConfigured, AiUnavailable, DraftLimitReached, DraftNotPossible
│   ├── drafts.py                 # request_draft, origin_for
│   └── summaries.py              # save_summary with draft_id
├── schemas/catalog.py            # SummaryDraftRequest, SummaryDraft, SummaryCreate.draft_id
├── api/books.py                  # POST /books/{id}/summary-drafts
├── api/errors.py, responses.py   # new problem codes
└── web/
    ├── routes/catalog.py         # summary draft route; edit book suggest_series
    ├── routes/readings.py        # Add a book draft_summary action
    └── templates/                # summary.html, partials/summary_draft.html, entry.html, add_book.html, edit_book.html

migrations/versions/0006_summary_drafts.py

tests/
├── fakes.py                      # FakeSummaryGenerator
├── unit/test_draft_rules.py      # word count, copy check, blocked hosts, key, origin
├── unit/test_claude_generator.py # request shape, loop, errors (mocked transport)
├── external/test_open_library_describe.py
├── integration/test_summary_drafts.py
├── integration/test_draft_failures.py
├── integration/test_draft_cache.py
├── integration/test_series_suggestion.py
├── integration/test_draft_entry_points.py
├── contract/test_summary_drafts_contract.py
└── a11y/test_summary_drafts_a11y.py
```

**Structure Decision**: the generator sits beside the book-source adapter, as the
constitution's layout says. The use case is one service shared by the pages and the API.

## Complexity Tracking

No "No" answers; nothing to justify.
