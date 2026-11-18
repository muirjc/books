---
description: "Task list for 001 – Family Reading List"
---

# Tasks: Family Reading List

**Input**: Design documents from `/specs/001-family-reading-list/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/openapi.yaml](contracts/openapi.yaml),
[contracts/ui-routes.md](contracts/ui-routes.md), [quickstart.md](quickstart.md)

**Tests**: REQUIRED. Constitution Principle V (NON-NEGOTIABLE) makes tests mandatory for every
feature: each acceptance criterion maps to at least one test, and test tasks come before the
implementation tasks they cover.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Test tasks name the acceptance criteria they cover, e.g. `(AC-01, AC-02)`. Every test
  function carrying a criterion is decorated `@pytest.mark.ac("001/AC-xx")`.
- Implementation tasks name the functional requirements they deliver, e.g. `(FR-003)`
- Every JSON API route declares its error responses from `api/responses.py` and converts
  service results with `schemas/mappers.py` (research R16). Without this, the generated
  OpenAPI document won't match the contract and T114 and the CI contract check fail.
- "Confirm it fails" on a test task means: run it, see it fail for the expected reason
  (missing route, missing module, wrong behaviour), not an import error in the test itself.

## Path Conventions

- Single deployable: `src/book_tracker/`, `migrations/`, `tests/` at the repository root
  (`/home/jmuir/projects/books`), exactly as laid out in [plan.md](plan.md#source-code-repository-root)
- Test layers: `tests/unit/`, `tests/integration/` (real PostgreSQL via testcontainers),
  `tests/contract/` (OpenAPI), `tests/a11y/` (marker `a11y`), `tests/perf/` (marker `perf`).
  No `tests/external/` layer: this feature calls no external services.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Make `/home/jmuir/projects/books` its own git repository, so `.github/workflows/ci.yml`, pull requests and the spec gate work (Constitution: CI gates and Reviews). Done 2026-11-18: `git init`, branch `master`, remote `origin` = `https://github.com/muirjc/books`
- [X] T002 Create `pyproject.toml` for a uv project named `book-tracker` (src layout, package `book_tracker`, `requires-python = ">=3.12"`, console script `book-tracker = "book_tracker.cli:main"`) with the runtime and dev dependencies listed in plan.md "New dependencies", then run `uv lock` to create `uv.lock`
- [X] T003 Add tool configuration to `pyproject.toml`: ruff (lint + format, `target-version = "py312"`, rule sets E, F, I, B, UP, S, ASYNC), mypy (`strict = true`, pydantic plugin, `files = ["src"]`), pytest (`asyncio_mode = "auto"`, markers `ac`, `a11y`, `perf`, `addopts = "-m 'not perf and not a11y'"`), coverage (`source = ["src/book_tracker"]`, `branch = true`, `fail_under = 85`)
- [X] T004 [P] Create `scripts/check_coverage.py`: reads `coverage.json` and exits non-zero unless each module listed in plan.md "Coverage-critical modules" has 100% line coverage; prints the failing modules and their missing lines
- [X] T005 [P] Create the package skeleton with empty `__init__.py` files: `src/book_tracker/`, `src/book_tracker/{auth,api,schemas,domain,services,persistence,web,web/routes}/`, plus empty directories `src/book_tracker/web/templates/{pages,partials,admin}/`, `src/book_tracker/web/static/{css,vendor}/`, and `tests/{unit,integration,contract,a11y,perf}/__init__.py`
- [X] T006 [P] Vendor HTMX 2.0.4 as `src/book_tracker/web/static/vendor/htmx.min.js` and write `src/book_tracker/web/static/vendor/README.md` recording the version, source URL, license (0BSD) and SHA-384 hash of the file (research R14)
- [X] T007 [P] Create `.gitignore` at the project root covering `.venv/`, `__pycache__/`, `.coverage`, `coverage.json`, `htmlcov/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.env`, `.claude/settings.local.json`
- [X] T008 [P] Create `.github/workflows/ci.yml` with these jobs, all required to merge: `ruff check` + `ruff format --check`; `mypy --strict src`; `pytest --cov --cov-report=json` then `python scripts/check_coverage.py`; `pytest -m a11y` (after `playwright install --with-deps chromium`); `pytest -m perf`; `pip-audit` (with `--ignore-vuln` entries read from a committed `.pip-audit-ignore` file, each with a reason and review date); contract check (`python -m book_tracker.export_openapi > generated.json` then `docker run --rm tufin/oasdiff:<version> breaking specs/001-family-reading-list/contracts/openapi.yaml generated.json --fail-on ERR`, with the image pinned to a released version looked up when this task is done and recorded in a comment in the workflow); spec gate (PR body must link a `specs/` directory or the PR is labelled `chore` or `fix`)
- [X] T009 [P] Create `Dockerfile` (python:3.12-slim, uv install from `uv.lock` without dev deps, non-root user, `EXPOSE 8000`) and `docker/entrypoint.sh` that runs `alembic upgrade head`, then `book-tracker create-admin --if-missing` when `BOOK_TRACKER_ADMIN_LOGIN` is set, then `uvicorn book_tracker.main:app --host 0.0.0.0 --port 8000 --proxy-headers` (research R12)
- [X] T010 Confirm the license of every dependency in plan.md "New dependencies" against its installed metadata (`uv run python -c "import importlib.metadata as m; ..."` printing `License` / `License-Expression` / classifiers) and correct the table in `specs/001-family-reading-list/plan.md` where it differs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema, authentication, sign-in, page layout and test infrastructure that every story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for the foundation ⚠️

> **Write these tests FIRST and confirm they FAIL before T024–T044.**

- [X] T011 Create `tests/conftest.py`: a session-scoped PostgreSQL 16 testcontainer; `alembic upgrade head` once per session; per-test isolation by truncating all tables except `alembic_version`; an `app` fixture built by `book_tracker.main.create_app(settings)`; an async `httpx.AsyncClient` over `httpx.ASGITransport` with base URL `https://testserver`; factories `make_user(role="member", login=..., password="password123", must_change_password=False, is_active=True)`, `make_author`, `make_series`, `make_book`, `make_entry`; a `signed_in(client, user)` helper that signs in through `POST /api/v1/auth/login` and sets the `X-CSRF-Token` header from `GET /api/v1/me`; and a `pytest_collection_modifyitems` hook that fails collection when an `ac` marker id doesn't match `^001/AC-\d{2}$`
- [X] T012 [P] Create `tests/contract/conftest.py` with a fixture that loads `specs/001-family-reading-list/contracts/openapi.yaml` with `openapi-core` and an `assert_matches_contract(response)` helper that validates an httpx response (status, content type, body) against the operation for its method and path
- [X] T013 [P] Write `tests/integration/test_migrations.py`: on an empty database, upgrade → downgrade → upgrade succeeds; after upgrade all nine tables from data-model.md exist; after downgrade only `alembic_version` remains (Principle VI)
- [X] T014 [P] Write `tests/integration/test_constraints.py`: one test per constraint in data-model.md, each inserting a violating row directly and expecting `IntegrityError`: series number without series (AC-06), real name without pen name (AC-18), case-insensitive unique author name, series name and login (AC-16, AC-29), ISBN format and uniqueness (AC-30), unique series + number (AC-19), series number range, times-read range, unique (user, book) (AC-05), one current summary per book, `origin='manual' OR model IS NOT NULL`, `finished_on >= 1900-01-01`, role and status value checks, `book_author.position >= 1` and unique (book, position)
- [X] T015 [P] Write `tests/unit/test_domain_values.py`: `Isbn13` accepts a valid ISBN with hyphens and spaces and normalizes to 13 digits, rejects a bad checksum, wrong length and non-digits (AC-30); `SeriesNumber` accepts 0, 2.5 and 999.99, rejects -1, 1000 and 2.555 (AC-20); `normalize_name` trims and collapses inner whitespace; `default_sort_name("J.K. Rowling") == "Rowling, J.K."` and a single-word name is returned unchanged
- [X] T016 [P] Write `tests/unit/test_passwords.py`: hashes start with `$argon2id$`; verify succeeds for the right password and fails for a wrong one; `needs_rehash` is true for a hash made with weaker parameters
- [X] T017 [P] Write `tests/integration/test_sessions.py` (covers all of `auth/sessions.py`): creating a session stores only the SHA-256 hash of the token; look-up of a valid token returns the user; a token unused for more than 14 days is rejected; `last_seen_at` is written at most once per minute; revoking one session and revoking all sessions for a user both work; a session for a deactivated user is rejected (AC-10)
- [X] T018 [P] Write `tests/integration/test_auth_dependencies.py` (covers all of `auth/dependencies.py`): no cookie → 401 (API) and 303 to `/sign-in` (UI) or `HX-Redirect` for an HTMX request; POST, PATCH and DELETE without or with a wrong CSRF token → 403 `csrf_failed`, GET is not checked; `require_admin` → 403 `not_admin` for a member; with `must_change_password` set, API routes other than `/auth/password`, `/auth/logout` and `/me` → 403 `password_change_required`, and UI routes redirect to `/account/password`
- [X] T019 [P] Write `tests/contract/test_auth_contract.py`: `GET /api/v1/auth/csrf` 200; `POST /api/v1/auth/login` 200, 401 (wrong password; deactivated account gives the same body), 403 (no CSRF), 422; `POST /api/v1/auth/logout` 204; `GET /api/v1/me` 200 and 401. Every response passes `assert_matches_contract` (AC-01, AC-02)
- [X] T020 [P] Write `tests/integration/test_sign_in_pages.py`: `GET /sign-in` renders a form with labelled login and password fields and no account-creation link; posting valid credentials sets a `__Host-session` cookie that is Secure, HttpOnly and SameSite=Lax and redirects 303 to `/` (AC-01); `POST /sign-out` ends the session, then `GET /` redirects to `/sign-in` (AC-02); a wrong password re-renders the form with one generic error message
- [X] T021 [P] Write `tests/integration/test_cli_create_admin.py`: `create-admin` with `BOOK_TRACKER_ADMIN_PASSWORD` set creates exactly one active Admin with `must_change_password = false` that can sign in (AC-27); a second run fails with a clear message and creates nothing; `--if-missing` exits 0 without changes when an Admin exists; a password shorter than 8 characters is refused
- [X] T022 [P] Write `tests/unit/test_mappers.py`: for each ORM model in `persistence/models.py`, the function in `persistence/mappers.py` returns the matching frozen dataclass from `domain/models.py` with every field copied, authors ordered by `position`, `current_summary` set only from the `is_current` row, and no SQLAlchemy object reachable from the result (Principle VII). Mapping from domain objects to API schemas is checked by the contract tests in each story
- [X] T023 [P] Write `tests/unit/test_logging.py`: the redaction filter replaces values of `password`, `token`, `csrf_token`, `notes` and any cookie header with `[REDACTED]`, including inside nested dicts; request log lines contain the route template (e.g. `/entries/{entry_id}`), method and status, never the raw path

### Implementation for the foundation

- [X] T024 Implement `src/book_tracker/settings.py`: a `Settings(BaseSettings)` class with prefix `BOOK_TRACKER_` and fields `database_url: PostgresDsn`, `secret_key: SecretStr` (min 32 characters), `environment: Literal["local", "test", "production"]`, `session_idle_days: int = 14`, `admin_login`, `admin_display_name`, `admin_password: SecretStr | None`; plus a cached `get_settings()`
- [X] T025 [P] Implement `src/book_tracker/logging.py`: JSON formatter, `RedactingFilter` and a request-logging middleware that logs method, matched route template, status and duration (research R19); make T023 pass
- [X] T026 [P] Implement `src/book_tracker/domain/enums.py` (`Role`, `ReadingStatus`, `SummaryOrigin`), `src/book_tracker/domain/values.py` (`Isbn13`, `SeriesNumber` as a `Decimal` wrapper, `normalize_name`, `default_sort_name`) as Pydantic-compatible annotated types, and `src/book_tracker/domain/models.py` with frozen, slotted dataclasses `UserRef`, `Account`, `Author`, `Series`, `BookAuthor`, `Summary`, `Book`, `ReadingEntry` (fields as in data-model.md; no ORM or Pydantic imports). Services take and return only these types (Principle VII); make T015 pass
- [X] T027 Implement `src/book_tracker/persistence/db.py`: async engine from `settings.database_url` using the `postgresql+psycopg` driver, `async_sessionmaker`, and a FastAPI dependency `get_db()` that yields a session and commits on success / rolls back on error
- [X] T028 Implement `src/book_tracker/persistence/models.py`: SQLAlchemy 2.0 typed models for all nine tables in data-model.md, with every column, check constraint, unique constraint, functional index (`lower(...)`) and partial index named explicitly (for example `author_name_lower_uq`, `book_series_number_uq`) so services can map `IntegrityError` by constraint name
- [X] T029 Implement `src/book_tracker/persistence/mappers.py`: explicit functions from each SQLAlchemy model to its domain dataclass (`to_account`, `to_user_ref`, `to_author`, `to_series`, `to_book`, `to_summary`, `to_reading_entry`); repositories return only domain objects; make T022 pass (Principle VII)
- [X] T030 Create `alembic.ini`, `migrations/env.py` (sync psycopg URL derived from settings, `target_metadata` from models) and `migrations/versions/0001_initial.py` creating all tables, constraints and indexes, with a `downgrade()` that drops them in reverse dependency order; make T013 and T014 pass
- [X] T031 [P] Implement `src/book_tracker/auth/passwords.py`: `hash_password`, `verify_password`, `needs_rehash` using `argon2.PasswordHasher()` defaults, plus `DUMMY_HASH` for timing-equalized checks of unknown logins (research R2, R3); make T016 pass
- [X] T032 Implement `src/book_tracker/persistence/accounts.py`: `UserRepository` (get by id, get by login using `lower(login)`, create, list, update, count active Admins `FOR UPDATE`) and `SessionRepository` (insert, get by token hash with user join, touch, delete one, delete all for user)
- [X] T033 Implement `src/book_tracker/auth/sessions.py`: `create_session(user) -> (token, csrf_token)`, `resolve_session(token)`, sliding expiry written at most once per minute, `revoke(token)`, `revoke_all(user_id)`; validity requires `expires_at > now()` and `user.is_active` (research R1); make T017 pass
- [X] T034 [P] Implement `src/book_tracker/auth/csrf.py`: issue and verify a pre-session CSRF token as an HMAC-SHA256 of a random nonce with `settings.secret_key`, stored in a short-lived (10 minutes) `__Host-presession` cookie; constant-time comparison (research R4)
- [X] T035 Implement `src/book_tracker/auth/dependencies.py`: `current_user` (reads `__Host-session`, raises 401 for the API or redirects for the UI), `require_csrf` (checks `X-CSRF-Token` header or `csrf_token` form field against the session row on unsafe methods; uses the pre-session token for sign-in), `require_admin`, `require_password_current`; make T018's API cases pass
- [X] T036 [P] Implement `src/book_tracker/services/errors.py` with the error types services raise: `NotFoundError`, `ConflictError(code, existing_id, existing_label)`, `ForbiddenError(code)`. It imports nothing from `api/`. Then implement `src/book_tracker/api/errors.py`: Pydantic models `Problem`, `Conflict`, `ValidationProblem`, and handlers that turn those errors into HTTP responses, that return `application/problem+json` and convert `RequestValidationError` to 422 with `errors[{field, message}]`. Also create `src/book_tracker/api/responses.py` with shared `responses=` maps (for example `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `CATALOG_CONFLICT`, `VALIDATION`) using the contract's component names and `application/problem+json` content, for every route to declare (research R16)
- [X] T037 [P] Implement `src/book_tracker/schemas/auth.py`: `Password` (annotated `str`, 8–128 characters, FR-028), `LoginRequest`, `CsrfToken`, `CurrentUser`, `PasswordChange`, with `model_config = ConfigDict(extra="forbid")` on request models
- [X] T038 Implement a skeleton `create_app(settings)` in `src/book_tracker/main.py`: logging setup, exception handlers from `api/errors.py`, an empty `/api/v1` router, the `/static` mount, and a custom `openapi()` that replaces FastAPI's default 422 `HTTPValidationError` with `ValidationProblem` (research R16). Later tasks register their routers here
- [X] T039 Implement `src/book_tracker/api/auth.py` (`GET /auth/csrf`, `POST /auth/login`, `POST /auth/logout`) and `src/book_tracker/api/me.py` (`GET /me`), using `auth/sessions.py`; a wrong login, wrong password and a deactivated account all return the same 401 body, and unknown logins are verified against `DUMMY_HASH`; every route declares its responses from `api/responses.py`; `api/me.py` builds `CurrentUser` through `schemas/mappers.py` (create it with `to_current_user`); register both routers in `create_app`; make T019 pass (FR-001, FR-002)
- [X] T040 Create `src/book_tracker/web/templates/base.html` (lang attribute, skip link, `<main id="main">`, nav with the member's display name, Switch user and Sign out buttons, `<body hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'>`, an `aria-live="polite"` region `#messages`, HTMX script from `/static/vendor/htmx.min.js`) and `src/book_tracker/web/static/css/app.css` (mobile-first layout, max-width container, visible `:focus-visible` outline, minimum 4.5:1 text contrast, 44 px touch targets) (FR-026, FR-030)
- [X] T041 Implement `src/book_tracker/web/routes/auth.py` with templates `src/book_tracker/web/templates/pages/sign_in.html`: `GET /sign-in`, `POST /sign-in` (303 to `/`), `POST /sign-out` (303 to `/sign-in`); plus a `render(request, template, **ctx)` helper in `src/book_tracker/web/rendering.py` that injects `csrf_token`, the current user and returns only the named block for HTMX requests; register the router in `create_app`; make T020 pass (FR-001)
- [X] T042 Complete `src/book_tracker/main.py`: add the unauthenticated-UI redirect handler (303 to `/sign-in`, or `HX-Redirect` for HTMX) and the password-change redirect, and module-level `app = create_app(get_settings())`; make T018's UI cases pass
- [X] T043 [P] Implement `src/book_tracker/cli.py`: `main()` with a `create-admin` subcommand (`--login`, `--display-name`, `--if-missing`; password from `BOOK_TRACKER_ADMIN_PASSWORD` or a no-echo prompt; validated with `Password`) that creates an active Admin with `must_change_password = false` (FR-006); make T021 pass
- [X] T044 [P] Implement `src/book_tracker/export_openapi.py`: `python -m book_tracker.export_openapi` prints `create_app(...).openapi()` as JSON to stdout, using placeholder settings so no database is needed

**Checkpoint**: Foundation ready. A member created by the CLI or a test factory can sign in and out; every later route inherits sessions, CSRF and error handling.

---

## Phase 3: User Story 1 - Sign in and keep my own reading list (Priority: P1) 🎯 MVP

**Goal**: A signed-in member adds books (title and authors required; series, number and notes optional), sees only their own list, and edits, re-reads or removes entries.

**Independent Test**: With two members created by factories, each signs in, adds books and confirms their list contains only their own entries and that the other member's entries return "not found" everywhere.

### Tests for User Story 1 ⚠️

> **Write these tests FIRST and confirm they FAIL before T052.**

- [X] T045 [P] [US1] Write `tests/unit/test_times_read.py` for the pure function `apply_status_change(old_status, new_status, times_read, override)` in `services/readings.py`: adding as Finished gives 1, adding as Want to read or Reading gives 0 (AC-31); a change into Finished adds 1, capped at 99; Finished → Reading via read-again leaves the count unchanged (AC-35); an explicit `times_read` in the same update replaces the increment
- [X] T046 [P] [US1] Write `tests/unit/test_reading_schemas.py`: `ReadingEntryCreate` requires exactly one of `book_id` and `new_book`; `finished_on` tomorrow is rejected (AC-31); notes over 10,000 characters are rejected; `BookCreate` with `series_number` and no `series_id` is rejected (AC-06); an empty `author_ids` list is rejected; `status` defaults to `finished`
- [X] T047 [P] [US1] Write `tests/integration/test_readings_repository.py` (covers all of `persistence/readings.py`): a repository bound to Alice lists, gets, updates and deletes only Alice's entries; `get` with Ben's entry id returns `None`, the same as a random UUID; no public method of `ReadingEntryRepository` has a parameter named `user_id` (checked with `inspect.signature`) (AC-04)
- [X] T048 [P] [US1] Write `tests/integration/test_reading_isolation.py`: with entries for Alice and Ben, Alice's `GET /api/v1/me/readings` contains only her entries; for Ben's entry id, `GET`, `PATCH`, `DELETE /api/v1/me/readings/{id}` and `POST .../read-again`, and the UI routes `GET /entries/{id}`, `POST /entries/{id}`, `POST /entries/{id}/read-again`, `POST /entries/{id}/remove`, each return 404 with a body identical to a random UUID's, and Ben's entry is unchanged afterwards (AC-04)
- [X] T049 [P] [US1] Write `tests/integration/test_reading_service.py`: adding a new book with title and one author only stores it with no series and no number and lists it (AC-03); adding a book already on the list returns 409 `already_on_list` with `existing_id` of the entry and creates no rows (AC-05); a number in series without a series returns 422 and creates no rows (AC-06); removing an entry leaves the catalog book and Ben's entry for it (AC-07); status, date finished and notes are saved and are absent from Ben's view of the same book (AC-08); default status and future date rules via the API (AC-31); read-again then Finished on a new date gives times read 2 and the new date, still one entry (AC-35); removing a book and adding it again creates a fresh entry without the old status or notes (edge case); catalog uniqueness when adding a new book inline: an author or series whose name matches an existing one ignoring capitalization returns 409 `author_exists` / `series_exists` with the existing id and name, a taken series number returns 409 `series_number_taken` naming the existing book, an ISBN already in the catalog returns 409 `isbn_exists` offering that book, and two concurrent creates of the same new author end with one row and the loser gets 409 with the winner's id; in every case no rows are created (AC-16, AC-19, AC-30)
- [X] T050 [P] [US1] Write `tests/contract/test_readings_contract.py`: `GET` and `POST /api/v1/me/readings`; `GET`, `PATCH`, `DELETE /api/v1/me/readings/{id}`; `POST /api/v1/me/readings/{id}/read-again`; `POST /api/v1/authors` and `POST /api/v1/series` (201); `GET /api/v1/authors/{id}`, `/series/{id}`, `/books/{id}`; including the 404, 409 `already_on_list` and 422 shapes; each response passes `assert_matches_contract` (AC-03, AC-05, AC-07)
- [X] T051 [P] [US1] Write `tests/integration/test_reading_pages.py`: `GET /` lists the member's entries with title, authors, series and status; the add form at `/books/add` can create a new author and a new series inline and saves the book (AC-03); adding a duplicate shows "Already on your list" with a "Read again" button (AC-05); `GET /entries/{id}` edits status, date, times read and notes (AC-08); remove asks for confirmation, then removes (AC-07)

### Implementation for User Story 1

- [X] T052 [P] [US1] Implement `src/book_tracker/schemas/catalog.py` (base models): `UserRef`, `AuditInfo`, `SeriesRef`, `BookAuthorRef`, `AuthorCreate` (sort name defaults to `default_sort_name(name)`), `Author`, `SeriesWrite`, `Series`, `BookCreate`, `Book`, `Summary` (output only), matching contracts/openapi.yaml field for field (FR-012, FR-013)
- [X] T053 [US1] Implement `src/book_tracker/schemas/readings.py`: `ReadingEntryCreate` (model validator for exactly one of `book_id` / `new_book`; `finished_on` not in the future), `ReadingEntryUpdate`, `ReadingEntry`, `ReadingEntryPage`; make T046 pass (FR-016, FR-018)
- [X] T054 [P] [US1] Implement `src/book_tracker/persistence/readings.py`: `ReadingEntryRepository(session, user_id)` with `list(page, page_size)`, `get(entry_id)`, `get_by_book(book_id)`, `add(book_id, status, finished_on, times_read, notes)`, `update(entry_id, **fields)`, `delete(entry_id)`; every statement includes `ReadingEntry.user_id == self._user_id`; no method takes a user id; make T047 pass (FR-020)
- [X] T055 [US1] Implement `src/book_tracker/persistence/catalog.py` (create and read only): `create_author`, `create_series`, `create_book(title, author_ids, series_id, series_number, isbn_13, actor_id)` writing `book` and ordered `book_author` rows in one transaction, `get_book` (with authors, series and current summary), `get_author`, `get_series`; set `created_by` / `updated_by` to the actor (FR-009, FR-012)
- [X] T056 [US1] Add to `src/book_tracker/schemas/mappers.py` explicit functions from domain dataclasses to the Pydantic output schemas (`book_out`, `author_out`, `series_out`, `summary_out`, `reading_entry_out`, `reading_entry_page_out`, `user_ref_out`), checked by T050 (Principle VII)
- [X] T057 [US1] Implement `src/book_tracker/services/catalog.py` (create part): `create_author`, `create_series`, `create_book`, returning domain objects, that normalize names, validate and normalize ISBNs with `Isbn13`, and check that referenced author and series ids exist (404 otherwise). Add conflict handling (research R9): catch `IntegrityError`, map the constraint name (`author_name_lower_uq`, `series_name_lower_uq`, `book_isbn_13_key`, `book_series_number_uq`) to a code, look up the existing row and raise `ConflictError(code, existing_id, existing_label)` (FR-009, FR-011, FR-012, FR-013, FR-015)
- [X] T058 [US1] Implement `src/book_tracker/services/readings.py`: `apply_status_change` (FR-029), `add_entry` (existing book or `new_book` in one transaction; duplicate → `ConflictError("already_on_list", existing_id=entry.id)`), `update_entry`, `read_again`, `remove_entry`, all using `ReadingEntryRepository` bound to the session user, taking and returning domain objects; inline author, series and book creates go through `services/catalog.py` so conflicts return 409; make T045 pass (FR-016, FR-017, FR-018, FR-019, FR-029)
- [X] T059 [US1] Implement `src/book_tracker/api/readings.py`: `GET /me/readings` (pagination, default sort by title; other query parameters arrive in US4), `POST /me/readings`, `GET`/`PATCH`/`DELETE /me/readings/{entry_id}`, `POST /me/readings/{entry_id}/read-again`; convert service results with `schemas/mappers.py` and declare responses from `api/responses.py`; register the router in `src/book_tracker/main.py` (FR-016–FR-020, FR-029)
- [X] T060 [US1] Implement `src/book_tracker/api/authors.py` (`POST /authors`, `GET /authors/{id}`), `src/book_tracker/api/series.py` (`POST /series`, `GET /series/{id}`) and `src/book_tracker/api/books.py` (`GET /books/{id}`), declaring responses from `api/responses.py`; register them in `src/book_tracker/main.py` (FR-009, FR-012)
- [X] T061 [US1] Implement `src/book_tracker/web/routes/readings.py` with templates `pages/list.html` (with block `reading_list` for HTMX), `pages/add_book.html` (labelled fields for title, authors with an "add new author" sub-form, series with an "add new series" sub-form, number in series, status, date finished, notes; server-side validation messages linked with `aria-describedby`), `pages/entry.html` (book details, edit form, Read again, Remove with a confirmation step): routes `GET /`, `GET`/`POST /books/add`, `GET`/`POST /entries/{id}`, `POST /entries/{id}/read-again`, `POST /entries/{id}/remove`; a catalog conflict on the add form re-renders it with "Already in the catalog: <existing name>" next to the field; register in `src/book_tracker/main.py`; make T048, T049, T050 and T051 pass (FR-011, FR-016–FR-020, FR-026, FR-029)

**Checkpoint**: User Story 1 works on its own: members created by the CLI or factories keep separate lists.

---

## Phase 4: User Story 2 - Parents manage family accounts (Priority: P1)

**Goal**: Admins create, deactivate, reactivate and reset accounts; nobody can register themselves; sign-in is throttled; members can switch user on a shared device.

**Independent Test**: The initial Admin creates a member, the member signs in and must change the temporary password, the Admin resets the password and later deactivates the account; each step is checked from the member's side.

### Tests for User Story 2 ⚠️

> **Write these tests FIRST and confirm they FAIL before T069.**

- [X] T062 [P] [US2] Write `tests/integration/test_accounts_service.py` (covers all of `services/accounts.py`): an Admin creates an account with a username and no email, `must_change_password` is true, and the member can sign in (AC-09); creating login `sam` when `Sam` exists → 409 `login_exists` (AC-29); a 7-character password is rejected and `abcdefgh` is accepted, both for creation and reset (AC-34); deactivating ends the member's sessions, sign-in is then refused, and their entries are still there after reactivation (AC-10); the only active Admin can't deactivate themselves or drop the Admin role → 409 `last_admin`, and two Admins demoting each other concurrently can't both succeed (AC-26); reset sets `must_change_password` and ends the member's sessions (FR-004)
- [X] T063 [P] [US2] Write `tests/integration/test_throttle.py` (covers all of `auth/throttle.py`), using an injectable clock: after 5 wrong passwords for a login, the correct password returns 429 with `Retry-After` and a "try again later" message, and the UI form shows the same message; after 15 minutes the correct password works (AC-33); a login that matches no account gets identical status codes and bodies; a successful sign-in resets the count; wrong passwords entered during the lock are refused without being counted and the lock still ends at its original time; rows not updated for more than 24 hours are pruned; the `login_throttle` table never contains the login text (FR-027, Principle IX)
- [X] T064 [P] [US2] Write `tests/integration/test_password_change.py`: a member signing in for the first time with an Admin-set initial password, or after a reset, is redirected to `/account/password` from every other UI route, and gets 403 `password_change_required` from API routes other than `/auth/password`, `/auth/logout` and `/me` (AC-09, AC-11); changing the password with the wrong current password returns 400; a successful change clears the flag and ends the member's other sessions (FR-004, FR-028)
- [X] T065 [P] [US2] Write `tests/integration/test_admin_access.py`: a member gets 403 `not_admin` from every `/api/v1/admin/*` operation and from every `/admin/*` page (AC-13); an Admin's `GET /api/v1/me/readings` shows only the Admin's own entries, the Admin gets 404 for Ben's entry by API and UI, and no admin page or response contains any reading entry field (AC-14); no route exists for self-registration: `GET /register`, `GET /sign-up` → 404, unauthenticated `POST /api/v1/admin/users` → 401, and the sign-in page has no account-creation link (AC-12)
- [X] T066 [P] [US2] Write `tests/integration/test_switch_user.py`: each sign-in updates the `recent_profiles` cookie (HttpOnly, Secure, SameSite=Lax, 90 days) to at most 5 user ids, most recent first; `POST /switch-user` ends the session and keeps the cookie; `GET /sign-in` lists the display name and login of each active recent account and omits deactivated ones; choosing a profile fills in the login field and still requires the password (AC-28)
- [X] T067 [P] [US2] Write `tests/contract/test_admin_contract.py`: `GET` and `POST /api/v1/admin/users`, `PATCH /api/v1/admin/users/{id}`, `POST /api/v1/admin/users/{id}/password-reset`, `POST /api/v1/auth/password`, and the 429 sign-in response with `Retry-After`, including the 403, 404, 409 and 422 shapes; each response passes `assert_matches_contract` (AC-09, AC-26, AC-29, AC-33)
- [X] T068 [P] [US2] Write `tests/integration/test_admin_pages.py`: `/admin/users` lists accounts with role and active state; `/admin/users/new` creates an account and shows the login-in-use and password-length errors next to their fields; the deactivate, reactivate, change-role and reset-password buttons work and the last-Admin refusal is shown as a message (AC-09, AC-10, AC-26)

### Implementation for User Story 2

- [X] T069 [P] [US2] Implement `src/book_tracker/schemas/accounts.py`: `Account`, `AccountCreate` (login 3–255 characters, `Password`), `AccountUpdate` (at least one field), `PasswordReset`, and `account_out` in `src/book_tracker/schemas/mappers.py` (FR-003, FR-028)
- [X] T070 [US2] Implement `src/book_tracker/auth/throttle.py`: `check_allowed(login_key, now) -> int | None` (seconds remaining when locked), `record_failure`, `record_success`, `prune(now)`, using the `login_throttle` table and a `Clock` protocol (research R3); compute `login_key` with `hmac.new(secret_key, normalized_login, sha256).hexdigest()`; make T063 pass (FR-027)
- [X] T071 [US2] Wire throttling into `POST /api/v1/auth/login` in `src/book_tracker/api/auth.py` (429 + `Retry-After`) and `POST /sign-in` in `src/book_tracker/web/routes/auth.py` ("Too many attempts. Try again later." message) (FR-027)
- [X] T072 [US2] Implement `src/book_tracker/services/accounts.py`: `create_account` (login uniqueness → `ConflictError("login_exists")`), `update_account` (locks active Admin rows with `FOR UPDATE` and refuses to leave zero → `ConflictError("last_admin")`; deactivation calls `revoke_all`), `reset_password` (sets `must_change_password`, `revoke_all`), `change_own_password` (verifies current password, clears the flag, revokes other sessions); make T062 pass (FR-002–FR-005, FR-008, FR-028)
- [X] T073 [US2] Implement `src/book_tracker/api/admin.py` (`GET`/`POST /admin/users`, `PATCH /admin/users/{user_id}`, `POST /admin/users/{user_id}/password-reset`, all behind `require_admin`) and add `POST /auth/password` to `src/book_tracker/api/auth.py`, declaring responses from `api/responses.py`; register in `src/book_tracker/main.py`; make T064 (API part), T065 and T067 pass (FR-003, FR-004)
- [X] T074 [US2] Implement `src/book_tracker/web/routes/admin.py` with templates `admin/users.html` and `admin/new_user.html`: routes `GET /admin/users`, `GET`/`POST /admin/users/new`, `POST /admin/users/{id}`, `POST /admin/users/{id}/reset-password`; show an Admin link in the nav in `base.html` only for Admins; make T068 pass (FR-003–FR-005)
- [X] T075 [US2] Add to `src/book_tracker/web/routes/auth.py`: `GET`/`POST /account/password` with template `pages/change_password.html`, `POST /switch-user`, maintenance of the `recent_profiles` cookie on sign-in, and the recent-profiles list on `pages/sign_in.html` (buttons that fill the login field); make T064 (UI part) and T066 pass (FR-004, FR-007)

**Checkpoint**: User Stories 1 and 2 together give a usable family app: parents create accounts, members keep private lists.

---

## Phase 5: User Story 3 - Add books from a shared family catalog (Priority: P2)

**Goal**: Type-ahead suggestions for books, authors and series; duplicates are prevented and the existing entry is offered; pen names with optional real names; any member can edit catalog entries, with the last editor shown.

**Independent Test**: Alice adds a book; Ben finds it through type-ahead and adds it, leaving one catalog copy; a pen-name author is saved without a real name and later found by the real name.

### Tests for User Story 3 ⚠️

> **Write these tests FIRST and confirm they FAIL before T083.**

- [X] T076 [P] [US3] Write `tests/integration/test_typeahead.py`: `GET /api/v1/books?q=` matches title or author name, ranks prefix matches first, returns at most `limit` (default 10), treats `%` and `_` as literal characters, and a query that is a valid ISBN-13 (with or without hyphens) returns the book with that ISBN first (AC-15); `GET /api/v1/authors?q=` matches both name and real name (FR-010); `GET /api/v1/series?q=` matches names case-insensitively
- [X] T077 [P] [US3] Write `tests/integration/test_catalog_conflicts.py` for **edits** (creates are covered by T049): renaming an author or series to an existing name ignoring capitalization returns 409 `author_exists` / `series_exists` with the existing id (AC-16); patching a book to a series number already taken returns 409 `series_number_taken` naming the existing book (AC-19); patching a book to an invalid ISBN returns 422, and to an ISBN another book has returns 409 `isbn_exists` offering that book (AC-30); in every case the row is unchanged
- [X] T078 [P] [US3] Write `tests/integration/test_pen_names.py`: an author marked as a pen name with no real name is saved; after `PATCH` adds real name "J.K. Rowling", `GET /api/v1/authors?q=Rowling` returns that author and `GET /api/v1/books?q=Rowling` returns their books (AC-17); a real name on an author not marked as a pen name, on create or patch, returns 422 with the message "Mark the author as a pen name first" (AC-18)
- [X] T079 [P] [US3] Write `tests/integration/test_catalog_edit.py`: Ben's `PATCH /api/v1/books/{id}` on a book Alice created changes the title on Alice's list, and the book shows `updated_by` Ben with a later `updated_at`, while `created_by` stays Alice (AC-32); series number 2.5 is accepted on create and patch (AC-20); changing a book's authors keeps their order; two books with the same title and different authors can both be created (edge case)
- [X] T080 [P] [US3] Write `tests/integration/test_shared_catalog_flow.py`: Alice adds a book; Ben types its title in `/books/add`, `/suggest/books` returns it, Ben chooses it, and the number of `book` rows doesn't change (AC-15); creating a duplicate author in the add form shows "Already in the catalog" with a button to use the existing author (AC-16)
- [X] T081 [P] [US3] Write `tests/contract/test_catalog_contract.py`: `GET /api/v1/books`, `/authors`, `/series` with `q`; `PATCH /api/v1/books/{id}`, `/authors/{id}`, `/series/{id}`; and the `CatalogConflict` 409 shape; each response passes `assert_matches_contract` (AC-15, AC-16, AC-19, AC-30, AC-32)
- [X] T082 [P] [US3] Write `tests/integration/test_catalog_pages.py`: `/catalog/books/{id}/edit`, `/catalog/authors/{id}/edit` (pen name checkbox, real name field enabled only when checked) and `/catalog/series/{id}/edit` save changes and show "Last edited by <name> on <date>" (AC-17, AC-18, AC-32); suggestion lists use the ARIA combobox pattern (`role="combobox"`, `aria-controls`, `role="listbox"`, `role="option"`) (FR-030)

### Implementation for User Story 3

- [X] T083 [P] [US3] Add `AuthorUpdate`, `BookUpdate` and the pen-name rule (model validator: `real_name` only when `is_pen_name`) to `src/book_tracker/schemas/catalog.py`, applying it to both create and update; make T078's 422 cases pass (FR-014)
- [X] T084 [US3] Add search functions to `src/book_tracker/persistence/catalog.py`: `search_books(q, limit)` (title or any author name or real name, plus an exact `isbn_13` match ranked first when `q` normalizes to a valid ISBN-13), `search_authors(q, limit)` (name or real name), `search_series(q, limit)`, using `ILIKE` with escaped `%`/`_`, prefix matches first, then alphabetical (research R7) (FR-010)
- [X] T085 [US3] Add update functions to `src/book_tracker/persistence/catalog.py`: `update_author`, `update_series`, `update_book` (replacing `book_author` rows when `author_ids` is given), each setting `updated_by` and `updated_at` (FR-009)
- [X] T086 [US3] Implement `update_author`, `update_series` and `update_book` in `src/book_tracker/services/catalog.py`, returning domain objects and setting `updated_by` to the session user; reuse T057's conflict handling and validate ISBNs with `Isbn13`; make T077 pass (FR-009, FR-011, FR-015, R9)
- [X] T087 [US3] Add `search_books`, `search_authors` and `search_series` to `src/book_tracker/services/catalog.py`, and the endpoints (all declaring responses from `api/responses.py`) `GET /books`, `PATCH /books/{id}` in `src/book_tracker/api/books.py`, `GET /authors`, `PATCH /authors/{id}` in `src/book_tracker/api/authors.py`, `GET /series`, `PATCH /series/{id}` in `src/book_tracker/api/series.py`; make T076, T078, T079 and T081 pass (FR-009, FR-010, FR-014)
- [X] T088 [US3] Implement `src/book_tracker/web/routes/suggest.py` with `partials/suggestions.html`: `GET /suggest/books`, `/suggest/authors`, `/suggest/series` returning listbox fragments (hx-trigger `input changed delay:250ms`), keyboard navigation with arrow keys, Enter and Escape, and the result count announced in an `aria-live` region (FR-010, FR-030)
- [X] T089 [US3] Update `src/book_tracker/web/templates/pages/add_book.html` and `src/book_tracker/web/routes/readings.py` to use the suggestion comboboxes for the book, authors and series, and to show catalog conflicts as "Already in the catalog" with a button to use the existing entry; make T080 pass (FR-010, FR-011, FR-016)
- [X] T090 [US3] Implement `src/book_tracker/web/routes/catalog.py` with templates `pages/edit_book.html`, `pages/edit_author.html`, `pages/edit_series.html`: routes `GET`/`POST /catalog/books/{id}/edit`, `/catalog/authors/{id}/edit`, `/catalog/series/{id}/edit`, showing the last editor and date; link to them from `pages/entry.html`; make T082 pass (FR-009, FR-014)

**Checkpoint**: The catalog stays free of duplicates, and Stories 1–3 all work independently.

---

## Phase 6: User Story 4 - Browse, sort, filter and search my list (Priority: P3)

**Goal**: Sort, filter and search the member's own list; a series view in reading order.

**Independent Test**: With a seeded list across several authors and series for two members, sort, filter, search and open a series view, and check only the member's own books appear.

### Tests for User Story 4 ⚠️

> **Write these tests FIRST and confirm they FAIL before T094.**

- [X] T091 [P] [US4] Write `tests/integration/test_list_browse.py`: each `sort` value (title, author, series, finished_on, ascending and descending) orders only the member's entries, and each filter (`author_id`, `series_id`, `status`) returns only matching entries of that member, never Ben's (AC-21); `GET /api/v1/me/series/{id}` for books numbered 1, 2.5, 3 and one unnumbered returns 1, 2.5, 3, then the unnumbered one (AC-22, AC-20); `q` matching a title, an author name, an author real name or a series name returns the member's matches and none of Ben's (AC-23); a series with no entries for this member returns an empty `entries` list, and an unknown series id returns 404; **cross-user (Principle I)**: with Ben owning entries in the same series, including at numbers Alice doesn't have, Alice's `GET /api/v1/me/series/{id}` contains none of Ben's entries, and Ben's response contains none of Alice's
- [X] T092 [P] [US4] Write `tests/contract/test_browse_contract.py`: `GET /api/v1/me/readings` with `q`, `author_id`, `series_id`, `status`, `sort`, `page`, `page_size` (including a 422 for `page_size=500`) and `GET /api/v1/me/series/{id}`; each response passes `assert_matches_contract` (AC-21, AC-22, AC-23)
- [X] T093 [P] [US4] Write `tests/integration/test_browse_pages.py`: the list page's search box, sort select and filter selects update the list via HTMX (`hx-get`, `hx-push-url`) and also work as a plain GET form without JavaScript; `GET /series/{id}` shows the member's books in series order; series names on the list link to the series page; **cross-user (Principle I)**: with Ben owning entries in the same series, Alice's `GET /series/{id}` page and her list page filtered by that series show none of Ben's entries or notes (AC-21, AC-22, AC-23)

### Implementation for User Story 4

- [X] T094 [US4] Extend `ReadingEntryRepository.list` in `src/book_tracker/persistence/readings.py` with `q`, `author_id`, `series_id`, `status` and `sort` (author sorts by the first author's `sort_name`; series sorts by series name then number, nulls last), and add `list_series(series_id)` ordered by `series_number` with nulls last, then title; every query keeps the bound-user filter; make T091's repository-level cases pass (FR-021, FR-022, FR-023)
- [X] T095 [US4] Add the query parameters to `GET /me/readings` and add `GET /me/series/{series_id}` in `src/book_tracker/api/readings.py`, declaring responses from `api/responses.py`, with service functions in `src/book_tracker/services/readings.py`; make T091 and T092 pass (FR-021, FR-022, FR-023)
- [X] T096 [US4] Add search, sort and filter controls to `src/book_tracker/web/templates/pages/list.html`, and add `GET /series/{id}` with `pages/series.html` to `src/book_tracker/web/routes/readings.py`; make T093 pass (FR-021, FR-022, FR-023)

**Checkpoint**: Large lists are easy to navigate; Stories 1–4 all work independently.

---

## Phase 7: User Story 5 - Write and keep a book summary (Priority: P3)

**Goal**: Any member writes a summary for a catalog book; one current summary is shared, and history is kept.

**Independent Test**: A member writes a summary, another member sees it and then replaces it; the latest is shown and the earlier one is kept.

### Tests for User Story 5 ⚠️

> **Write these tests FIRST and confirm they FAIL before T100.**

- [X] T097 [P] [US5] Write `tests/integration/test_summaries.py`: Alice's `POST /api/v1/books/{id}/summaries` creates a current summary with `origin = "manual"`, `created_by` Alice and a timestamp, and Ben sees it as `current_summary` on `GET /api/v1/books/{id}` (AC-24); Ben saving a new summary makes his current and keeps Alice's in `GET /api/v1/books/{id}/summaries`, newest first (AC-25); two concurrent saves leave exactly one current summary; a `summary` given in `new_book` when adding to a list is saved the same way (FR-024, FR-025)
- [X] T098 [P] [US5] Write `tests/contract/test_summaries_contract.py`: `GET` and `POST /api/v1/books/{id}/summaries`, including 404 for an unknown book and 422 for empty or over-5,000-character text; each response passes `assert_matches_contract` (AC-24, AC-25)
- [X] T099 [P] [US5] Write `tests/integration/test_summary_pages.py`: `GET /catalog/books/{id}/summary` shows the current summary and history with author and date; posting the form saves a new current summary; `pages/entry.html` shows the current summary with "Written by <name> on <date>" (AC-24, AC-25)

### Implementation for User Story 5

- [X] T100 [P] [US5] Add `SummaryCreate` to `src/book_tracker/schemas/catalog.py` (text trimmed, 1–5,000 characters) (FR-024)
- [X] T101 [US5] Add `list_summaries(book_id)` and `save_summary(book_id, text, origin, actor_id)` to `src/book_tracker/persistence/catalog.py`; `save_summary` locks the book row `FOR UPDATE`, sets the current summary's `is_current` to false and inserts the new one in one transaction (FR-024, FR-025)
- [X] T102 [US5] Implement `src/book_tracker/services/summaries.py` (`save_manual_summary`, `history`) and add `GET`/`POST /books/{book_id}/summaries` to `src/book_tracker/api/books.py`, declaring responses from `api/responses.py`; call `save_manual_summary` from `add_entry` in `src/book_tracker/services/readings.py` when `new_book.summary` is set; make T097 and T098 pass (FR-024, FR-025)
- [X] T103 [US5] Add `GET`/`POST /catalog/books/{id}/summary` with `pages/summary.html` to `src/book_tracker/web/routes/catalog.py`, an optional summary field to `pages/add_book.html`, and the current summary with attribution to `pages/entry.html`; make T099 pass (FR-024, FR-025)

**Checkpoint**: All five user stories work independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility, performance, security hardening and release readiness across all stories

### Tests ⚠️

> **Write T104–T108 FIRST and confirm they FAIL (or expose violations) before T109–T111.**

- [X] T104 Create `tests/a11y/conftest.py`: starts the app with uvicorn in a background thread against the test database on a free port, seeds an Admin, two members, a series with numbered books and a summary, and provides a signed-in Playwright `page` fixture plus a helper `assert_no_axe_violations(page)` that runs axe-core via `axe-playwright-python` with tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`
- [X] T105 [P] Write `tests/a11y/test_axe_pages.py` (marker `a11y`): every page in contracts/ui-routes.md that renders HTML (sign-in, change password, list, add book, entry, series, each edit page, summary, admin users, new user), plus the add-book page with validation errors and with the suggestions open, has zero axe violations (FR-030, SC-007)
- [X] T106 [P] Write `tests/a11y/test_keyboard_journeys.py` (marker `a11y`): using only `page.keyboard`, complete sign in, add a book choosing an author from suggestions, edit an entry's status, and switch user, checking that focus is visible and moves in a logical order (FR-030, SC-007)
- [X] T107 [P] Write `tests/a11y/test_responsive.py` (marker `a11y`): at a 360 × 740 viewport, every page from T105 has `document.documentElement.scrollWidth <= window.innerWidth` and all controls are at least 44 × 44 px (FR-026, SC-006)
- [X] T108 [P] Write `tests/perf/test_list_performance.py` (marker `perf`): seed 5,000 books, about 1,500 authors, 300 series and 2,000 entries for one member; 100 requests each to `/` and `/api/v1/me/readings` across sort and filter options have p95 under 1 s (SC-002); 100 type-ahead requests each to `/api/v1/books?q=`, `/authors?q=` and `/series?q=` have p95 under 300 ms (SC-008)
- [X] T109 [P] Write `tests/integration/test_security_headers.py`: every HTML response sets `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin`; in `production`, plain-HTTP requests redirect to HTTPS and responses set `Strict-Transport-Security` (Principle IX)

### Implementation

- [X] T110 Fix every accessibility and responsive-layout failure found by T105–T107 in `src/book_tracker/web/templates/` and `src/book_tracker/web/static/css/app.css` until `uv run pytest -m a11y` passes (FR-026, FR-030)
- [X] T111 Add a security-headers middleware and the production HTTPS redirect to `src/book_tracker/main.py`; make T109 pass (Principle IX)
- [X] T112 Run `uv run pytest -m perf`; if SC-002 or the type-ahead budget fails, add a reversible migration `migrations/versions/0002_trgm_indexes.py` creating `pg_trgm` GIN indexes on `book.title`, `author.name`, `author.real_name` and `series.name` (research R7), then re-run until it passes
- [X] T113 Run `uv run pytest --cov --cov-report=json` and `python scripts/check_coverage.py`; add tests under `tests/` until overall coverage is at least 85% and every coverage-critical module is at 100% (Principle V)
- [X] T114 Run `python -m book_tracker.export_openapi` and compare it with `specs/001-family-reading-list/contracts/openapi.yaml` using `oasdiff diff`; fix the code (or, for a contract mistake, the contract, with a note in plan.md) until there are no differences other than descriptions
- [X] T115 [P] Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src` and `uv run pip-audit` over `src/book_tracker/` and `tests/`, and fix every finding (each remaining `type: ignore` has an error code and a reason; any accepted `pip-audit` exception goes in `.pip-audit-ignore` with a reason and review date)
- [X] T116 [P] Update the "Build & Test" section of `CLAUDE.md` with the real commands from `specs/001-family-reading-list/quickstart.md`, and remove the "No application code exists yet" note
- [X] T117 Build the container (`docker build -t book-tracker .`), start it with PostgreSQL and `BOOK_TRACKER_ADMIN_LOGIN` set, and walk through every manual scenario in `specs/001-family-reading-list/quickstart.md`, recording any failure as a new task in this file. **Done 2026-11-18**: image built (non-root, `--no-editable` install), run with PostgreSQL 16 and `BOOK_TRACKER_ADMIN_LOGIN`; scenarios 1–10 passed 20/20 checks in Chromium (11 is covered by `tests/a11y`); restart is idempotent. Failures found and fixed: missing `book_tracker.main:app`, `readme = "CLAUDE.md"` breaking the image build, and the entry form's unchanged "Times read" blocking the re-read count
- [ ] T118 **Release gate (blocked until the hosting decision, source document open question 5)**: on the chosen host, schedule the nightly `pg_dump -Fc` with 30-day retention from `specs/001-family-reading-list/quickstart.md` "Backups", run one restore into a scratch database, and record the backup schedule and restore-test date in `docs/release-notes.md`. The first release MUST NOT happen before this task is done (Constitution: Technology Constraints and Release gates)

---

## Traceability

Every acceptance criterion and functional requirement in [spec.md](spec.md) maps to at least one task.

| Requirement | Tasks |
|---|---|
| AC-01 | T019, T020, T039, T041 |
| AC-02 | T019, T020, T039, T041 |
| AC-03 | T049, T050, T051, T058, T061 |
| AC-04 | T047, T048, T054, T061 |
| AC-05 | T014, T049, T050, T051, T058 |
| AC-06 | T014, T046, T049, T053 |
| AC-07 | T049, T050, T051, T058 |
| AC-08 | T049, T051, T058 |
| AC-09 | T062, T064, T067, T068, T072, T073, T074 |
| AC-10 | T017, T062, T068, T072 |
| AC-11 | T064, T072, T075 |
| AC-12 | T065, T073 |
| AC-13 | T065, T073, T074 |
| AC-14 | T065, T073 |
| AC-15 | T076, T080, T081, T084, T087, T089 |
| AC-16 | T014, T049, T057, T077, T080, T081, T086, T089 |
| AC-17 | T078, T082, T083, T087, T090 |
| AC-18 | T014, T078, T082, T083 |
| AC-19 | T014, T049, T057, T077, T081, T086 |
| AC-20 | T015, T079, T091, T026 |
| AC-21 | T091, T092, T093, T094, T095, T096 |
| AC-22 | T091, T092, T093, T094, T095, T096 |
| AC-23 | T091, T092, T093, T094, T095, T096 |
| AC-24 | T097, T098, T099, T101, T102, T103 |
| AC-25 | T097, T098, T099, T101, T102, T103 |
| AC-26 | T062, T067, T068, T072 |
| AC-27 | T021, T043 |
| AC-28 | T066, T075 |
| AC-29 | T014, T062, T067, T072 |
| AC-30 | T014, T015, T049, T057, T077, T081, T086 |
| AC-31 | T045, T046, T049, T058 |
| AC-32 | T079, T081, T082, T085, T087, T090 |
| AC-33 | T063, T067, T070, T071 |
| AC-34 | T062, T069, T072 |
| AC-35 | T045, T049, T058 |
| FR-001 | T019, T020, T039, T041 |
| FR-002 | T017, T062, T039, T072 |
| FR-003 | T062, T069, T072, T073, T074 |
| FR-004 | T062, T064, T072, T073, T075 |
| FR-005 | T062, T072, T074 |
| FR-006 | T021, T043, T009 |
| FR-007 | T066, T075 |
| FR-008 | T014, T062, T072 |
| FR-009 | T055, T057, T079, T085, T087, T090 |
| FR-010 | T076, T084, T087, T088, T089 |
| FR-011 | T014, T049, T057, T061, T077, T086 |
| FR-012 | T052, T055, T057 |
| FR-013 | T014, T015, T046, T052, T057 |
| FR-014 | T078, T083, T087, T090 |
| FR-015 | T015, T057, T076, T077, T084, T086 |
| FR-016 | T049, T053, T058, T059, T061 |
| FR-017 | T049, T058 |
| FR-018 | T046, T049, T053, T058 |
| FR-019 | T049, T058, T059 |
| FR-020 | T047, T048, T054, T059, T091, T093, T094 |
| FR-021 | T091, T094, T095, T096 |
| FR-022 | T091, T094, T095, T096 |
| FR-023 | T091, T094, T095, T096 |
| FR-024 | T097, T100, T101, T102, T103 |
| FR-025 | T097, T101, T102, T103 |
| FR-026 | T040, T107, T110 |
| FR-027 | T063, T070, T071 |
| FR-028 | T037, T062, T064, T069, T072 |
| FR-029 | T045, T049, T058 |
| FR-030 | T040, T082, T088, T105, T106, T110 |
| SC-001 | T117 (timed during the quickstart walk-through) |
| SC-002 | T108, T112 |
| SC-003 | T047, T048, T065 |
| SC-004 | T077, T080 |
| SC-005 | Manual usability check with the family after release (not automatable) |
| SC-006 | T107, T110 |
| SC-007 | T105, T106, T110 |
| SC-008 | T108, T112 |
| Principle VII layer separation | T026, T022, T029, T056, T069 |
| Release gate: backups | T118 |
| CI and review gates | T001, T008 |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately. T010 needs T002. T008 (CI) needs T001 (done: own repository with a GitHub remote).
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 and US2 (both P1) can proceed in parallel
  - US3 builds on US1's catalog code (`persistence/catalog.py`, `services/catalog.py`, `pages/add_book.html`): start it after T061
  - US4 builds on US1's `ReadingEntryRepository` and list page: start it after T061
  - US5 builds on US1's book and entry pages and US3's `web/routes/catalog.py`: start it after T090
- **Polish (Final Phase)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: After Foundational. No dependency on other stories
- **User Story 2 (P1)**: After Foundational. No dependency on other stories (touches `web/routes/auth.py`, `api/auth.py` and the nav in `base.html`, which US1 does not)
- **User Story 3 (P2)**: After US1, because it extends US1's catalog modules and add form
- **User Story 4 (P3)**: After US1. Independent of US2, US3 and US5
- **User Story 5 (P3)**: After US1 and US3

```text
Setup → Foundational ─┬─ US1 ─┬─ US3 ─── US5 ─┐
                      │       └─ US4 ─────────┼─ Polish
                      └─ US2 ─────────────────┘
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Schemas and repositories before services
- Services before API endpoints and pages
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- Setup: T004–T009 in parallel after T002–T003
- Foundational tests: T012–T023 in parallel after T011
- Foundational implementation: T025, T026, T031, T034, T036, T037 in parallel; T043 and T044 in parallel after T042
- US1 and US2 can be built at the same time by two people after Phase 2
- Each story's test tasks marked [P] can all be written at once
- US4 can run in parallel with US3 after US1
- Polish tests T105–T109 in parallel after T104

---

## Parallel Example: User Story 1

```bash
# Write all US1 tests together (all different files):
Task: "T045 Unit tests for apply_status_change in tests/unit/test_times_read.py"
Task: "T046 Schema tests in tests/unit/test_reading_schemas.py"
Task: "T047 Repository ownership tests in tests/integration/test_readings_repository.py"
Task: "T048 Cross-user 404 tests in tests/integration/test_reading_isolation.py"
Task: "T049 Service behaviour tests in tests/integration/test_reading_service.py"
Task: "T050 Contract tests in tests/contract/test_readings_contract.py"
Task: "T051 Page tests in tests/integration/test_reading_pages.py"

# Then the modules that don't depend on each other:
Task: "T052 Catalog schemas in src/book_tracker/schemas/catalog.py"
Task: "T054 ReadingEntryRepository in src/book_tracker/persistence/readings.py"
```

## Parallel Example: User Story 2

```bash
Task: "T062 tests/integration/test_accounts_service.py"
Task: "T063 tests/integration/test_throttle.py"
Task: "T064 tests/integration/test_password_change.py"
Task: "T065 tests/integration/test_admin_access.py"
Task: "T066 tests/integration/test_switch_user.py"
Task: "T067 tests/contract/test_admin_contract.py"
Task: "T068 tests/integration/test_admin_pages.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 and 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1, and validate it independently with factory-created members
4. Complete Phase 4: User Story 2, so a real family can get accounts without the CLI
5. **STOP and VALIDATE**: run quickstart scenarios 1, 2, 6, 7, 8 and 9
6. Demo if ready. A real release needs T118 (backups and restore test) done first

US1 alone is testable, but a real family can't use it without US2: only the CLI-created
Admin would have an account. The smallest *usable* release is US1 + US2.

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 + US2 → usable family app (MVP)
3. US3 → no duplicate typing, pen names, catalog editing
4. US4 → search, sort, filter, series view
5. US5 → shared summaries (and the base for spec 002's AI drafts)
6. Polish → accessibility, performance and security gates green → T118 backup release gate → release

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail for the expected reason before implementing
- Every commit leaves the test suite passing
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
