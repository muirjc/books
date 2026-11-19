---
description: "Task list for 002 – Import an Author's Books"
---

# Tasks: Import an Author's Books

**Input**: Design documents from `/specs/002-author-book-import/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/openapi.yaml](contracts/openapi.yaml),
[contracts/ui-routes.md](contracts/ui-routes.md), [quickstart.md](quickstart.md)

**Tests**: REQUIRED. Constitution Principle V (NON-NEGOTIABLE) makes tests mandatory for every
feature: each acceptance criterion maps to at least one test, and test tasks come before the
implementation tasks they cover.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- Test tasks name the acceptance criteria they cover, e.g. `(AC-01, AC-02)`. Every test
  function carrying a criterion is decorated `@pytest.mark.ac("002/AC-xx")`.
- Implementation tasks name the functional requirements they deliver, e.g. `(FR-003)`
- Every JSON API route declares its error responses from `api/responses.py` and converts
  service results through `schemas/mappers.py`, as in spec 001 (001 research R16), so the
  generated OpenAPI document matches the contract.
- "Confirm it fails" on a test task means: run it and see it fail for the expected reason
  (missing route, module or behaviour), not because of an error in the test itself.
- Open Library is the only source (research R1). CI never calls it: tests use
  `FakeBookSource` (service and route tests) or recorded fixtures replayed through
  `httpx.MockTransport` (adapter tests).

## Path Conventions

- Single deployable: `src/book_tracker/`, `migrations/`, `tests/` at the repository root
  (`/home/jmuir/projects/books`), as laid out in [plan.md](plan.md#source-code-repository-root)
- Test layers: `tests/unit/`, `tests/integration/` (real PostgreSQL), `tests/contract/`
  (OpenAPI), `tests/external/` (new: recorded Open Library responses), `tests/a11y/`
  (marker `a11y`), `tests/perf/` (marker `perf`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Make the 001-only test and coverage tooling work for more than one feature.

- [X] T001 In `tests/conftest.py`, change `AC_ID` from `^001/AC-\d{2}$` to `^\d{3}/AC-\d{2}$` and update the error message to "must look like '002/AC-01'"; add a unit test in `tests/unit/test_ac_marker.py` that imports the pattern (`from tests.conftest import AC_ID`) and asserts `AC_ID.match("002/AC-01")` and `AC_ID.match("001/AC-35")` succeed while `"2/AC-1"`, `"002/AC-1"` and `"002/FR-01"` don't. Run it before changing the pattern and confirm the `002/AC-01` case fails. Testing the pattern directly avoids needing pytest's `pytester` plugin
- [X] T002 [P] In `tests/contract/conftest.py`, replace the single `CONTRACT` path with a `contract(feature: str) -> OpenAPI` helper (cached per feature) that loads `specs/<feature>/contracts/openapi.yaml`; keep the existing fixtures validating against `001-family-reading-list` and add a `contract_002` fixture for `002-author-book-import`. Existing contract tests must still pass unchanged
- [X] T003 [P] In `scripts/check_coverage.py`, add `src/book_tracker/services/imports.py` to `CRITICAL_MODULES` and change the docstring to cite both `specs/001-family-reading-list/plan.md` and `specs/002-author-book-import/plan.md` "Coverage-critical modules"
- [X] T004 [P] Create `src/book_tracker/sources/__init__.py` and `tests/external/__init__.py`, and the directory `tests/external/fixtures/open_library/`
- [X] T005 [P] Add a comment to `deploy/pi/.env.example` that, from spec 002, the app makes outbound HTTPS requests to `openlibrary.org` and needs no setting for it (research R16)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, domain objects, the source adapter and the cache, which every story uses.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests first

- [X] T006 Extend `tests/integration/test_migrations.py` so the upgrade → downgrade → upgrade round trip covers `0002_author_import`, and add checks that after upgrade the tables `book_source_ref` and `source_lookup_cache` exist with the named constraints from data-model.md, and after downgrade to `0001_initial` they are gone. Confirm it fails
- [X] T007 [P] Write `tests/integration/test_import_constraints.py`: inserting two `book_source_ref` rows with the same (`source`, `source_work_id`) violates `book_source_ref_source_work_key`; two rows for one book and source violate `book_source_ref_book_source_key`; `source_work_id='abc'` violates `book_source_ref_open_library_id_format`; `source='google_books'` violates the source CHECK; a cache row with `expires_at <= fetched_at` violates its CHECK; deleting a book deletes its source ref (Principle VI). Confirm it fails
- [X] T008 [P] Write `tests/unit/test_matching.py` for `domain/matching.py`: `normalize_title` (case, NFKC, punctuation, whitespace, leading "The"/"A"/"An" dropped only as a whole word: "The Way of Kings" == "way of kings", "Anathem" unchanged); `normalize_person_name`; `isbn10_to_13` ("0765326353" → "9780765326355", bad check digit → `None`, ISBN-13 passes through after validation); `merge_duplicate_works` keeps the most-editions id, earliest year and union of ISBN-13s (research R6). Confirm it fails
- [X] T009 [P] Write `tests/unit/test_rate_limit.py` for `sources/rate_limit.py`: with an injected clock and sleep, two acquisitions 0.5 s apart cause a 1.5 s sleep; acquisitions 2.5 s apart cause none; and an acquisition whose wait would end after the caller's deadline raises `SourceUnavailable` at once, without sleeping (FR-016, FR-018; research R2, R9). Confirm it fails
- [X] T010 Record the fixtures with a new script `scripts/record_open_library_fixtures.py` (run by hand, never in CI; documented in its docstring; uses the same User-Agent as the adapter and sends only author names and keys) and commit its output to `tests/external/fixtures/open_library/`: `authors_brandon_sanderson.json` (two matches), `authors_single.json` (one match, e.g. "Ursula K. Le Guin"), `authors_none.json` (no match), `works_OL1394865A.json` (the 239-work list, fields as in research R3), and hand-made `works_duplicates.json` (two works with the same title and first author), `works_large_page1.json` / `works_large_page2.json` (`numFound` 2,500), `works_malformed.json` (one work missing `title`, one with `author_name` absent), `works_unknown_author.json` (`numFound` 0), `works_repeated_author.json` (a work whose `author_name` lists the same person twice) and `works_long_values.json` (a 400-character title and a 250-character name). Trim `authors_single.json` to one author if the live search returns more
- [X] T011 Write `tests/external/test_open_library.py` replaying the fixtures with `httpx.MockTransport` (FR-015, FR-016, FR-018, FR-020, SC-005):
  - author search parses key, name, dates, top work and work count;
  - works parsing converts ISBN-10s and drops invalid ISBNs;
  - malformed works are dropped and logged, not fatal;
  - paging stops after 2 pages of 1,000 with `total` = 2,500 and `truncated`;
  - every request goes only to the configured base URL with only `q`, `author_key`, `fields`, `limit` and `page` parameters, a `User-Agent` of exactly `FamilyBookTracker/<version>`, and no `From`, `Referer` or `Cookie` header (FR-015, FR-018, research R2);
  - a 503, a 429, a connection error and a read timeout (a transport that sleeps past a 0.1 s test timeout) each raise `SourceUnavailable`.

  Confirm it fails
  Also (review of PR #9): the works list's author comes from the response (name at the `author_key` position, `work_count` = `numFound`) when no search result is given; `works_unknown_author.json` raises `SourceNotFound`; a repeated author is listed once; titles and names are NFKC-normalized and a 400-character title is cut to 300 and a 250-character name to 200 at a word boundary with "…"; and a two-page list whose second request would exceed the 10 s request budget fails with `SourceUnavailable` (FR-016, FR-020, FR-021, FR-022; research R3, R6, R9).
- [X] T012 [P] Write `tests/integration/test_source_cache.py` for `persistence/source_cache.py`: put then get returns the payload; a row past `expires_at` is not returned; putting a row deletes expired rows; a second put for the same key upserts (FR-017). Confirm it fails
- [X] T013 [P] Add to `tests/integration/test_reading_isolation.py` (or a new `tests/integration/test_book_ids_on_list.py`): `ReadingEntryRepository(db, alice).book_ids_on_list([b1, b2, b3])` returns only the books on Alice's list, never Ben's, and an empty input returns an empty set (Principle I; this module must stay at 100% coverage). Confirm it fails

### Implementation

- [X] T014 Add `BookSourceRef` and `SourceLookupCache` to `src/book_tracker/persistence/models.py` with every constraint and index named exactly as in data-model.md, and write the reversible migration `migrations/versions/0002_author_import.py` (`down_revision = "0001_initial"`; downgrade drops `source_lookup_cache` then `book_source_ref`, with a comment pointing to the backup step in data-model.md). Add both tables to `TABLES` in `tests/conftest.py` so they're truncated between tests. Makes T006, T007 pass
- [X] T015 [P] Create `src/book_tracker/domain/imports.py` (frozen, slotted dataclasses `AuthorCandidate`, `WorkCandidate` (with `alias_ids`), `WorkList`, `ImportedBook`, `SkippedBook` (with `reason` `on_list` or `duplicate`), `ImportResult`, and the `WorkState` enum `NEW`/`IN_CATALOG`/`ON_MY_LIST`, fields as in data-model.md) and `src/book_tracker/domain/matching.py`. Makes T008 pass (FR-004, FR-005)
- [X] T016 [P] Create `src/book_tracker/sources/rate_limit.py`: an `asyncio.Lock`-guarded limiter that spaces calls at least `min_interval` (default 2.0 s) apart, with injectable clock and sleep, and `acquire(deadline)` that raises `SourceUnavailable` if the wait would end after `deadline`. Makes T009 pass (FR-016, FR-018)
- [X] T017 Create `src/book_tracker/sources/base.py` (`BookSource` Protocol with `async search_authors(name: str) -> list[AuthorCandidate]` and `async author_works(author_key: str) -> WorkList`; `SourceUnavailable(Exception)` with a `reason` attribute; `SourceNotFound` for an unknown author key) and `src/book_tracker/sources/open_library.py`: an `OpenLibrarySource` built from settings and an `httpx.AsyncClient`. Requirements:
  - parse responses with private Pydantic models, never passing raw dicts out of `sources/`;
  - give each call one 10 s budget (`settings.source_timeout_seconds`), covering the limiter wait (`acquire(deadline)`) and the request (`asyncio.timeout`);
  - map timeouts, transport errors, 429 and 5xx to `SourceUnavailable`;
  - fetch at most 2 pages of `limit=1000` and merge duplicates with `merge_duplicate_works`;
  - log kind, status and duration only.

  Makes T011 pass (FR-015, FR-016, FR-018, FR-020; research R2–R4, R9)
  Also: normalize and cut titles and names as in research R6 (FR-022); remove repeated authors on a work (FR-021); take the author header as in research R3 with no third request; raise `SourceNotFound` for an unknown key; and apply the 10 s budget **per member request** across all calls and limiter waits (`author_works` takes one deadline for both pages).
- [X] T018 [P] Add to `src/book_tracker/settings.py`: `openlibrary_base_url: str = "https://openlibrary.org"`, `source_timeout_seconds: float = 10.0` (no contact setting: research R2); add a unit test in `tests/unit/test_settings.py` for the defaults and environment overrides first (FR-016)
- [X] T019 [P] Create `src/book_tracker/persistence/source_cache.py` with `get(db, source, kind, key, now)`, `put(db, source, kind, key, payload, now, ttl=timedelta(hours=24))` (upsert, then delete rows with `expires_at < now`), and JSON (de)serialization of `AuthorCandidate` lists and `WorkList` to and from the `payload` column. Makes T012 pass (FR-017; research R5)
- [X] T020 [P] Add `book_ids_on_list(self, book_ids: Collection[uuid.UUID]) -> set[uuid.UUID]` to `ReadingEntryRepository` in `src/book_tracker/persistence/readings.py`, built on `self._owned()` so it is always filtered by the bound user. Makes T013 pass (Principle I)
- [X] T021 Create `tests/fakes.py` with `FakeBookSource` (configurable authors, works lists and errors, plus a call log), and wire the source into the app: `create_app` in `src/book_tracker/main.py` sets `app.state.book_source = OpenLibrarySource(settings, client)` and closes the httpx client on shutdown; add a `book_source` fixture in `tests/conftest.py` that swaps in a `FakeBookSource` for the test and restores it afterwards; add a `BookSourceDep` dependency in a new `src/book_tracker/sources/dependencies.py` reading `request.app.state.book_source`, so `auth/dependencies.py`, which must keep 100% coverage, doesn't change
  Also (review finding 3): `create_app(settings, book_source=None)` uses the source it's given; with none, it builds `OpenLibrarySource` only when `settings.environment != "test"`, and under test installs a source whose every call fails. Add a FastAPI lifespan that opens and closes the `httpx.AsyncClient` (research R18). Pass `FakeBookSource` to the app built by `tests/a11y/conftest.py::live_server`. Add a guard test in `tests/unit/test_no_live_calls.py` that patches `OpenLibrarySource.__init__` to fail and builds the app with test settings (Principle V).

**Checkpoint**: schema migrated, adapter and cache tested, fake source available: user story work can begin

---

## Phase 3: User Story 1 - Find an author's books and add the ones I choose (Priority: P1) 🎯 MVP

**Goal**: a member searches an author, sees their works marked by state, ticks some, picks a
status and confirms; the books go onto that member's list only, with new catalog books
linked to Open Library.

**Independent Test**: with `FakeBookSource` serving the recorded Sanderson works, a member
searches, ticks three works and confirms; exactly those three are on their list, the catalog
holds one copy of each, and no other member's list changed.

### Tests for User Story 1 ⚠️

> **Write these tests FIRST and confirm they FAIL for the expected reason before implementation.**
> Tag each test with its feature-qualified AC ID, e.g. `@pytest.mark.ac("002/AC-01")`.

- [X] T022 [P] [US1] Contract tests in `tests/contract/test_imports_contract.py` against `contract_002`: `GET /api/v1/import/authors?q=`, `GET /api/v1/import/authors/{key}/works`, and `POST /api/v1/me/imports` responses validate (200, 201, 401, 403 for a missing CSRF header, 404 `author_not_found`, 409 `results_expired`, 422 including 501 `work_keys`, 503 `source_unavailable`), and `ImportResult.skipped` carries `reason` (AC-01, AC-02, AC-13, AC-21, AC-23)
- [X] T023 [P] [US1] Service tests in `tests/integration/test_imports_service.py` for `services/imports.py` with `FakeBookSource`:
  - search returns the author candidates (AC-01);
  - `list_works` returns each work with `NEW`, `IN_CATALOG` or `ON_MY_LIST` (AC-04, AC-17);
  - a catalog book whose ISBN-13 is one of a work's ISBNs is `IN_CATALOG` (AC-15);
  - a catalog book with the same normalized title and first author is `IN_CATALOG`;
  - `confirm_import` adds exactly the selected works to the member's list with the chosen status, Finished by default (AC-02, AC-19);
  - it reuses an existing author by case-insensitive name (AC-05) and keeps co-authors in order, reusing existing ones (AC-06);
  - it writes `book_source_ref` with source, work id, importer and time, and sets `book.created_by` to the importer (AC-07);
  - new books have no series, number or ISBN (AC-14);
  - nothing is written by search or list (AC-03, FR-007);
  - a work already on the list is skipped and reported (AC-17, FR-012);
  - an expired cache row gives `results_expired`, and a work id not in the cached list gives a validation error (research R8);
  - `list_works` with `sort="title"` (the default) orders by normalized title, and with `sort="year"` by first published year, works without a year last, then by title, so the API matches the contract from US1 on (contracts/openapi.yaml).
  Also (review of PR #9):
  - two selected works that resolve to one catalog book add it once and report the other as `duplicate`; a work listing an author twice adds the author once; the rest of the selection is still added (AC-22, FR-021);
  - an author whose stored name differs from Open Library's only by Unicode form (precomposed vs decomposed accent) is reused, not duplicated (AC-05, FR-022);
  - a 400-character title is stored cut to 300 (FR-022);
  - a book matched through any of a merged work's `alias_ids` is `IN_CATALOG` (research R6);
  - a cache row with under 1 hour left is refreshed when the list is shown (research R8);
  - 501 selected works are refused with "You can add up to 500 books at a time" and nothing is added (AC-21, FR-014);
  - an unknown author key gives `SourceNotFound` (AC-23).
- [X] T024 [P] [US1] Concurrency tests in `tests/integration/test_imports_concurrency.py` (AC-16, SC-003; research R7):
  - **Deterministic race:** Alice lists the works; then, in a separate session, Ben's confirm of the same new work commits; then Alice confirms. Afterwards there is one `book`, one `book_source_ref` and an entry on each list, and Alice's summary says the book wasn't new to the catalog.
  - **Serialized confirms:** a session holding `pg_advisory_xact_lock(hashtext('book_tracker.import'))` makes a confirm wait until it commits (assert the confirm doesn't finish while the lock is held).
  - **No deadlock:** two confirms with overlapping new co-authors in opposite orders, via `asyncio.gather`, both succeed.
  - **Backstop:** call the per-work insert step (`services/imports._add_new_work`, see T031) directly, without the lock, after another session has committed a `book_source_ref` for the same work; it rolls back its savepoint on `book_source_ref_source_work_key` and returns the existing book. No test-only flag in production code.
- [X] T025 [P] [US1] Cross-user tests in `tests/integration/test_imports_isolation.py`: after Alice imports, Ben's list is unchanged, Ben's works list shows those books as `IN_CATALOG` (not `ON_MY_LIST`), and no import endpoint accepts a user id: sending `user_id` in the body is rejected by `additionalProperties: false`. The same for the page routes: when Ben loads `GET /import/authors/{key}`, Alice's imported books show "In the family catalog", never "Already on your list"; when Ben confirms with `POST /import/authors/{key}`, entries are added to Ben's list only, and Alice's list keeps the same entries and statuses (AC-18, Principle I)
  Cover every import endpoint explicitly (Principle I): `GET /api/v1/import/authors/{key}/works` as Ben shows Alice's books as `in_catalog`, and `POST /api/v1/me/imports` as Ben adds only to Ben's list, as well as the page routes.
- [X] T026 [P] [US1] Failure tests in `tests/integration/test_imports_failures.py`: with `FakeBookSource` raising `SourceUnavailable`, the API returns 503 `source_unavailable`, the page shows "The book site couldn't be reached. Try again later, or add the book by hand," with a link to `/books/add`, and nothing is written; other pages still load (AC-13, SC-004)
- [X] T027 [P] [US1] UI tests in `tests/integration/test_import_pages.py`:
  - `/import` renders the search form; a non-Admin member can use it (FR-014);
  - `/import/authors?q=` with one match redirects to `/import/authors/{key}`, using `HX-Redirect` for HTMX;
  - the works page shows the state badges, has no checkbox for "Already on your list" rows, and has status radios defaulting to Finished;
  - `POST /import/authors/{key}` with the CSRF token renders the summary "Added N books to your list (M new to the family catalog)" (AC-01, AC-02, AC-04, AC-17, AC-19, FR-012);
  - a POST without CSRF is refused;
  - a POST with nothing ticked shows a field error.
- [X] T028 [P] [US1] Book-page test in `tests/integration/test_import_pages.py`: an imported book's entry page and catalog edit page show "Imported from Open Library" linking to `https://openlibrary.org/works/<id>` (AC-07, FR-009)

### Implementation for User Story 1

- [X] T029 [P] [US1] Create `src/book_tracker/persistence/imports.py`: `find_books_by_source_ids(db, source, ids) -> dict[str, uuid.UUID]`, `find_books_by_isbns(db, isbns) -> dict[str, uuid.UUID]`, `books_by_first_author_name(db, name) -> list[tuple[uuid.UUID, str]]` (id, title) using `lower(author.name)` and `book_author.position = 1`, `find_authors_by_names(db, names) -> dict[str, uuid.UUID]` (one query on `lower(name)`), `insert_source_ref(db, book_id, source, work_id, actor_id, now)`, and `source_ref_for_book(db, book_id)` (FR-005, FR-009, SC-006)
  Pass id and ISBN sets as one array parameter (`= ANY(:ids)`), never an expanded `IN (...)`, and match source refs on a work's id or any of its `alias_ids` (research R6, review finding 6); test with 5,000 ISBNs.
- [X] T030 [P] [US1] Create `src/book_tracker/schemas/imports.py`: `AuthorCandidateOut`, `AuthorCandidateList`, `WorkCandidateOut`, `WorkList`, `ImportRequest` (`model_config = ConfigDict(extra="forbid")`, `author_key` pattern `^OL[0-9]+A$`, 1–500 unique `work_keys` matching `^OL[0-9]+W$`, `status: ReadingStatus = FINISHED`), `ImportedBookOut`, `SkippedBookOut` (with `reason`), `ImportResult` (`added`, `skipped`), an `AuthorSearchQuery` form/query model (`q` 1–200 chars), a `WorksViewForm` for the page routes that treats blank `sort` and `q` as absent (review finding 9), and mappers from domain objects in `src/book_tracker/schemas/mappers.py` (FR-001, FR-003, FR-013; contracts/openapi.yaml)
- [X] T031 [US1] Create `src/book_tracker/services/imports.py`:
  - `search_authors(db, source, name, now)`: cache first, then source; cache put.
  - `list_works(db, source, user_id, author_key, now)`: cache first, then source. Compute each work's state via `persistence/imports.py` and `ReadingEntryRepository(db, user_id).book_ids_on_list`.
  - `confirm_import(db, user_id, request, now)`:
    - read the cached works; refuse with `ConflictError("results_expired", ...)` if the cache row has expired, and with `ValidationFailed` for unknown work keys;
    - for each work, in a savepoint: find or create its authors via `catalog_service.create_author`, treating `author_exists` as "reuse `existing_id`";
    - create the book with title and author ids only, via `catalog_service.create_book`;
    - insert the source ref; on `book_source_ref_source_work_key`, roll back the savepoint and reuse the existing book;
    - then add the entry via `ReadingEntryRepository`, using `readings.apply_status_change` for `times_read` and skipping books already on the list;
    - return an `ImportResult`.
  - Keep it fast (SC-006): look up existing authors for all selected works in one query (`find_authors_by_names`) and work out catalog matches once for the whole selection; use a savepoint per work only around the inserts. No query may run once per author per work.

  The user id always comes from the caller's session argument; there is no other input for it. Must reach 100% line coverage (FR-001, FR-003, FR-005, FR-007 to FR-014, FR-017; research R6–R8, R10). Makes T023–T025 pass
  Put the per-work step (create the book and its source ref in a savepoint, reusing the existing book on `book_source_ref_source_work_key`) in its own function, `_add_new_work`, so T024 can test the database backstop without the lock.
  Also (review of PR #9; research R7): `confirm_import` first takes `pg_advisory_xact_lock(hashtext('book_tracker.import'))`, then works out matches afresh inside the lock; removes duplicate targets (reported as `duplicate`) and repeated author ids; inserts each new book with its source ref in a savepoint; inserts each reading entry in its own savepoint, treating `reading_entry_user_book_key` as "already on the list"; refuses more than 500 works (FR-014); and `list_works` refreshes a cache row with under 1 hour left (research R8). (FR-021, FR-022)
- [X] T032 [US1] Map `ConflictError` with code `results_expired` to 409 in `src/book_tracker/api/errors.py` (the existing conflict handler may already do this; confirm with T022), `SourceNotFound` → 404 `author_not_found` ("No such author on Open Library"), and add a `SourceUnavailable` → 503 `source_unavailable` problem mapping (with the spec's message as `title`) for both the API and `web` error rendering; add both responses to `src/book_tracker/api/responses.py` (FR-016; AC-13)
- [X] T033 [US1] Create `src/book_tracker/api/imports.py` with the three operations exactly as in contracts/openapi.yaml (`GET /import/authors`, `GET /import/authors/{author_key}/works` with `sort` (`title` or `year`, both applied from US1) and `q` (accepted; title filtering arrives in US3, until then it is ignored and documented as such in the route's docstring), `POST /me/imports` requiring the CSRF header and `ApiUser`), and include its router in `src/book_tracker/main.py` (FR-001, FR-003, FR-007, FR-013, FR-014). Makes T022, T026 (API part) pass
- [X] T034 [US1] Create `src/book_tracker/web/routes/imports.py` and the templates:
  - `src/book_tracker/web/templates/pages/import_search.html`: the search form;
  - `pages/import_works.html`: works table with caption, per-row checkbox and label, state badges, status `<fieldset>` of radio buttons defaulting to Finished, and a confirm button;
  - `partials/import_works.html`: fragment `#import-works`;
  - `pages/import_summary.html`: the summary inside an `aria-live="polite"` region;
  - the unreachable message with a link to `/books/add`.

  `/import/authors?q=` redirects straight to the works page when there's exactly one match; its multi-match chooser is completed in US2, so until then it lists the names as links. Route rules as in contracts/ui-routes.md. Include the router in `main.py` and add "Import from Open Library" to the main navigation in `src/book_tracker/web/templates/base.html` and a link on `pages/add_book.html` (FR-001, FR-003, FR-005, FR-012, FR-013, FR-019). Makes T026 (page part), T027 pass
  Also: add the read-only `POST /import/authors/{key}/view` route (CSRF-checked) that re-renders `#import-works` from the ticked `work` values in the body (research R12; built out in US3); show "No such author on Open Library" for an unknown key (AC-23); show "You can add up to 500 books at a time" when more are ticked (AC-21); and list skips as "Already on your list" or "Same book as another one you ticked" in the summary (FR-012, FR-021).
- [X] T035 [US1] Show "Imported from Open Library" with a link to `https://openlibrary.org/works/<id>` on `src/book_tracker/web/templates/pages/entry.html` and `pages/edit_book.html`, reading the ref through `persistence/imports.source_ref_for_book` via the catalog service (FR-009). Makes T028 pass
- [X] T036 [US1] Regenerate the committed OpenAPI baseline: `uv run python -m book_tracker.export_openapi > specs/001-family-reading-list/contracts/openapi.generated.json`, check that `tests/contract/test_generated_baseline.py` passes, and check that the diff only adds the three operations and their schemas (no breaking change)

**Checkpoint**: User Story 1 works on its own: search → (single match) → works → confirm → summary, with isolation, concurrency and failure handling

---

## Phase 4: User Story 2 - Pick the right author when names are shared (Priority: P2)

**Goal**: when a name matches several authors, the member sees each with distinguishing
details and picks one; with no match, they're pointed to adding by hand.

**Independent Test**: with the recorded two-match "Brandon Sanderson" response, the member
sees both authors with birth year, best-known title and work count, picks the second, and
sees only that author's works.

### Tests for User Story 2 ⚠️

- [X] T037 [P] [US2] UI tests in `tests/integration/test_import_author_choice.py`: with `FakeBookSource` returning two candidates, `/import/authors?q=brandon sanderson` lists both with birth/death years, top work and number of works, each linking to its works page, and doesn't redirect; following the second link lists only that author's works (AC-08, FR-002)
- [X] T038 [P] [US2] No-match tests in `tests/integration/test_import_author_choice.py`: with no candidates, the page says "No author found" with a link to `/books/add`, the API returns `{"authors": []}`, and nothing is written (AC-09)

### Implementation for User Story 2

- [X] T039 [US2] Create `src/book_tracker/web/templates/pages/import_authors.html` (a list of candidates: name, "born … – died …" when present, "best known for <top work>", "<n> works", each a link to `/import/authors/{key}`) and the "No author found" state with a link to `/books/add`; update `src/book_tracker/web/routes/imports.py` to render it for zero or several matches (FR-002). Makes T037, T038 pass

**Checkpoint**: User Stories 1 and 2 both work independently

---

## Phase 5: User Story 3 - Import a long bibliography without fuss (Priority: P3)

**Goal**: for prolific authors, the list shows each work once, can be sorted and filtered by
title, supports "Select all shown", and says when it's capped at 2,000.

**Independent Test**: with a 300-work fake list, the member filters by a word in the title,
chooses "Select all shown" and confirms; only the shown, selectable works are added.

### Tests for User Story 3 ⚠️

- [X] T040 [P] [US3] Service tests in `tests/integration/test_imports_service.py`: `list_works` with `q="mist"` keeps only works whose title contains "mist" ignoring case; combined with `sort="year"` the filtered works keep the year order tested in T023; an empty result says so rather than erroring (AC-10, FR-006)
- [X] T041 [P] [US3] De-duplication test in `tests/integration/test_imports_service.py` using the `works_duplicates.json` shape through `FakeBookSource`: the two entries appear once, under the id with more editions (AC-12, FR-004)
- [X] T042 [P] [US3] Cap test: with a `WorkList` of `total` 2,500 and 2,000 works, the API returns `truncated: true` and `total: 2500`, and the page shows "Showing the first 2,000 of 2,500 works. To add a book beyond these, add it by hand." with a link to `/books/add` (AC-20, FR-020)
- [X] T043 [P] [US3] UI tests in `tests/integration/test_import_pages.py`:
  - an HTMX `POST /import/authors/{key}/view` with `sort=year`, `q=mist` and two ticked `work` values in the body returns the `#import-works` fragment, sorted and filtered, with those works still ticked;
  - `select=shown` ticks every shown work whose state isn't `ON_MY_LIST`, up to 500, ticks no hidden work, and with 600 shown ticks the first 500 and says so (AC-10, AC-11); blank `sort` and `q` behave as absent (review finding 9);
  - confirming after a filtered select-all adds only those works (US3 independent test).

### Implementation for User Story 3

- [X] T044 [US3] Implement title filtering (`q`, case-insensitive substring of the title) in `list_works` in `src/book_tracker/services/imports.py`, applied after state is computed and combined with the sorting already done in T031, and pass `q` through `src/book_tracker/api/imports.py` (FR-006). Makes T040, T041 pass (merging is already done in the adapter by T017; T041 confirms it end to end)
- [X] T045 [US3] Add to `src/book_tracker/web/templates/partials/import_works.html` and `web/routes/imports.py`:
  - sort select and title filter inputs that re-render `#import-works` via `hx-post` to `/import/authors/{key}/view`, with `hx-include="[name=work]:checked, [name=status]:checked"` so selections travel in the body and survive;
  - a "Select all shown" button (`hx-post` with `select=shown`, at most 500 ticked);
  - a count of ticked works in an `aria-live="polite"` region;
  - the truncation note (FR-006, FR-020).

  Makes T042, T043 pass

**Checkpoint**: all user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility, performance, coverage, contract and docs across all stories

- [ ] T046 [P] Add the import pages (search, author choice, works list with a fake 30-work list, summary, unreachable message) to `tests/a11y/test_axe_pages.py`, a keyboard journey (search → choose author → tick two works with Space → choose status → confirm, all without a mouse) to `tests/a11y/test_keyboard_journeys.py`, and the works page at phone width (no horizontal scroll) to `tests/a11y/test_responsive.py`; fix any findings in the templates and `src/book_tracker/web/static/css/app.css` (FR-019)
  Also (review findings 1 and 3): these tests run against the live uvicorn server with `FakeBookSource` injected (T021), so no Open Library call is made. Add one test that ticks 500 works and confirms through the live server, proving the request fits uvicorn/h11's header limit and Starlette's 1,000-field form limit (AC-21, SC-006).
- [ ] T047 [P] Write `tests/perf/test_import_perf.py` (marker `perf`): with the 5,000-book seed and a warm cache of 300 works for one author, rendering `/import/authors/{key}` and `GET /api/v1/import/authors/{key}/works` each have p95 under 1 s over 30 runs (SC-002); and `POST /api/v1/me/imports` with 200 new works (fresh database each run, 5 runs) finishes in under 5 s in CI, a stand-in for the Pi's 10 s (SC-006); and the same with the maximum 500 new works (1 run) finishes in under 12 s in CI, a stand-in for the Pi's 25 s (SC-006)
- [ ] T048 [P] Add a test in `tests/external/test_open_library.py` that records every outgoing request across a full search → works → confirm flow and asserts none contains the member's login, display name, session cookie, notes or status, and that confirm makes no request at all (SC-005, FR-015, research R8)
- [ ] T049 Run `uv run pytest --cov --cov-report=json && uv run python scripts/check_coverage.py` and bring `services/imports.py` and `persistence/readings.py` to 100% line coverage and the total to at least 85%
- [ ] T050 Run the full gate list from CLAUDE.md "Build & Test" (`ruff check`, `ruff format --check`, `mypy --strict src`, pytest, `-m a11y`, `-m perf`, `pip-audit`, `export_openapi`) and fix anything that fails
- [ ] T051 [P] Update `docs/Family Book Tracker – Specification.md`:
  - section 10.4 or "Outbound internet": the app now calls `openlibrary.org` over HTTPS, and requests carry only the app name and version;
  - the "Where the information comes from" table: Open Library is in use for author import, and Google Books is deferred (decision books-zl3, follow-up books-395).
- [ ] T052 [P] Add a short "Import from Open Library" section to `deploy/pi/README.md` section 9 (Routine maintenance): no setup needed beyond outbound HTTPS; what the "couldn't be reached" message means and that it never blocks adding books by hand
- [ ] T053 Walk through [quickstart.md](quickstart.md) "Manual walk-through" against the real Open Library on a local instance and record the results (pass/fail per step) in the PR description; after deploying, time a 200-book confirm on the Pi against the 10 s budget (SC-006)

---

## Traceability

| Requirement | Tasks |
|---|---|
| AC-01 | T022, T023, T027, T031, T033, T034 |
| AC-02 | T022, T023, T027, T031, T034 |
| AC-03 | T023, T031 |
| AC-04 | T023, T027, T031 |
| AC-05 | T023, T031 |
| AC-06 | T023, T031 |
| AC-07 | T023, T028, T031, T035 |
| AC-08 | T037, T039 |
| AC-09 | T038, T039 |
| AC-10 | T023, T031, T040, T043, T044, T045 |
| AC-11 | T043, T045 |
| AC-12 | T008, T041, T015, T017 |
| AC-13 | T011, T022, T026, T032, T034 |
| AC-14 | T023, T031 |
| AC-15 | T008, T023, T029, T031 |
| AC-16 | T007, T024, T014, T031 |
| AC-17 | T013, T023, T027, T020, T031, T034 |
| AC-18 | T013, T025, T020, T031 |
| AC-19 | T023, T027, T031, T034 |
| AC-20 | T011, T042, T017, T045 |
| AC-21 | T022, T023, T030, T031, T034, T046 |
| AC-22 | T010, T011, T023, T017, T031, T034 |
| AC-23 | T010, T011, T022, T023, T017, T032, T034 |
| FR-001 | T030, T031, T033, T034 |
| FR-002 | T037, T039 |
| FR-003 | T029, T030, T031, T033, T034 |
| FR-004 | T008, T015, T017, T041 |
| FR-005 | T015, T029, T031, T034 |
| FR-006 | T040, T043, T044, T045 |
| FR-007 | T023, T031, T033 |
| FR-008 | T023, T031 |
| FR-009 | T014, T029, T031, T035 |
| FR-010 | T023, T031 |
| FR-011 | T011, T017, T023, T031 |
| FR-012 | T023, T027, T031, T034 |
| FR-013 | T025, T030, T031, T033, T034 |
| FR-014 | T023, T027, T030, T031, T033 |
| FR-015 | T011, T017, T048 |
| FR-016 | T011, T017, T018, T026, T032 |
| FR-017 | T012, T019, T031 |
| FR-018 | T009, T011, T016, T017 |
| FR-019 | T034, T046 |
| FR-020 | T011, T017, T042, T045 |
| FR-021 | T011, T017, T023, T031, T034 |
| FR-022 | T011, T017, T023 |
| SC-001 | T053 |
| SC-002 | T047 |
| SC-003 | T024 |
| SC-004 | T026 |
| SC-005 | T011, T048 |
| SC-006 | T029, T031, T047, T053 |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001 first (other test tasks rely on the widened tag)
- **Foundational (Phase 2)**: depends on Setup; blocks all user stories. Within it: T006–T013
  (tests) before T014–T021; T014 before T019, T020 and T029; T015 before T017 and T019;
  T016 and T018 before T017; T017 and T019 before T021
- **User Stories (Phase 3+)**: all depend on Phase 2
  - US1 (P1) first: it provides the services, API and pages US2 and US3 extend
  - US2 and US3 can then proceed in parallel; they touch different templates, apart from
    `web/routes/imports.py`, so merge them one after the other
- **Polish (Phase 6)**: after the desired stories

### User Story Dependencies

- **User Story 1 (P1)**: after Phase 2; no dependency on other stories
- **User Story 2 (P2)**: after US1's T034 (extends the author-choice route); independently
  testable with the two-match fixture
- **User Story 3 (P3)**: after US1's T031 and T034 (extends `list_works` and the works
  partial); independently testable with a large fake list

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Persistence and schemas (T029, T030) before the service (T031); service before API and pages
- T036 (baseline regeneration) after every API change in US1; re-run it after T044 if the
  API surface changes

### Parallel Opportunities

- Setup: T002–T005 in parallel after T001
- Foundational tests: T007, T008, T009, T012 and T013 in parallel; T010 then T011
- Foundational implementation: T015, T016, T018, T019 and T020 in parallel after T014
- US1 tests: T022–T028 in parallel; then T029 and T030 in parallel
- US2 and US3 phases in parallel once US1 is done
- Polish: T046, T047, T048, T051 and T052 in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract tests in tests/contract/test_imports_contract.py"
Task: "Service tests in tests/integration/test_imports_service.py"
Task: "Concurrency test in tests/integration/test_imports_concurrency.py"
Task: "Cross-user tests in tests/integration/test_imports_isolation.py"
Task: "Failure tests in tests/integration/test_imports_failures.py"
Task: "UI tests in tests/integration/test_import_pages.py"

# Then the persistence and schema layers together:
Task: "Create src/book_tracker/persistence/imports.py"
Task: "Create src/book_tracker/schemas/imports.py"
```

## Parallel Example: Foundational

```bash
Task: "Constraint tests in tests/integration/test_import_constraints.py"
Task: "Matching unit tests in tests/unit/test_matching.py"
Task: "Rate limiter unit tests in tests/unit/test_rate_limit.py"
Task: "Source cache tests in tests/integration/test_source_cache.py"
Task: "book_ids_on_list isolation test"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run the US1 tests and quickstart steps 1–2 and 5–9 with a
   single-match author (e.g. "Ursula K. Le Guin")
5. Deploy to the Pi if ready: `git pull`, `docker compose pull && docker compose up -d`
   (migration 0002 runs at start-up)

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → test → deploy (MVP: single-match authors, full import)
3. US2 → test → deploy (shared names, no-match message)
4. US3 → test → deploy (sort, filter, select all, 2,000 cap)
5. Polish → a11y, perf, docs → close books-0tw

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail for the expected reason before implementing
- Every commit leaves the test suite passing
- Stop at any checkpoint to validate story independently
- Never call the live Open Library from tests or CI; re-record fixtures with
  `scripts/record_open_library_fixtures.py` only by hand
