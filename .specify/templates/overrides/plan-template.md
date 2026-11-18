# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

<!--
  This template is a project override of the Spec Kit core template. It implements the
  plan requirements of .specify/memory/constitution.md. A plan that leaves a Constitution
  Check row unanswered, or answers "No" on row I, III or V, is rejected.
-->

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  Defaults below come from the constitution's Technology Constraints. Change a value only
  through a constitution amendment; add feature-specific detail where marked.
-->

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX, httpx

**Storage**: PostgreSQL 16+

**Testing**: pytest, pytest-asyncio, testcontainers (PostgreSQL), recorded HTTP fixtures, fake LLM

**Target Platform**: Single container image (Linux)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**: List pages under 1 s at p95 with 5,000 books; AI draft under 30 s [add feature-specific goals]

**Constraints**: [Feature-specific constraints or N/A]

**Scale/Scope**: One family: about 2–10 users and a few thousand books

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

<!--
  Answer every row Yes or No, with a one-line note on how the design meets the gate.
  Rows I, III and V are NON-NEGOTIABLE: "No" rejects the plan.
  A "No" on any other row requires an entry in Complexity Tracking below.
-->

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | | |
| II | Catalog vs personal data placement is stated; no duplication | | |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | | |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | | |
| V | Tests are written first; every AC maps to a feature-qualified test | | |
| VI | Rules are enforced by DB constraints; migrations are reversible | | |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | | |
| VIII | No new deployables or datastores; new dependencies are justified | | |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | | |

### Coverage-critical modules (Principle V)

<!--
  Name the modules holding authorization and ownership-filtering code touched by this
  feature. They MUST be listed in the coverage configuration at 100% line coverage.
-->

- [e.g., `src/book_tracker/persistence/readings.py`, or "None touched"]

### New dependencies (Principle VIII)

| Package | Purpose | Alternatives considered | License |
|---|---|---|---|
| [None, or package name] | | | |

### Migrations (Principle VI)

- **Schema changes**: [None | migrations to add, with the constraints they create]
- **Destructive changes**: [None | columns or tables dropped, and the backup step taken first]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command): OpenAPI for JSON API endpoints
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

<!--
  The application is a single deployable (Principle VIII). Use this layout, adjusted to the
  directories that already exist, and list only the paths this feature touches. A separate
  frontend, extra services or extra datastores need a ratified constitution amendment.
-->

```text
src/book_tracker/
├── api/            # JSON API routers under /api/v1 (Pydantic v2 request/response models)
├── web/            # Server-rendered routes, Jinja2 templates and HTMX partials
├── schemas/        # Pydantic v2 API and form schemas
├── domain/         # Domain models and business rules
├── services/       # Use cases shared by api/ and web/
├── persistence/    # SQLAlchemy models and repositories (ownership filtering lives here)
└── sources/        # Source adapters and the SummaryGenerator interface

migrations/         # Alembic migrations (reversible)

tests/
├── unit/
├── integration/    # Real PostgreSQL via testcontainers
├── contract/       # Responses validated against OpenAPI
└── external/       # Recorded HTTP fixtures; fake LLM
```

**Structure Decision**: [Document the paths this feature adds or changes]

## Complexity Tracking

> **Fill ONLY for a "No" on Constitution Check rows II, IV, VI, VII, VIII or IX.**
> Rows I, III and V cannot be justified here.

| Gate | Violation | Why Needed | Simpler Alternative Rejected Because |
|------|-----------|------------|-------------------------------------|
| [e.g., VIII] | [e.g., add a background worker] | [current need] | [why the single deployable cannot meet it] |
