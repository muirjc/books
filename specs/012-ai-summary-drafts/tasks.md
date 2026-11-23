# Tasks: AI Summary Drafts (spec 012)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: required (Constitution V). Each test is written first and seen failing. Tests are
tagged `@pytest.mark.ac("012/AC-xx")`. No test calls Anthropic or the web.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [ ] T001 Add `anthropic>=2.12,<3` to `pyproject.toml` and refresh `uv.lock`. Check that
  `uv run mypy --strict src` and `uv run pip-audit` still pass.
- [ ] T002 Add the settings `anthropic_api_key: SecretStr | None`, `ai_model`
  (`claude-opus-5-5`), `ai_daily_draft_limit` (10) and `ai_timeout_seconds` (30.0) to
  `src/book_tracker/settings.py`, with a unit test in `tests/unit/test_settings.py`
  (defaults; the key is never in `repr`).
- [ ] T003 Add `FakeSummaryGenerator` to `tests/fakes.py`: scripted results or errors, a
  record of every call's `BookFacts` and description. Add `summary_draft` and
  `ai_draft_usage` to the conftest table list, and a `summary_generator` fixture installed
  on the app.

## Phase 2: Foundational

- [ ] T004 [P] Write failing unit tests in `tests/unit/test_draft_rules.py` for:
  - `draft_key` (ISBN, or title and authors, normalized and order-independent);
  - `word_count`;
  - `copies_source` (12-word runs; case and punctuation ignored);
  - `is_blocked` (amazon.* storefronts and goodreads.com, including subdomains; not
    `notamazon.com`);
  - source filtering (R5);
  - `origin_for` (R6).
- [ ] T005 Add `src/book_tracker/domain/drafts.py` (`BookFacts`, `BookDescription`,
  `GeneratedDraft`, `DraftView`, the rules above, `BLOCKED_DOMAINS`) to make T004 pass.
- [ ] T006 Write a failing migration test (`TABLES_0006`, constraints, the widened
  `source_lookup_cache` kind check, upgrade → downgrade → upgrade) in `tests/integration/test_migrations.py`. Then add
  `migrations/versions/0006_summary_drafts.py` and the `SummaryDraft` and `AiDraftUsage`
  models.
- [ ] T007 Write failing repository tests, then add:
  - `persistence/drafts.py`: insert, newest-for-key within 30 days, get by id, prune;
  - `persistence/draft_usage.py`: `DraftUsageRepository(db, user_id)` with `reserve` and
    `left` (atomic at the limit, under concurrency; no effect on another member; prune).

  Add `draft_usage.py` to `scripts/check_coverage.py`.
- [ ] T008 [P] Write failing external tests with recorded fixtures in
  `tests/external/test_open_library_describe.py`:
  - by ISBN;
  - by title and author;
  - string and `{value}` descriptions;
  - none found;
  - Open Library down (returns None, no raise).

  Then add `describe_book` to `BookSource`, `UnavailableSource` and `OpenLibrarySource`.
  Add `get_description` and `put_description` (kind `book_description`, 24 h, with "none
  found" cached) to `persistence/source_cache.py`, with tests. The service uses the cache
  before calling Open Library.
- [ ] T009 [P] Write failing unit tests in `tests/unit/test_claude_generator.py`, against
  a mocked SDK transport, for:
  - the request: model, effort, the `web_search_20260209` tool with `max_uses` 3 and
    `blocked_domains`, the strict `submit_summary_draft` tool, `fallbacks`;
  - the user message, which holds only `BookFacts` fields and the description (R7);
  - the `pause_turn` resume;
  - the result read from the tool input, with search-result and citation URLs collected;
  - `refusal` and an ending without the tool raise `AiDeclined`;
  - timeouts, connection errors, 429 and 5xx raise `AiUnavailable`;
  - the overall 30 s deadline.

  Then add `sources/summary_generator.py` (the protocol, `UnconfiguredGenerator`, the
  dependency) and `sources/claude.py`.
- [ ] T010 Add `AiNotConfigured`, `AiUnavailable`, `DraftLimitReached` and
  `DraftNotPossible(code)` to `services/errors.py`, with API status mapping in
  `api/errors.py` and `api/responses.py` (research R11). Wire `summary_generator` into
  `create_app`: Claude when a key is set, otherwise unconfigured.

## Phase 3: User Story 1 - Draft, review and accept (P1) 🎯 MVP

- [ ] T011 [US1] Write failing tests in `tests/integration/test_summary_drafts.py` for
  AC-01 to AC-08:
  - the button and hint;
  - the draft page contents;
  - nothing stored until saving;
  - `ai` vs `ai_edited` with model and sources;
  - the history wording and sources;
  - discard;
  - the no-JS POST flow and the HTMX partial;
  - forged, other-book and expired draft ids saving as `manual`.
- [ ] T012 [US1] Add `services/drafts.py` (`request_draft`, R9). Change
  `services/summaries.save_manual_summary` to `save_summary(…, draft_id=None)` using
  `origin_for`, and `persistence.catalog.save_summary` to take a model and sources.
- [ ] T013 [US1] Add `POST /catalog/books/{id}/summary/draft`, the `draft_id` on the save
  route, the `DraftForm` and `SummaryForm` Pydantic models, and the templates
  (`pages/summary.html`, `partials/summary_draft.html`: notice, sources, model, actions,
  allowance, HTMX indicator), plus the history wording.

## Phase 4: User Story 2 - Failures and limits (P1)

- [ ] T014 [US2] Write failing tests in `tests/integration/test_draft_failures.py` for
  AC-09 to AC-14:
  - each failure message, with the typed text kept and a hand save still working;
  - the allowance: counting rules, reset by day, per member, the 11th request refused;
    cached drafts don't count;
  - blocked-site, length and copy rejections;
  - other pages working while the generator hangs: the summary and My books pages with no
    AI call.
- [ ] T015 [US2] Implement the failure paths in `services/drafts.py` and the page
  messages; the allowance reservation before the call; the remaining count on the page.

## Phase 5: User Story 3 - Cache and regenerate (P2)

- [ ] T016 [US3] Write failing tests in `tests/integration/test_draft_cache.py` for AC-15
  to AC-18:
  - the same key reused by another member, with no count and the "drafted earlier" note;
  - 30-day expiry;
  - regenerate bypasses the cache and counts, and the old draft id still saves;
  - a changed title, authors or ISBN gets no old draft;
  - drafts never shown as summaries (entry page, API book, catalog).
- [ ] T017 [US3] Implement the cache lookup, regenerate and pruning in `services/drafts.py`.

## Phase 6: User Story 4 - Series suggestion (P2)

- [ ] T018 [US4] Write failing tests in `tests/integration/test_series_suggestion.py` for
  AC-19 to AC-21:
  - the hint, shown or hidden;
  - a name alone;
  - Edit book pre-filled and unsaved, with the notice;
  - saving through the spec 005 confirmation and the number conflict;
  - the unsaved-draft confirmation page.
- [ ] T019 [US4] Add the hint to the draft partial, `suggest_series` and `suggest_number`
  to Edit book (validated by a Pydantic query model), and
  `GET /catalog/books/{id}/summary/use-series`.

## Phase 7: User Story 5 - Entry page and Add a book (P3)

- [ ] T020 [US5] Write failing tests in `tests/integration/test_draft_entry_points.py` for
  AC-22 and AC-23:
  - the entry-page form, and another member's entry returning 404;
  - Add a book's `draft_summary` action keeps every field, fills the summary and a hidden
    id; saving the book stores `ai` or `ai_edited`;
  - a missing title or author gives a message;
  - failures and the allowance.
- [ ] T021 [US5] Add `POST /entries/{id}/summary-draft` and the entry template form; the
  Add a book action, template button and `summary_draft_id` passed through to the summary
  save.

## Phase 8: User Story 6 - JSON API (P3)

- [ ] T022 [US6] Write failing tests in `tests/contract/test_summary_drafts_contract.py`
  and `tests/integration/test_summary_drafts.py` for AC-24 to AC-26:
  - the response schema;
  - each error status and code;
  - regenerate;
  - `draft_id` on save;
  - CSRF.
- [ ] T023 [US6] Add `POST /api/v1/books/{id}/summary-drafts`, `SummaryDraftRequest`,
  `SummaryDraft` and `SummaryCreate.draft_id`. Update `openapi.yaml` and regenerate the
  baseline.

## Phase 9: Polish

- [ ] T024 [P] Add `tests/a11y/test_summary_drafts_a11y.py` (SC-005): axe at five widths
  for the draft, a failure, the series hint and the confirmation page; the keyboard
  journey draft → edit → save; the HTMX status announcement. Then add the CSS.
- [ ] T025 [P] Amend `specs/001-family-reading-list/contracts/ui-routes.md` with the rows
  in `contracts/ui-summary-drafts.md`, and the product spec's section 4 "In use so far"
  note.
- [ ] T026 [P] Document the Pi environment variable in `deploy/pi/` (README or env
  example: the name only, no value).
- [ ] T027 Run all the gates: ruff, format, mypy, pytest with coverage, the coverage
  script, a11y, perf, pip-audit and the OpenAPI export.

## Traceability

| AC | Tests |
|---|---|
| AC-01 – AC-08 | T011 (T004 for origin rules) |
| AC-09 – AC-14 | T014 (T004, T009 for checks and errors) |
| AC-15 – AC-18 | T016 |
| AC-19 – AC-21 | T018 |
| AC-22 – AC-23 | T020 |
| AC-24 – AC-26 | T022 |
| SC-005 | T024 |

## Dependencies & Execution Order

- Phase 1 → Phase 2 (T004–T010) → US1 → US2 → US3 → US4, US5, US6, which can run in any
  order after US3 → Polish.
- T004, T008 and T009 can run in parallel (different files).
- Every implementation task follows its failing tests.

## Implementation Strategy

- **MVP:** US1 + US2. Drafting, saving and failing safely on the Summary page are useful on
  their own.
- Then cache and regenerate, the series hint, the extra entry points and the API.
