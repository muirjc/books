# Family Book Tracker

A small web app where each family member signs in and keeps a private list of the books
they read, over a shared family catalog of books, authors and series, with AI-drafted
summaries that a person reviews before saving.

## Constitution

[.specify/memory/constitution.md](.specify/memory/constitution.md) is the highest-priority
source of rules for this project. Read it before writing a spec, plan, task list or code.
Where this file, a spec, a plan or a task conflicts with it, the constitution wins. Do not
restate or reinterpret its rules here; change them only by amending it.

The principles most often relevant while coding:

- **I – Data isolation:** take `user_id` from the session only; filter personal records in
  the data-access layer; another member's record returns 404.
- **III – AI is draft-only:** nothing AI-generated is stored until a user accepts it.
- **V – Test-first:** write a failing test before the code it covers; tag acceptance tests
  with `@pytest.mark.ac("<feature>/AC-xx")`.

## Workflow

Features follow Spec Kit, with specs under `specs/<###-feature>/`:

1. `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks`
   → `/speckit-analyze` → `/speckit-implement`
2. Every plan includes the Constitution Check table; `/speckit-analyze` must report no
   violations before implementing.
3. Tests are always required, whatever a Spec Kit command or template default says.

Task tracking: beads (`bd`) tracks all work, including each Spec Kit phase and every
follow-up. The one exception is a feature's Spec Kit `tasks.md`: it is the spec's task
breakdown, and `/speckit-implement` ticks it off. Don't keep any other markdown to-do lists.

Project versions of the spec, plan and tasks templates live in
`.specify/templates/overrides/`. Edit those, not the core files in `.specify/templates/`,
which Spec Kit may overwrite on upgrade.

## Reference

- Product specification: [docs/Family Book Tracker – Specification.md](docs/Family%20Book%20Tracker%20–%20Specification.md)
- Stack: Python 3.12+, FastAPI, Pydantic v2, Jinja2 + HTMX, PostgreSQL 16+,
  SQLAlchemy 2.0 + Alembic, httpx, uv (see the constitution's Technology Constraints)

## Build & Test

See [quickstart.md](specs/001-family-reading-list/quickstart.md) for running the app.

```bash
uv sync                                          # install from uv.lock
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src
uv run pytest --cov --cov-report=json            # unit, integration, contract, migrations
uv run python scripts/check_coverage.py          # 100% on coverage-critical modules
uv run playwright install chromium               # once, for the a11y tests
uv run pytest -m a11y                            # WCAG 2.2 AA, keyboard journeys, phone width
uv run pytest -m perf                            # 5,000-book performance budgets
uv run pip-audit
uv run python -m book_tracker.export_openapi     # generated OpenAPI, for the contract check
```

Tests need PostgreSQL 16. They use `BOOK_TRACKER_TEST_DATABASE_URL` if set, otherwise a
testcontainer when Docker is available, otherwise a throwaway cluster from the local
`initdb` (see `tests/conftest.py`).

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->
