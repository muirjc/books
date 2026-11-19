# Implementation Plan: Import an Author's Books

**Branch**: `002-author-book-import` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-author-book-import/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A member searches Open Library for an author, picks the right one when several share a name,
sees the author's works de-duplicated and marked "Already on your list" or "In the family
catalog", ticks the ones they want with one status, and confirms. The ticked works go onto
that member's list only; works new to the family become catalog books (title and authors only;
no series or ISBN), each linked to its Open Library record.

Open Library is the only source (decision books-zl3: Google Books' terms forbid altering its
results; follow-up books-395). It sits behind a new source-adapter interface with recorded
HTTP fixtures in tests. Lookups are cached for 24 hours in a PostgreSQL table, which also holds
the draft list until the member confirms, so provenance comes from the server's copy, not the
browser. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: as spec 001 (FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.0
async + psycopg 3, Alembic, Jinja2, vendored HTMX 2.0.4, httpx). No new packages

**Storage**: PostgreSQL 16+; two new tables (`book_source_ref`, `source_lookup_cache`)

**Testing**: pytest, pytest-asyncio, testcontainers, openapi-core, pytest-playwright + axe;
new `tests/external/` layer replaying recorded Open Library responses with
`httpx.MockTransport` (research R14)

**Target Platform**: single Linux container image; production on the Raspberry Pi 5 behind
Caddy, which already allows outbound HTTPS (research R16)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: list pages under 1 s at p95 with 5,000 books (unchanged); an author's
works list under 5 s at p95 with Open Library answering normally (measured about 1.1 s for
239 works), and under 1 s from the cache (SC-002)

**Constraints**: Open Library only; at most 1 request/s per app process (2 processes, so 2/s,
under the 3/s Open Library allows identified clients); 10 s timeout per call (FR-016); requests
carry only an author name or Open Library ids (FR-015); WCAG 2.2 AA; no custom JavaScript

**Scale/Scope**: one family; up to 2,000 works per author list (FR-020); 3 new API operations
and 4 UI routes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked before Phase 0 and again after Phase 1 design. **Result: all gates pass; no
Complexity Tracking entries.**

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | Import endpoints take the user from `current_user` only; no request carries a user id. List state and new entries go through `ReadingEntryRepository(db, user.id)`, whose new `book_ids_on_list` takes no user id. Cross-user tests: Alice's import never reaches Ben's list or his "on my list" marks (AC-18, research R10) |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec Data Ownership table and [data-model.md](data-model.md). Book, authors and `book_source_ref` are catalog; the entry holds only the link and status. The cache is neither and holds no user ids. Authors are reused by case-insensitive name, and books by source id, ISBN or title + first author (research R6) |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI in this feature. Its caching rule is followed for source lookups (24 h, outside the catalog, never shown as catalog content). Imported data follows the same draft-then-confirm rule (FR-007), with provenance in `book_source_ref` (FR-009). Adding by hand stays available when Open Library fails (AC-13) |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | Open Library's official API, whose terms permit it (research R2), behind the `BookSource` interface (R4). The adapter can reach only the configured Open Library base URL. Google Books was checked and excluded (R1). No LLM web search in this feature |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | tasks.md will put tests first. 20 ACs, each tagged `@pytest.mark.ac("002/AC-xx")`; the tag check in `tests/conftest.py` is widened from `001/` to any three-digit feature. Layers: unit (matching rules), integration (constraints, concurrency, cross-user), contract, external (recorded fixtures; CI makes no live calls), a11y and perf |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | Unique (source, source work id) and (book, source), the source and kind CHECKs, the Open Library id format CHECK and the expiry CHECK ([data-model.md](data-model.md)). `0002_author_import` has a downgrade and runs in the upgrade → downgrade → upgrade test. Its downgrade drops `book_source_ref`, so a production downgrade needs a backup first, which is documented in data-model.md |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | [contracts/openapi.yaml](contracts/openapi.yaml) covers the 3 new operations; [contracts/ui-routes.md](contracts/ui-routes.md) covers the pages, which use the same Pydantic models and services. Open Library responses are parsed into Pydantic models in the adapter, then mapped to frozen domain dataclasses; raw dicts never leave `sources/`. `mypy --strict` |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | Same service and database. The cache is a table, not Redis. No new packages: `httpx.MockTransport` replaces respx or vcrpy |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | No new personal data. The importer is recorded as `created_by` and `imported_by`, as for any catalog change. Requests to Open Library carry only the typed author name or Open Library ids. The optional User-Agent contact comes from operator configuration, never from a user (R2). No secrets are added. Logs record call kind, status and duration only (R9) |

### Coverage-critical modules (Principle V)

Added to `CRITICAL_MODULES` in `scripts/check_coverage.py` (100% line coverage, enforced in CI):

- `src/book_tracker/persistence/readings.py`: already critical; gains `book_ids_on_list`
- `src/book_tracker/services/imports.py` (new): decides which member's list receives entries
  and computes per-member list state

The script's docstring is updated to point at both plans.

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| None | `httpx` (already a dependency) is the Open Library client; `httpx.MockTransport` replays fixtures | respx, vcrpy: extra dependencies for what MockTransport already does | — |

### Migrations (Principle VI)

- **Schema changes**: `0002_author_import` creates `book_source_ref` and
  `source_lookup_cache` with the constraints and indexes in [data-model.md](data-model.md).
- **Destructive changes**: none on upgrade. The downgrade drops both new tables, losing
  source links (imported books stay). Take and check a backup with `books-backup.sh` before a
  production downgrade.

## Project Structure

### Documentation (this feature)

```text
specs/002-author-book-import/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R16
├── data-model.md        # Phase 1: new tables, domain objects, migration
├── quickstart.md        # Phase 1: run and validation guide
├── contracts/
│   ├── openapi.yaml     # Phase 1: the 3 new JSON API operations
│   └── ui-routes.md     # Phase 1: the 4 new server-rendered routes
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
migrations/versions/0002_author_import.py      # new: two tables, reversible

src/book_tracker/
├── settings.py                 # + openlibrary_base_url, openlibrary_contact, source_timeout_seconds
├── main.py                     # + import routers; BookSource on app.state (overridable in tests)
├── sources/                    # new package
│   ├── base.py                 # BookSource protocol, SourceUnavailable
│   ├── open_library.py         # Open Library adapter (httpx, Pydantic response models)
│   └── rate_limit.py           # per-process 1 request/s limiter
├── domain/
│   ├── imports.py              # AuthorCandidate, WorkCandidate, WorkList, WorkState, ImportResult
│   └── matching.py             # normalize_title, normalize_person_name, isbn10_to_13, merge_duplicate_works
├── services/
│   └── imports.py              # search_authors, list_works, confirm_import   [100% coverage]
├── persistence/
│   ├── models.py               # + BookSourceRef, SourceLookupCache
│   ├── source_cache.py         # cache get/put/expire
│   ├── imports.py              # source-ref lookups and inserts; catalog matching queries
│   └── readings.py             # + ReadingEntryRepository.book_ids_on_list   [100% coverage]
├── schemas/imports.py          # Pydantic API + form models for the 3 operations
├── api/imports.py              # /import/authors, /import/authors/{key}/works, /me/imports
└── web/
    ├── routes/imports.py       # /import pages (contracts/ui-routes.md)
    └── templates/pages/import_*.html, partials/import_works.html

tests/
├── conftest.py                 # ac tag check widened to NNN/AC-xx; FakeBookSource fixture
├── fakes.py                    # FakeBookSource
├── unit/test_matching.py       # normalization, ISBN-10 → 13, duplicate merge
├── external/                   # new layer
│   ├── fixtures/open_library/*.json
│   └── test_open_library.py    # adapter parsing, errors, timeout, truncation
├── integration/test_imports*.py  # service, constraints, concurrency (AC-16), cross-user (AC-18)
├── contract/test_imports_contract.py  # against specs/002-author-book-import/contracts/openapi.yaml
├── a11y/                       # + import pages in axe, keyboard and phone-width tests
└── perf/test_import_perf.py    # 300 works, cache warm, p95 < 1 s

scripts/
├── check_coverage.py           # + services/imports.py
└── record_open_library_fixtures.py  # manual re-capture of fixtures; never run in CI

specs/001-family-reading-list/contracts/openapi.generated.json  # regenerated baseline (CI check)
deploy/pi/.env.example          # + optional BOOK_TRACKER_OPENLIBRARY_CONTACT
```

**Structure Decision**: the existing single project. Adds the `sources/` package the plan
template reserves for source adapters, and the `tests/external/` layer that spec 001 deferred.
The contract-test helper (`tests/contract/conftest.py`) changes from one hard-coded contract
path to one per feature, so 002's tests validate against 002's file. The generated-OpenAPI
baseline stays at the path CI already uses, under spec 001, and is regenerated.

## Complexity Tracking

> **Fill ONLY for a "No" on Constitution Check rows II, IV, VI, VII, VIII or IX.**
> Rows I, III and V cannot be justified here.

No entries: every Constitution Check row is "Yes".

## Spec changes made during planning

- **Open Library only** (research R1, decision books-zl3): Google Books and the Admin site
  setting removed; user story 4 and its criteria dropped.
- **No series or ISBN import** (research R3): Open Library's work data doesn't carry them
  reliably; ISBNs are used only for matching. AC-14 and AC-15 rewritten; FR-010 and FR-011
  changed.
- **2,000-work cap** (FR-020, AC-20) and **expired results at confirm** (edge case, research R8)
  added.
