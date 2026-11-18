# Implementation Plan: Family Reading List

**Branch**: `001-family-reading-list` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-family-reading-list/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Build the first deployable version of the Family Book Tracker. It covers Admin-managed
family accounts with session sign-in, a shared catalog of books, authors and series (with
type-ahead, pen names and hand-written summaries), and a private reading list for each
member with status, re-read count, notes, search and a series view.

It ships as one FastAPI service serving both a JSON API (`/api/v1`) and server-rendered
Jinja2 + HTMX pages, backed by PostgreSQL. Both the API and the pages call one service
layer. Reading entries can only be reached through a repository bound to the session
user. Decisions are recorded in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.0 (async) +
psycopg 3, Alembic, Jinja2, HTMX 2.0.4 (vendored), argon2-cffi, python-multipart, httpx

**Storage**: PostgreSQL 16+ (one database; sessions and sign-in throttling stored there too)

**Testing**: pytest, pytest-asyncio, pytest-cov, testcontainers (PostgreSQL), openapi-core
(contract), pytest-playwright + axe-playwright-python (accessibility); oasdiff in CI
(container image, not a Python dependency)

**Target Platform**: Single Linux container image. Production hosting is a Raspberry Pi 5
(`linux/arm64`) with Docker Compose behind Caddy, per source document section 10. The arm64
build and hosting setup are follow-up work and don't change this feature

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: list pages under 1 s at p95 with 5,000 books (SC-002); type-ahead
suggestions under 300 ms at p95 (SC-008)

**Constraints**: WCAG 2.2 AA (FR-030); usable at phone width without horizontal scrolling
(SC-006); no external network calls at runtime; HTTPS outside local development

**Scale/Scope**: one family, about 2–10 users and a few thousand books; about 25 UI routes
and 29 API operations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked before Phase 0 and again after Phase 1 design. **Result: all gates pass; no
Complexity Tracking entries.**

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | `ReadingEntryRepository` is created with the session user id and has no method that takes a user id from its caller ([data-model.md](data-model.md#ownership-and-access-summary)). Another member's entry returns 404. Each `/me/*` endpoint and entry page gets a cross-user test. Admin routes never return entries (AC-14) |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Placement is stated in the spec's Data Ownership table and data-model.md. `reading_entry` references `book` and holds only personal fields. Removing an entry never deletes the book (FK `RESTRICT`, AC-07) |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | This feature has no AI. Summaries are `origin='manual'` with `created_by` and `created_at` stored. The `book_summary` table already carries `model` and `source_urls`, with `CHECK (origin='manual' OR model IS NOT NULL)`, ready for spec 002 |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | No external sources in this feature. HTMX is vendored, so no CDN request is made |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | tasks.md will order tests first. 35 ACs are each tagged `@pytest.mark.ac("001/AC-xx")`. Four test layers plus `a11y` and `perf` markers. CI makes no live external calls |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | The data-model.md constraints cover the series-number rule, the real-name rule, unique (user, book), one current summary, case-insensitive name uniqueness, ISBN format, and the series-number and times-read ranges. Rules that can't be constraints are listed with how they're enforced ([research R8](research.md#r8-rules-enforced-in-the-service-layer-not-by-the-database)). Every migration has a `downgrade` and is tested in CI with upgrade → downgrade → upgrade. No destructive migrations |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | [contracts/openapi.yaml](contracts/openapi.yaml) covers all 29 operations. UI form input uses the same Pydantic models ([contracts/ui-routes.md](contracts/ui-routes.md)). Three separate layers: SQLAlchemy models (`persistence/models.py`), frozen domain dataclasses (`domain/models.py`) and Pydantic API schemas (`schemas/`). Services take and return domain objects only. `persistence/mappers.py` maps ORM → domain, and `schemas/mappers.py` maps domain → API schemas. Every endpoint declares its responses so the generated OpenAPI matches the contract (research R16). `mypy --strict` |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | One FastAPI service and one PostgreSQL database, with no Redis or SPA. Each dependency is justified below |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Stores display name, login and an Argon2id hash only; no email is required. There are no external calls. Secrets come from the environment. The session cookie is `__Host-`, Secure, HttpOnly and SameSite=Lax. Synchronizer CSRF tokens. Logs are redacted (research R19). Sign-in is throttled per login (FR-027) |

### Coverage-critical modules (Principle V)

These modules must have 100% line coverage, listed in `[tool.coverage]` per-file
thresholds and enforced in CI:

- `src/book_tracker/auth/sessions.py`: session create, look-up, sliding expiry, revoke
- `src/book_tracker/auth/dependencies.py`: `current_user`, `require_admin`,
  `require_password_current`, CSRF check
- `src/book_tracker/auth/throttle.py`: per-login sign-in throttling
- `src/book_tracker/persistence/readings.py`: `ReadingEntryRepository` (ownership filtering)
- `src/book_tracker/services/accounts.py`: last-Admin guard, deactivate, reset

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| fastapi | Web framework (constitution) | — | MIT |
| pydantic | Validation (constitution) | — | MIT |
| pydantic-settings | Typed settings from environment variables | Hand-rolled `os.environ` parsing: untyped | MIT |
| sqlalchemy | ORM (constitution) | — | MIT |
| psycopg[binary] | PostgreSQL driver, async and sync (R5) | asyncpg: Alembic would need a second driver | LGPL-3.0 (used as an unmodified library) |
| alembic | Migrations (constitution) | — | MIT |
| jinja2 | Templates (constitution) | — | BSD-3-Clause |
| python-multipart | Required by FastAPI to parse form posts | None; FastAPI depends on it for `Form` | Apache-2.0 |
| argon2-cffi | Argon2id hashing (Principle IX, R2) | passlib: unmaintained | MIT |
| httpx | HTTP client (constitution); ASGI test client | — | BSD-3-Clause |
| uvicorn | ASGI server in the container | hypercorn: less common, no advantage here | BSD-3-Clause |
| htmx 2.0.4 (vendored JS) | Partial page updates (constitution) | CDN: external request; npm: Node toolchain | 0BSD |
| *dev:* pytest, pytest-asyncio, pytest-cov, testcontainers | Testing (constitution); coverage gate | — | MIT / Apache-2.0 / MIT / Apache-2.0 |
| *dev:* openapi-core | Validates responses against the committed contract (R16) | schemathesis: heavier; can be added later | BSD-3-Clause |
| *dev:* pytest-playwright, axe-playwright-python | WCAG 2.2 AA checks and keyboard journeys (R15) | pa11y and Lighthouse: need Node | Apache-2.0 / MIT (bundles axe-core 4.12.1, MPL-2.0) |
| *dev:* ruff, mypy, pip-audit | Quality gates (constitution) | — | MIT / MIT / Apache-2.0 |

Licenses confirmed against installed package metadata on 2026-11-18 (task T010). Corrections
made then: pytest-asyncio is Apache-2.0; axe-playwright-python is MIT and bundles axe-core
(MPL-2.0). Resolved versions are pinned in `uv.lock`.

### Migrations (Principle VI)

- **Schema changes**: one initial migration, `0001_initial`, creating all nine tables and
  their constraints and indexes from [data-model.md](data-model.md). Its `downgrade` drops
  them in reverse dependency order.
- **Destructive changes**: None.

## Project Structure

### Documentation (this feature)

```text
specs/001-family-reading-list/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R20
├── data-model.md        # Phase 1: tables, constraints, state transitions
├── quickstart.md        # Phase 1: run and validation guide
├── contracts/
│   ├── openapi.yaml     # Phase 1: JSON API contract (29 operations)
│   └── ui-routes.md     # Phase 1: server-rendered routes (not in OpenAPI)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                # uv project; ruff, mypy, pytest, coverage config
uv.lock
Dockerfile                    # single image: migrate, optional first Admin, uvicorn
alembic.ini
migrations/
└── versions/0001_initial.py

src/book_tracker/
├── main.py                   # app factory: mounts api/ and web/, static files
├── settings.py               # pydantic-settings (BOOK_TRACKER_*)
├── cli.py                    # `book-tracker create-admin`
├── export_openapi.py         # writes app.openapi() for the CI contract check
├── logging.py                # JSON formatter + redaction filter
├── auth/
│   ├── passwords.py          # Argon2id hash/verify/rehash
│   ├── sessions.py           # server-side sessions        [100% coverage]
│   ├── throttle.py           # per-login sign-in limit     [100% coverage]
│   ├── csrf.py               # pre-session token signing
│   └── dependencies.py       # current_user, require_admin, CSRF  [100% coverage]
├── api/                      # JSON routers under /api/v1
│   ├── auth.py  me.py  readings.py  books.py  authors.py  series.py  admin.py
│   ├── errors.py             # Problem / Conflict / ValidationProblem responses
│   └── responses.py          # shared `responses=` maps so generated OpenAPI matches the contract
├── web/                      # server-rendered routes
│   ├── routes/ (auth.py, readings.py, catalog.py, admin.py, suggest.py)
│   ├── templates/            # base.html, pages/, partials/ (HTMX fragments)
│   └── static/ (css/app.css, vendor/htmx.min.js, vendor/README.md)
├── schemas/                  # Pydantic v2 request/response/form models; mappers.py (domain → schema)
├── domain/                   # models.py (frozen dataclasses), enums, value objects (Isbn13, SeriesNumber), sort-name rule
├── services/                 # accounts.py [100%], readings.py, catalog.py, summaries.py,
│                             #   errors.py (error types raised by services; mapped to HTTP in api/errors.py)
└── persistence/
    ├── db.py                 # async engine/session
    ├── models.py             # SQLAlchemy models
    ├── mappers.py            # ORM models → domain dataclasses
    ├── readings.py           # ReadingEntryRepository (bound to user)  [100% coverage]
    ├── catalog.py            # authors, series, books, summaries
    └── accounts.py           # users, sessions, throttle rows

tests/
├── conftest.py               # PostgreSQL testcontainer, app client, user factories, ac marker
├── unit/                     # domain rules, schemas, times-read transitions
├── integration/              # repositories, constraints, services, migrations, cross-user
├── contract/                 # responses validated against contracts/openapi.yaml
├── a11y/                     # axe-core WCAG 2.2 AA + keyboard journeys (marker: a11y)
└── perf/                     # 5,000-book p95 test (marker: perf)
```

**Structure Decision**: a single project under `src/book_tracker/`, the default layout
from the plan template, with an `auth/` package added. Authentication code is kept in its
own package so the coverage-critical modules are easy to find and configure. There is no
`tests/external/` layer yet, because this feature calls no external services. Spec 002 adds
it with the source adapters.

## Complexity Tracking

> **Fill ONLY for a "No" on Constitution Check rows II, IV, VI, VII, VIII or IX.**
> Rows I, III and V cannot be justified here.

No entries: every Constitution Check row is "Yes".

## Contract changes during implementation

- **2026-11-18 (T114)**: added `422 ValidationError` responses to 11 operations that take a
  UUID path parameter or a type-ahead `q` (the API returns 422 for an invalid UUID or an
  empty query). Found by comparing FastAPI's generated document with the contract; after the
  change their operations, status codes, media types and parameters match. Adding responses
  is not a breaking change.
- **2026-11-18 (T114, Docker run)**: the CI breaking-change check now compares against a
  committed generated baseline, `contracts/openapi.generated.json` (research R16, revised).
  Problem `detail` and Conflict `existing_label` are documented as plain strings, since they
  are omitted rather than sent as null.
