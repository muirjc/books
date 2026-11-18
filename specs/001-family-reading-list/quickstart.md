# Quickstart: Family Reading List

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This guide is for running and checking the feature end to end. Schemas are in
[data-model.md](data-model.md) and [contracts/openapi.yaml](contracts/openapi.yaml); this
guide doesn't repeat them.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Docker or Podman (PostgreSQL 16 for development, and testcontainers in tests)
- For accessibility tests: `uv run playwright install chromium`

## Setup

```bash
uv sync                                     # install from the committed lock file
docker run -d --name books-db -p 5432:5432 \
  -e POSTGRES_USER=books -e POSTGRES_PASSWORD=books -e POSTGRES_DB=books postgres:16

export BOOK_TRACKER_DATABASE_URL=postgresql+psycopg://books:books@localhost:5432/books
export BOOK_TRACKER_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
export BOOK_TRACKER_ENVIRONMENT=local       # allows HTTP on localhost only

uv run alembic upgrade head
uv run book-tracker create-admin --login parent --display-name "Parent"   # prompts for password
uv run uvicorn book_tracker.main:app --reload
```

Open <http://localhost:8000/sign-in>.

## Quality gates (same as CI)

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src
uv run pytest -m "not perf and not a11y" --cov   # 85% overall; 100% on coverage-critical modules
uv run pytest -m a11y                           # WCAG 2.2 AA + keyboard journeys (SC-007)
uv run pytest -m perf                           # p95 < 1 s with 5,000 books (SC-002)
uv run pytest tests/integration/test_migrations.py   # upgrade → downgrade → upgrade
uv run pip-audit
```

Contract check: the generated OpenAPI document is committed as a baseline; regenerate it
whenever the API changes (a test fails if it's stale), and compare against the previous
baseline for breaking changes:

```bash
uv run python -m book_tracker.export_openapi > specs/001-family-reading-list/contracts/openapi.generated.json
git show HEAD:specs/001-family-reading-list/contracts/openapi.generated.json > /tmp/base.json
docker run --rm -v "$PWD":/w -v /tmp:/t -w /w tufin/oasdiff:v1.38.0 breaking \
  /t/base.json specs/001-family-reading-list/contracts/openapi.generated.json --fail-on ERR
```

## Manual validation scenarios

Each scenario corresponds to the spec's acceptance criteria. The automated tests that
carry the same `001/AC-xx` tags are the source of truth; this list is for a quick
hands-on check.

1. **Accounts (AC-09, AC-11, AC-29, AC-34)**: as `parent`, create the accounts
   `alice` (Member, password `correct horse`) and `ben` (Member). Then try to create `Ben`:
   it's rejected. Sign in as `alice`: you're sent to change the password first.
2. **Private lists (AC-03, AC-04, AC-14)**: Alice adds *The Hobbit* by J.R.R. Tolkien
   (title and author only). Ben signs in and sees an empty list. Copy the URL of Alice's
   entry (`/entries/<id>`) and open it as Ben: you get "not found". As `parent`, the admin
   pages show no reading entries.
3. **Shared catalog (AC-15, AC-16, AC-32)**: Ben types "Hob" in the add form; *The Hobbit*
   is suggested. Choose it; there's still one catalog book. Ben corrects a typo in the
   title; Alice's list shows the new title, last edited by Ben.
4. **Series rules (AC-06, AC-19, AC-20, AC-22)**: add number 2 with no series: validation
   error. Add *Harry Potter* books 1, 3 and a novella at 2.5, plus one book in that series
   with no number. The series view lists 1, 2.5, 3, then the unnumbered one. Giving another
   book number 3: rejected, naming the existing book.
5. **Pen names (AC-17, AC-18)**: create "Robert Galbraith", a pen name with no real name.
   Later add the real name "J.K. Rowling". A search for "Rowling" finds Galbraith's books.
   Entering a real name on an author who isn't a pen name: rejected.
6. **Duplicates and re-reads (AC-05, AC-35)**: add *The Hobbit* again as Alice: "Already on
   your list", with a re-read offer. Choose "Read again", then mark it Finished: times read
   is 2, still one entry.
7. **Sign-in limit (AC-33)**: enter 5 wrong passwords for `ben`. The correct password is
   then refused with "try again later" for 15 minutes. A made-up login behaves the same way.
8. **Deactivation (AC-10, AC-26)**: `parent` deactivates `ben`. Ben's open session ends,
   and sign-in is refused. Reactivating him brings his list back. `parent` can't deactivate
   themselves while they're the only active Admin.
9. **Switch user (AC-28)**: on one browser, sign in as Alice, choose "Switch user", and pick
   Alice from the recent profiles: the login is filled in and the password is asked for.
10. **Summaries (AC-24, AC-25)**: Alice writes a summary for *The Hobbit*; Ben sees it,
    marked as hand-written by Alice. Ben writes a new one; it becomes current, and Alice's
    stays in the history.
11. **Accessibility (SC-007)**: complete scenarios 2, 3 and 9 with the keyboard only
    (Tab, Shift+Tab, Enter, arrow keys in the suggestion lists).

## Backups (release gate, research R20)

Before the first release, on the Raspberry Pi (source document section 10.6). The dump runs
inside the Compose `db` container and writes to the NAS mount. Run it nightly from a systemd
timer:

```bash
# nightly (systemd timer); /mnt/nas/books-backups is the NAS mount on the Pi
docker compose exec -T db pg_dump -U books -Fc books > /mnt/nas/books-backups/books-$(date +%F).dump
find /mnt/nas/books-backups -name 'books-*.dump' -mtime +30 -delete
# restore test (into a scratch database), at least once before go-live
docker compose exec -T db createdb -U books books_restore_test
docker compose exec -T db pg_restore -U books -d books_restore_test < /mnt/nas/books-backups/books-YYYY-MM-DD.dump
```

The encrypted off-site copy (restic) is still to be set up: its destination isn't chosen yet.
Record the restore test date in the release notes.
