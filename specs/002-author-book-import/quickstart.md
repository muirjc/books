# Quickstart: Import an Author's Books

How to check spec 002 end to end. Setup and running the app are as in
[001 quickstart](../001-family-reading-list/quickstart.md); this page lists only what's new.

## Prerequisites

- The app running locally (001 quickstart) with migrations at head, so
  `0002_author_import` is applied: `uv run alembic upgrade head`.
- Two member accounts, for example `alice` and `ben`.
- For manual checks against the real site: outbound HTTPS to `openlibrary.org`. No setting is
  needed; requests identify only the app (research R2).
- Automated tests never contact Open Library; they replay the recorded fixtures in
  `tests/external/fixtures/open_library/` (research R14).

## Automated checks

```bash
uv run pytest -m ac                           # every acceptance test (001/AC-xx and 002/AC-xx)
uv run pytest tests/external                  # Open Library adapter against recorded fixtures
uv run pytest tests/integration -k import     # import service, constraints, concurrency, cross-user
uv run pytest tests/contract -k import        # responses against contracts/openapi.yaml
uv run pytest -m a11y -k import               # WCAG 2.2 AA and keyboard journey for the import pages
uv run pytest -m perf -k import               # 300-work list under 1 s p95, cache warm (SC-002)
uv run pytest tests/integration/test_migrations.py   # upgrade → downgrade → upgrade includes 0002
uv run python scripts/check_coverage.py       # 100% on coverage-critical modules, incl. services/imports.py
```

## Manual walk-through (real Open Library)

| Step | Do | Expect | Spec |
|---|---|---|---|
| 1 | Sign in as `alice`, open **Import from Open Library** (`/import`), search "Brandon Sanderson" | Two authors listed with birth year, best-known title and number of works | AC-08 |
| 2 | Choose the one with about 238 works | The works list loads in a few seconds: titles, years, co-authors; each work once | AC-01, AC-12 |
| 3 | Sort by year, then filter by "mist" | The list re-sorts and narrows; ticked boxes stay ticked | AC-10 |
| 4 | Choose **Select all shown** | Every shown work not already on your list is ticked; hidden works are not | AC-11 |
| 5 | Leave status as Finished and confirm | Summary: "Added N books to your list (N new to the family catalog)". The books are on your list as Finished, with no series and no ISBN | AC-02, AC-14, AC-19 |
| 6 | Open one imported book | "Imported from Open Library" with a link to the work; created by alice | AC-07 |
| 7 | Search the same author again | The list appears almost at once (reused results), with your books marked "Already on your list" and unselectable | AC-17, FR-017 |
| 8 | Sign in as `ben`, open your list | None of alice's imports are on it | AC-18 |
| 9 | As `ben`, import the same author and tick one of alice's books | It is marked "In the family catalog"; confirming adds it to ben's list without a second catalog copy | AC-04, SC-003 |
| 10 | Search a nonsense name, for example "zzqx qqzz" | "No author found" with a link to add a book by hand | AC-09 |
| 11 | Disconnect the network (or point `BOOK_TRACKER_OPENLIBRARY_BASE_URL` at an unused port) and search | "The book site couldn't be reached..." within 10 s; the rest of the app still works | AC-13, SC-004 |

## Database checks

```sql
-- One source link per imported book; no duplicate Open Library works (AC-07, AC-16)
SELECT source, source_work_id, count(*) FROM book_source_ref GROUP BY 1, 2 HAVING count(*) > 1;  -- no rows
-- No duplicate authors by name (AC-05)
SELECT lower(name), count(*) FROM author GROUP BY 1 HAVING count(*) > 1;                          -- no rows
-- The cache holds no user ids and expires after a day (FR-017)
SELECT kind, lookup_key, expires_at - fetched_at AS ttl FROM source_lookup_cache;                 -- ttl = 1 day
```
