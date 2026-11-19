<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.0.1 (PATCH: clarification), 2026-11-19

Principle III: the caching rule now states the keys for lookups made for an author (spec 002,
author import), not only for one book. Lookups and drafts for one book are still keyed by
ISBN or normalized title + author; author lookups are keyed by the source's author id or the
normalized author name. No principle is added, removed or redefined.

Templates: no change needed.
Follow-up TODOs: none.

------------------------------------------------------------------------------------------

Version change: (template) → 1.0.0
Ratification: initial adoption

Principles added:
  I.    Family Data Isolation (NON-NEGOTIABLE)
  II.   Shared Catalog, Personal Records
  III.  Human-Approved AI Content (NON-NEGOTIABLE)
  IV.   Permitted Sources and Original Wording
  V.    Test-First Development (NON-NEGOTIABLE)
  VI.   Integrity Enforced by the Database
  VII.  Typed Contracts at Every Boundary
  VIII. Simplicity and a Single Deployable
  IX.   Privacy and Security by Default

Sections added: Technology Constraints, Development Workflow & Quality Gates, Governance

Templates updated (project overrides in .specify/templates/overrides/, which the Spec Kit
resolver uses ahead of the core templates):
  ✅ plan-template.md  — Constitution Check table, coverage-critical modules, dependency
                         justification, migration notes, single-deployable layout
  ✅ spec-template.md  — numbered acceptance criteria (AC-xx), Data Ownership, AI Involvement,
                         External Sources, Personal Data & Privacy, API Changes
  ✅ tasks-template.md — tests mandatory; test tasks precede implementation; traceability table

Agent guidance:
  ✅ CLAUDE.md created; references this file

Follow-up TODOs:
  - docs/Family Book Tracker – Specification.md still allows SQLite for a home install;
    align it with Technology Constraints.
  - The /speckit-tasks skill text says tests are optional unless requested. The spec
    template and CLAUDE.md state that they are always required; this file takes precedence.

Deferred placeholders: none
-->

# Family Book Tracker Constitution

This constitution governs every specification, plan, task list and line of code in the
Family Book Tracker. Spec Kit commands (`/speckit-specify`, `/speckit-clarify`,
`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`, `/speckit-implement`) MUST treat it
as the highest-priority source of rules. Where a spec, plan or task conflicts with it, the
constitution wins until it is formally amended.

## Core Principles

### I. Family Data Isolation (NON-NEGOTIABLE)

Each family member's reading records belong to that member alone.

- Every reading entry MUST carry an owning `user_id`, set by the server from the
  authenticated session. It MUST NOT be accepted from a request body, query string or path.
- Every query that reads, updates or deletes personal records MUST filter by the
  authenticated user in the data-access layer, not only in route handlers.
- A request for another member's record MUST return `404 Not Found` (not `403`), so that
  the record's existence is not revealed.
- Admin capability covers account management only. It MUST NOT grant read access to
  another member's entries unless a ratified spec explicitly introduces that feature.
- Every endpoint that touches personal records MUST have an automated cross-user test
  proving user A cannot see or change user B's data.

*Rationale:* separation of each person's list is the core promise of the product; one
leak breaks trust in it.

### II. Shared Catalog, Personal Records

The data model separates *what a book is* from *who read it*.

- Books, authors, series and summaries form one shared family catalog. Reading entries
  (status, dates, notes, rating) are personal.
- Features MUST NOT duplicate catalog data into personal records. A new feature that needs
  per-user book data MUST add columns or tables on the personal side.
- Catalog writes MUST deduplicate: type-ahead lookup comes before any create, and
  uniqueness rules (author name, series name, ISBN, series + number) MUST be enforced.
- Removing a book from a personal list MUST NOT delete the catalog book.

*Rationale:* one catalog avoids retyping and repeated AI costs; personal records keep
lists independent.

### III. Human-Approved AI Content (NON-NEGOTIABLE)

AI assists; people decide.

- AI output (summaries, series suggestions, any future enrichment) MUST be presented as a
  draft and MUST NOT be written to the catalog without an explicit user action to accept it.
- Each stored summary MUST record its origin (`ai`, `ai_edited` or `manual`) and a
  timestamp. Summaries with origin `ai` or `ai_edited` MUST also record the model
  identifier and the source URLs used.
- AI failures (timeout, no sources, ambiguous match) MUST degrade gracefully to manual
  entry. No core feature may depend on an AI call succeeding.
- LLM access MUST sit behind an interface (for example `SummaryGenerator`) so that the
  provider can be swapped and a deterministic fake used in tests.
- AI calls MUST have a timeout (default 30 s) and a per-user daily generation limit.
- Source lookups and unaccepted drafts MUST be cached. Lookups and drafts for one book are
  keyed by ISBN or by normalized title + author; lookups for an author are keyed by the
  source's author identifier or the normalized author name. The cache is stored outside the
  catalog tables and is never shown as catalog content; a cached draft still requires
  acceptance. An explicit "regenerate"
  request MUST bypass the cached draft and counts against the daily limit.

*Rationale:* a family catalog is only useful if it is accurate, and AI output can be wrong.

### IV. Permitted Sources and Original Wording

- Book data MUST come only from sources whose terms permit the use: official APIs
  (Google Books, Open Library) or an LLM web-search tool. Scraping sites whose terms
  forbid it (including Amazon and Goodreads) is prohibited.
- The LLM web-search tool MUST be configured to exclude domains whose terms forbid
  automated access (including Amazon and Goodreads), and the URLs it used MUST be recorded.
  A draft that cites an excluded domain MUST be rejected before it is shown.
- New sources MUST be added as adapters behind a common source-adapter interface, with
  their terms of use noted in the spec that introduces them.
- Generated summaries MUST be original, spoiler-free prose (default 100–200 words) and
  MUST NOT reproduce publisher blurbs or reviews verbatim.

*Rationale:* keeps the project legal and durable, and avoids building on access that can be
cut off.

### V. Test-First Development (NON-NEGOTIABLE)

- Tests MUST be written before the implementation they cover and MUST fail for the expected
  reason before that implementation is written. Tasks that change no behaviour
  (documentation, configuration, tooling) are exempt.
- `tasks.md` MUST order test tasks ahead of the implementation tasks they cover.
- Every acceptance criterion in a spec MUST map to at least one automated test tagged with
  its feature-qualified ID: the feature number plus the criterion ID, for example
  `@pytest.mark.ac("001/AC-01")`.
- Test layers:
  - **Unit:** domain rules and validation (Pydantic models, services).
  - **Integration:** repository and database behaviour against a real PostgreSQL instance
    (test container), including constraints.
  - **Contract:** API responses validated against the OpenAPI schema.
  - **External:** source adapters tested with recorded HTTP fixtures; the LLM replaced by
    a fake. CI MUST NOT call live external services.
- Line coverage MUST stay at or above 85% overall and at 100% for authorization and
  ownership-filtering code. The modules that hold that code MUST be named in `plan.md` and
  listed in the coverage configuration so that CI enforces the 100% threshold on them.

*Rationale:* small projects stay maintainable only if behaviour is pinned by tests from the
start.

### VI. Integrity Enforced by the Database

Business rules that can be expressed relationally MUST be enforced by the database, not
only in application code.

- Required fields MUST be `NOT NULL`; relationships MUST use foreign keys.
- Rules from the specification MUST be database constraints, including:
  `series_number` requires `series_id`; `real_name` is allowed only when `is_pen_name` is
  true; unique (`user_id`, `book_id`) on reading entries; one current summary per book.
- Every schema change MUST be an Alembic migration that has been reviewed, is reversible
  (has a working `downgrade`) and is tested in CI with upgrade → downgrade → upgrade.
- Destructive migrations (dropping columns or tables containing data) MUST have a backup
  step documented in the plan.

*Rationale:* the database outlives any version of the code; constraints stop bad data
whatever code path writes it.

### VII. Typed Contracts at Every Boundary

- All request and response bodies of the JSON API (`/api/v1`) MUST be Pydantic v2 models;
  raw dicts MUST NOT cross the API boundary.
- Server-rendered UI endpoints return HTML and are not part of the OpenAPI contract. Their
  form and query input MUST be validated by Pydantic v2 models before it reaches a service,
  and they MUST call the same services as the JSON API.
- The OpenAPI document generated by FastAPI is the API contract. `/speckit-plan` MUST
  produce contract files under `specs/<feature>/contracts/`, and contract tests MUST verify them.
- Domain models, persistence models (SQLAlchemy) and API schemas MUST be kept separate;
  mapping between them is explicit.
- Code MUST pass `mypy --strict`. Each `type: ignore` MUST carry an error code and a
  comment giving the reason.

*Rationale:* explicit contracts make specs verifiable and refactors safe.

### VIII. Simplicity and a Single Deployable

- The application MUST ship as one deployable unit: a FastAPI service serving both the
  JSON API and the server-rendered UI (Jinja2 + HTMX).
- A separate SPA framework, microservices, message brokers or additional datastores MUST NOT
  be introduced without a ratified amendment showing a requirement that the current design
  cannot meet.
- Design targets one family (about 2–10 users, a few thousand books). Plans MUST NOT add
  complexity for scale beyond that.
- Each new dependency MUST be justified in `plan.md` (purpose, alternatives considered,
  license).

*Rationale:* this is a family tool; operational simplicity matters more than theoretical scale.

### IX. Privacy and Security by Default

- The application MUST store only the minimum personal data: display name, login and
  password hash. Children's accounts MUST NOT require an email address.
- Passwords MUST be hashed with Argon2id. Session cookies MUST be Secure, HttpOnly and
  SameSite. State-changing form posts MUST be CSRF-protected.
- Self-registration MUST NOT exist: only Admins create accounts.
- Secrets (LLM keys, Google Books key, database credentials) MUST come from environment or
  a secret store and MUST NOT be committed or sent to the browser.
- Requests to external services (LLM provider, book data APIs) MUST contain book metadata
  only. They MUST NOT contain personal notes, ratings, reading status or anything that
  identifies a family member.
- Logs MUST NOT contain passwords, session tokens or personal notes.
- Traffic MUST be HTTPS only in every non-local environment.

*Rationale:* the app holds data about children and family members; leaks have a real cost.

## Technology Constraints

| Area | Required choice |
|---|---|
| Language | Python 3.12+ |
| Web / API | FastAPI |
| Models & validation | Pydantic v2 |
| UI | Jinja2 templates + HTMX, responsive for phone, tablet and desktop |
| Database | PostgreSQL 16+ (SQLite only for local throwaway development) |
| ORM / migrations | SQLAlchemy 2.0 + Alembic |
| HTTP client | httpx |
| Testing | pytest, pytest-asyncio, testcontainers (PostgreSQL), recorded HTTP fixtures |
| Quality tooling | ruff (lint + format), mypy, pip-audit |
| Packaging | uv with a committed lock file |
| Delivery | Single container image |

Performance budgets: list pages under 1 s at p95 with 5,000 books; AI draft under 30 s or a
clear failure message. Nightly database backups with 30-day retention are a release
requirement, not an optional extra.

## Development Workflow & Quality Gates

### Spec Kit flow

1. `/speckit-specify`: each feature spec MUST state user stories, numbered functional
   requirements (FR-xx), numbered acceptance criteria (AC-xx), a **Data Ownership** note
   (catalog vs personal) and an **AI Involvement** note (none, or what is generated and how
   it is approved).
2. `/speckit-clarify`: open questions MUST be resolved or explicitly deferred before planning.
3. `/speckit-plan`: the plan MUST include the Constitution Check below, with every row
   answered. A "No" on row I, III or V rejects the plan; those principles cannot be waived.
   A "No" on any other row requires an entry in the Complexity Tracking table with
   justification, or the plan is rejected.
4. `/speckit-tasks`: test tasks come before implementation tasks; every FR and AC MUST
   trace to at least one task.
5. `/speckit-analyze`: MUST report no constitution violations and no untraced requirements
   before `/speckit-implement` runs.
6. `/speckit-implement`: work proceeds task by task with tests passing at each commit.

### Constitution Check (copy into every plan.md)

| # | Gate | Yes / No |
|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | |
| II | Catalog vs personal data placement is stated; no duplication | |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | |
| V | Tests are written first; every AC maps to a feature-qualified test | |
| VI | Rules are enforced by DB constraints; migrations are reversible | |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | |
| VIII | No new deployables or datastores; new dependencies are justified | |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | |

### CI gates (all MUST pass before merge)

- `ruff check` and `ruff format --check`
- `mypy --strict`
- `pytest` with the coverage thresholds from Principle V
- Alembic upgrade → downgrade → upgrade against PostgreSQL
- OpenAPI contract check: the generated OpenAPI document is compared with the committed
  contract files; breaking changes require a spec that declares them
- `pip-audit` reporting no known vulnerabilities; each exception MUST be listed in a
  committed ignore list with a reason and a review date
- List-page performance test: p95 under 1 s against a 5,000-book seed dataset
- Spec gate: every PR links a `specs/<feature>/` directory, or is labelled `chore` / `fix`
  with a stated reason

### Release gates

- Nightly backups with 30-day retention are configured for the target environment, and a
  restore from backup has been tested.

### Reviews

- Every change MUST merge through a pull request approved by the project maintainer.
- When the maintainer is also the author, an AI review MUST be run and its findings
  resolved or answered in the pull request before the maintainer approves.
- Reviewers MUST check the Constitution Check table, not only the diff.

## Governance

- This constitution supersedes all other project practices and conventions. Specs, plans
  and tasks that conflict with it are invalid until corrected or until it is amended.
- **Ratification:** the project maintainer is the repository owner. A spec or an amendment
  is *ratified* when its pull request has been approved and merged by the maintainer.
- **Amendments** are proposed in a pull request that changes this file, states the reason,
  updates the Sync Impact Report at the top, and updates any affected
  `.specify/templates/*` files in the same PR.
- **Versioning** follows semantic versioning:
  - MAJOR: a principle is removed or redefined in a way that is not backward compatible
  - MINOR: a principle or section is added or materially expanded
  - PATCH: clarifications, wording and typo fixes
- **Compliance** is checked at `/speckit-plan` (Constitution Check), `/speckit-analyze` and
  pull request review. Non-compliance found after merge is tracked as a defect and fixed
  before new feature work in the same area.
- Principles marked NON-NEGOTIABLE (I, III, V) cannot be waived per feature; they change
  only by MAJOR amendment.
- Runtime guidance for AI coding agents (for example `CLAUDE.md` or
  `.github/copilot-instructions.md`) MUST reference this file and MUST NOT contradict it.

**Version**: 1.0.1 | **Ratified**: 2026-11-18 | **Last Amended**: 2026-11-19
