# Research: Family Reading List

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-11-18

The stack is fixed by the constitution's Technology Constraints. This document records
the decisions the spec and constitution leave open. Every Technical Context unknown is
resolved below.

## R1. Sessions

- **Decision**: server-side sessions stored in a PostgreSQL `user_session` table. The
  browser holds an opaque random token (32 bytes from `secrets.token_urlsafe`) in a cookie
  named `__Host-session`, marked Secure, HttpOnly and SameSite=Lax. The database stores only
  a SHA-256 hash of the token. A session expires after 14 days without use; each request
  slides `last_seen_at` forward, written at most once per minute.
- **Rationale**: deactivating an account, resetting a password and signing out must end
  sessions immediately (FR-002, edge case "deactivated while signed in"). A server-side
  session is deleted in one statement. Hashing the token means a database leak does not
  hand out live sessions. PostgreSQL is already the only datastore (Principle VIII).
- **Alternatives considered**: Starlette's signed-cookie `SessionMiddleware` can't be revoked
  server-side. JWTs have the same revocation problem and add a dependency. Redis would be a
  second datastore, which the constitution forbids.

## R2. Password hashing and rules

- **Decision**: `argon2-cffi`'s `PasswordHasher` (Argon2id) with its default parameters,
  which follow RFC 9106's recommended low-memory profile. Re-hash on sign-in when
  `check_needs_rehash` reports outdated parameters. Passwords are 8–128 characters with no
  complexity rules (FR-028; 128 meets the "no maximum below 64" rule and bounds hashing cost).
- **Rationale**: Principle IX requires Argon2id. The library default is maintained against
  current guidance, and re-hashing on sign-in keeps old hashes current.
- **Alternatives considered**: `passlib` is unmaintained. bcrypt is not Argon2id.

## R3. Sign-in throttling (FR-027)

- **Decision**: a `login_throttle` table keyed by an HMAC-SHA256 (with `SECRET_KEY`) of the
  normalized login string (lowercase, trimmed), so attempted logins, including typos and
  email addresses of people outside the family, are never stored as text. The table holds `failed_count`, `locked_until` and `updated_at`. Rows exist for logins
  that don't match any account too, so throttling behaves the same either way. On every
  failed attempt for an unknown login, the server still verifies against a fixed dummy
  Argon2 hash, so response time does not reveal whether the login exists. The fifth
  consecutive failure sets `locked_until = now + 15 minutes`. While locked, attempts are
  refused before the password is checked, are not counted, and don't extend the lock. A
  success deletes the row.
  Rows older than 24 hours are pruned on sign-in.
- **Rationale**: per-login counting is what the spec asks for. Storing it in PostgreSQL
  needs no extra infrastructure, and identical behaviour for real and unknown logins avoids
  revealing which logins exist.
- **Alternatives considered**: per-IP rate limiting (`slowapi`) doesn't match the
  per-login rule, and family members share one home IP. An in-memory counter is lost on
  restart and would break if a second process were ever run.

## R4. CSRF protection

- **Decision**: synchronizer token. Each session row stores a random CSRF token. Every
  state-changing request (POST, PATCH, PUT, DELETE) authenticated by the session cookie must
  carry it, either as a hidden `csrf_token` form field (plain forms) or an `X-CSRF-Token`
  header. HTMX sets the header for every request through `hx-headers` on `<body>`, and the
  JSON API reads the token from `GET /api/v1/me`. Sign-in uses a pre-session token from a
  short-lived signed cookie. A FastAPI dependency enforces the check. Failure returns 403.
- **Rationale**: Principle IX requires CSRF protection on state-changing form posts. The JSON
  API is cookie-authenticated too, so it needs the same protection. Keeping the token in the
  session row ties it to the session and needs no new library.
- **Alternatives considered**: `starlette-csrf` (double-submit cookie) adds a dependency for
  about 40 lines of code. SameSite=Lax alone does not cover all cases, such as older
  browsers and same-site subdomains.

## R5. Database driver and session style

- **Decision**: SQLAlchemy 2.0 async ORM with the `psycopg` (version 3) driver
  (`postgresql+psycopg://`). Alembic runs migrations through the same driver in sync mode.
- **Rationale**: one driver serves both the async app and sync migrations. psycopg 3 is the
  PostgreSQL project's maintained driver. Async matches FastAPI and the constitution's
  `pytest-asyncio`.
- **Alternatives considered**: `asyncpg` is faster, but Alembic would then need a second
  driver or an async env. A sync SQLAlchemy app is viable at family scale but would block
  the event loop on every query.

## R6. Case-insensitive uniqueness

- **Decision**: unique functional indexes on `lower(name)` for `author` and `series`, and on
  `lower(login)` for `app_user`. Values are stored as entered and also trimmed, with inner
  whitespace collapsed, before saving.
- **Rationale**: this matches the source document's "unique index on lower(name)", needs no
  extension, and keeps the display spelling.
- **Alternatives considered**: the `citext` extension changes comparison semantics for every
  query on the column and is one more extension to manage. A non-deterministic ICU collation
  doesn't support `LIKE`, which type-ahead needs.

## R7. Type-ahead and search (FR-010, FR-023)

- **Decision**: `ILIKE` with `%term%` on the relevant columns: book title, author name and
  real name, series name. For books, a term that normalizes to a valid ISBN-13 also matches
  `isbn_13` exactly and ranks first. Each query is limited to 10 suggestions. Prefix matches rank first
  (`ORDER BY (col ILIKE 'term%') DESC, col`), and `%` and `_` in the search term are escaped.
  A `pg_trgm` GIN index is added only if the performance test (SC-002) fails.
- **Rationale**: at about 5,000 books and fewer authors, a sequential scan with `ILIKE`
  takes milliseconds. Adding an index before a measurement shows it's needed would go
  against Principle VIII.
- **Alternatives considered**: PostgreSQL full-text search (`tsvector`) handles partial words
  in type-ahead poorly. `pg_trgm` is good but not yet needed. A separate search engine is
  forbidden by Principle VIII.

## R8. Rules enforced in the service layer, not by the database

Principle VI asks for database enforcement wherever a rule is relational. These rules are
not, so a service enforces them inside a transaction:

| Rule | Why not a constraint | Service enforcement |
|---|---|---|
| Last active Admin cannot be deactivated or demoted (FR-005) | A rule across many rows ("at least one") | `SELECT … FOR UPDATE` on active Admin rows in the same transaction, then check the count |
| Times read increments when status changes to Finished (FR-029) | A state transition, not a static rule | `ReadingService.update` compares old and new status. The database still enforces the 0–99 range |
| Date finished not in the future | `CHECK (finished_on <= current_date)` would fail on rows saved before a server clock change | Pydantic validation, plus a DB `CHECK (finished_on >= '1900-01-01')` sanity bound |
| One current summary per book | **Is** relational: partial unique index | DB partial unique index; the service flips `is_current` in one transaction |

## R9. Concurrent duplicate creation (edge case)

- **Decision**: catalog creates rely on the unique indexes. When an `IntegrityError` names
  a uniqueness index, the service looks up the existing row and returns `409 Conflict` with
  that row's id and name, so the UI can offer it. The same applies to series + number and
  ISBN collisions.
- **Rationale**: the database decides who wins without races. The second member is shown
  the existing entry, not a raw error.
- **Alternatives considered**: checking before inserting still races, and a table lock
  is too heavy for the benefit.

## R10. Concurrent catalog edits

- **Decision**: last save wins (accepted as low impact in the clarify session). Every edit
  updates `updated_by` and `updated_at`.
- **Alternatives considered**: optimistic locking with a version column and `If-Match`. It
  can be added later without breaking the API, by making `version` an optional field.

## R11. Recently used profiles (FR-007)

- **Decision**: a cookie named `recent_profiles`, marked HttpOnly, Secure and SameSite=Lax,
  lasting 90 days. It holds up to 5 user UUIDs, most recent first, and is updated at each
  successful sign-in. The sign-in page shows the display name and login of each listed
  account that is still active. "Switch user" deletes the session and leaves this cookie.
- **Rationale**: UUIDs reveal nothing and can't be guessed. The server shows only active
  accounts, so deactivated members disappear from the list. No new personal data is stored
  on the server (Principle IX).
- **Alternatives considered**: storing display names in `localStorage` would need
  JavaScript, and the data would go stale. A server-side "device" table would track devices,
  which is more personal data than needed.

## R12. First Admin account (FR-006, AC-27)

- **Decision**: a command `book-tracker create-admin --login <login> --display-name <name>`,
  which reads the password from a prompt or the `BOOK_TRACKER_ADMIN_PASSWORD` environment
  variable. It refuses to run if any Admin account exists. The container entrypoint runs
  `alembic upgrade head` and then, when `BOOK_TRACKER_ADMIN_LOGIN` is set and no Admin
  exists, creates the Admin.
- **Rationale**: no unauthenticated setup screen exists to be hijacked. The command works
  for both a container install and a home install.
- **Alternatives considered**: a first-run web wizard leaves a takeover window until
  someone completes it. Seeding the Admin in a migration would put a credential in the
  repository.

## R13. Forced password change (FR-004, AC-11)

- **Decision**: an `app_user.must_change_password` flag is set by an Admin reset and by
  account creation. While it is set, a dependency allows only the change-password page and
  `POST /api/v1/auth/password` plus sign-out. All other UI routes redirect, and other API
  calls return `403` with code `password_change_required`. Changing the password clears
  the flag and ends every other session for that user.

## R14. HTMX delivery

- **Decision**: vendor `htmx.min.js` **2.0.4** into `src/book_tracker/web/static/vendor/`,
  with a version comment and its SHA-384 hash recorded in `static/vendor/README.md`. It is
  served by the app, with no CDN.
- **Rationale**: the app works on a home server with no external fetch. Nothing is loaded
  from a third party (Principle IX). Vendoring the file needs no JavaScript build step.
- **Alternatives considered**: loading from a CDN adds an external request on every page.
  Using npm would add a Node toolchain to a Python-only project.

## R15. Accessibility testing (FR-030, SC-007)

- **Decision**: browser tests with `pytest-playwright` (Chromium) in `tests/a11y/`. Each
  screen is checked with axe-core (via `axe-playwright-python`) for the WCAG 2.2 AA tag set
  (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), and fails on any violation.
  Separate tests drive the four main journeys (sign in, add a book, edit an entry, switch
  user) using only keyboard input. Templates follow these rules: one `<h1>` per page, a
  `<label>` for every input, visible focus styles, and `aria-live="polite"` on regions HTMX
  swaps in, such as validation messages and type-ahead results.
- **Rationale**: axe-core is the standard automated checker. Keyboard journey tests cover
  what automation can't catch, such as focus order.
- **Alternatives considered**: `pa11y` and Lighthouse need Node. A manual audit alone can't
  run in CI.

## R16. Contract testing and breaking-change detection

- **Decision**: the committed contract is
  [contracts/openapi.yaml](contracts/openapi.yaml). Contract tests in `tests/contract/` call
  the app through `httpx.ASGITransport`, and the `openapi-core` library validates each
  response against the committed contract. A CI step exports `app.openapi()` and compares
  it with the committed file using `oasdiff breaking`, run from its published container
  image, so nothing is added to the Python dependencies. The step fails on breaking
  changes unless the PR's spec declares them.
- **Making the generated document match**: FastAPI's defaults would differ from the
  contract, so the comparison would fail on every run. To prevent that:
  - every route declares its error responses from shared `responses=` maps in
    `api/responses.py`, with `application/problem+json` content;
  - `create_app` replaces FastAPI's default 422 `HTTPValidationError` schema with
    `ValidationProblem`;
  - Pydantic response models use the contract's component names;
  - `response_model_exclude_none` is not used, so nullable fields appear as the contract
    defines them.
- **Rationale**: these are the two checks the constitution asks for: responses match the
  contract, and contract drift is caught.
- **Revised 2026-11-18 (implementation)**: running `oasdiff breaking` between the hand-written
  `openapi.yaml` and FastAPI's output reported 115 "breaking" changes that were all
  representational: Pydantic writes optional fields as `anyOf [X, null]`, FastAPI declares
  path parameters per operation, and the `oneOf` rule for `ReadingEntryCreate` lives in a
  validator. So the CI check now compares each change's generated document with the
  **generated baseline** committed as `contracts/openapi.generated.json`, taken from the
  base branch. `tests/contract/test_generated_baseline.py` fails if that baseline is stale.
  The hand-written `openapi.yaml` stays the design contract, and every response in the
  contract tests is still validated against it. A deliberate breaking change needs a spec
  that declares it and the PR label `breaking-api`.
- **Alternatives considered**: `schemathesis` (property-based) is valuable but heavier; it
  can be added later. Comparing the files as text flags harmless reordering.

## R17. Performance test (SC-002)

- **Decision**: `tests/perf/test_list_performance.py`, marked `@pytest.mark.perf`. It seeds
  5,000 books (with about 1,500 authors, 300 series and 2,000 entries for one member) into
  the test PostgreSQL. It then makes 100 requests to `/` and `/api/v1/me/readings`, using
  the sort and filter options, through the ASGI app, and asserts p95 under 1 s. It runs in
  CI on every merge.
- **Rationale**: this is the gate the constitution sets. In-process requests leave out
  network time, which is negligible for a home network.
- **Alternatives considered**: `locust` is a new tool and is load-oriented. The budget is
  about latency, not throughput.

## R18. Pagination

- **Decision**: list endpoints use `page` (from 1) and `page_size` (default 50, max 200),
  and return `total`. The UI pages at 50 entries per page.
- **Rationale**: at 2,000 entries per member, rendering every row at once would put the
  1 s budget at risk on a phone.

## R19. Configuration, logging and secrets

- **Decision**: settings use `pydantic-settings` with the `BOOK_TRACKER_` prefix
  (`DATABASE_URL`, `SECRET_KEY` for the signed pre-session cookie, `ENVIRONMENT`). Logging
  uses the standard library with a JSON formatter and a redaction filter that removes
  `password`, `token`, `csrf_token`, `notes` and cookie values. Request logs record the
  method, the route template (not the raw path) and the status code.
- **Rationale**: Principle IX says logs must never contain secrets or notes. Logging the
  route template keeps entry ids out of the logs.

## R20. Backups (release gate)

- **Decision**: no backup code ships in this feature. `quickstart.md` documents a nightly
  `pg_dump -Fc` with 30-day retention and a restore test. A full backup setup is required
  before the first release.
- **Updated 2026-11-18**: hosting is now decided (source document section 10: a Raspberry Pi
  with Docker Compose). The nightly dump runs in the `db` container on a systemd timer and
  writes to the NAS, with an encrypted restic copy off-site. The off-site destination is
  still open and blocks go-live, along with the restore test (T118).
- **Rationale**: backups depend on where the app is hosted. The constitution makes them a
  release gate, not a gate on merging code.
