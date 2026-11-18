---
description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: REQUIRED. Constitution Principle V (NON-NEGOTIABLE) makes tests mandatory for every
feature: each acceptance criterion maps to at least one test, and test tasks come before the
implementation tasks they cover.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions
- Test tasks name the acceptance criteria they cover, e.g. `(AC-01, AC-02)`
- Implementation tasks name the functional requirements they deliver, e.g. `(FR-003)`

## Path Conventions

- Single deployable (Constitution Principle VIII): `src/book_tracker/`, `migrations/` and
  `tests/` at repository root, as laid out in plan.md
- Test layers: `tests/unit/`, `tests/integration/` (real PostgreSQL), `tests/contract/`
  (OpenAPI), `tests/external/` (recorded HTTP fixtures, fake LLM)

<!--
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.

  The /speckit-tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Acceptance criteria (AC-xx) and functional requirements (FR-xxx) from spec.md
  - Feature requirements and coverage-critical modules from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/

  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment

  Every AC-xx and FR-xxx in spec.md MUST trace to at least one task.

  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize Python 3.12 project with uv and a committed lock file
- [ ] T003 [P] Configure ruff, mypy --strict and pytest coverage thresholds (85% overall, 100% for coverage-critical modules)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational tasks (adjust based on the plan):

- [ ] T004 Write migration round-trip test (upgrade → downgrade → upgrade) in tests/integration/test_migrations.py
- [ ] T005 Set up Alembic and the initial reversible migration in migrations/
- [ ] T006 [P] Write session and ownership-filter tests, including cross-user cases, in tests/integration/test_ownership.py
- [ ] T007 [P] Implement authentication and the session-user dependency in src/book_tracker/[location]
- [ ] T008 Set up API routing under /api/v1 and the server-rendered UI routes
- [ ] T009 Configure error handling and logging (no passwords, tokens or notes in logs)
- [ ] T010 Configure settings from environment variables (no secrets in the repository)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 ⚠️

> **Write these tests FIRST and confirm they FAIL for the expected reason before implementation.**
> Tag each test with its feature-qualified AC ID, e.g. `@pytest.mark.ac("[###]/AC-01")`.

- [ ] T011 [P] [US1] Contract test for [endpoint] in tests/contract/test_[name].py (AC-01)
- [ ] T012 [P] [US1] Integration test for [user journey] in tests/integration/test_[name].py (AC-01, AC-02)
- [ ] T013 [P] [US1] Cross-user test: another member gets 404 for this user's [record] in tests/integration/test_[name]_isolation.py
- [ ] T014 [P] [US1] Unit test for [domain rule] in tests/unit/test_[name].py (AC-02)

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create [Entity1] model and migration with its constraints (FR-001)
- [ ] T016 [P] [US1] Create [Entity2] Pydantic schemas in src/book_tracker/schemas/[entity2].py (FR-002)
- [ ] T017 [US1] Implement [Service] in src/book_tracker/services/[service].py (depends on T015, T016)
- [ ] T018 [US1] Implement [endpoint] in src/book_tracker/api/[file].py (FR-001)
- [ ] T019 [US1] Implement [page/partial] in src/book_tracker/web/[file].py (FR-002)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 ⚠️

- [ ] T020 [P] [US2] Contract test for [endpoint] in tests/contract/test_[name].py (AC-03)
- [ ] T021 [P] [US2] Integration test for [user journey] in tests/integration/test_[name].py (AC-03)

### Implementation for User Story 2

- [ ] T022 [P] [US2] Create [Entity] model and migration (FR-003)
- [ ] T023 [US2] Implement [Service] in src/book_tracker/services/[service].py
- [ ] T024 [US2] Implement [endpoint/page] (FR-003)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 ⚠️

- [ ] T025 [P] [US3] External test with recorded HTTP fixtures and a fake LLM in tests/external/test_[name].py (AC-04)
- [ ] T026 [P] [US3] Integration test for [user journey] in tests/integration/test_[name].py (AC-04)

### Implementation for User Story 3

- [ ] T027 [P] [US3] Create [adapter] behind the source-adapter interface in src/book_tracker/sources/[name].py (FR-004)
- [ ] T028 [US3] Implement [Service] in src/book_tracker/services/[service].py
- [ ] T029 [US3] Implement [endpoint/page] (FR-005)

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX List-page performance test: p95 under 1 s against a 5,000-book seed dataset
- [ ] TXXX Verify coverage thresholds (85% overall, 100% for coverage-critical modules)
- [ ] TXXX Update committed OpenAPI contract files and confirm the contract check passes
- [ ] TXXX Security hardening (CSRF, cookie flags, logging review)
- [ ] TXXX Run quickstart.md validation

---

## Traceability

<!--
  /speckit-tasks MUST fill this table. Every AC and FR in spec.md needs at least one task.
  /speckit-analyze reports any row with an empty Tasks column.
-->

| Requirement | Tasks |
|---|---|
| AC-01 | [e.g., T011, T012] |
| FR-001 | [e.g., T015, T018] |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Migrations and models before services
- Services before endpoints and pages
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for [endpoint] in tests/contract/test_[name].py"
Task: "Integration test for [user journey] in tests/integration/test_[name].py"
Task: "Cross-user test in tests/integration/test_[name]_isolation.py"

# Then launch the models for User Story 1 together:
Task: "Create [Entity1] model and migration"
Task: "Create [Entity2] Pydantic schemas"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail for the expected reason before implementing
- Every commit leaves the test suite passing
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
