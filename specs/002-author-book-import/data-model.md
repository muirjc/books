# Data Model: Import an Author's Books

Adds two tables to the spec 001 schema ([001 data-model](../001-family-reading-list/data-model.md))
in one reversible migration, `0002_author_import`. No existing table or column changes.

## New tables

### `book_source_ref` (catalog)

Links a catalog book to the source record it was imported from (FR-009, research R13).

| Column | Type | Rules |
|---|---|---|
| `id` | uuid | PK |
| `book_id` | uuid | NOT NULL, FK `book.id` ON DELETE CASCADE |
| `source` | varchar(20) | NOT NULL, `CHECK (source IN ('open_library'))` |
| `source_work_id` | varchar(40) | NOT NULL |
| `imported_by` | uuid | NOT NULL, FK `app_user.id` ON DELETE RESTRICT |
| `imported_at` | timestamptz | NOT NULL, default `now()` |

Constraints (named, so services can map violations):

- `book_source_ref_source_work_key`: UNIQUE (`source`, `source_work_id`). One catalog book per
  source record; this is what makes concurrent imports safe (AC-16, research R7).
- `book_source_ref_book_source_key`: UNIQUE (`book_id`, `source`). A book links to at most one
  record per source.
- `book_source_ref_open_library_id_format`:
  `CHECK (source <> 'open_library' OR source_work_id ~ '^OL[0-9]+W$')`.
- Index `book_source_ref_book_id_idx` on `book_id`.

### `source_lookup_cache` (neither catalog nor personal)

Open Library answers reused for 24 hours (FR-017, research R5), and the draft list between
showing and confirming (research R8). Never read as catalog content. It holds no user ids.

| Column | Type | Rules |
|---|---|---|
| `source` | varchar(20) | NOT NULL, `CHECK (source IN ('open_library'))` |
| `kind` | varchar(20) | NOT NULL, `CHECK (kind IN ('author_search', 'author_works'))` |
| `lookup_key` | varchar(300) | NOT NULL; normalized name, or the Open Library author key |
| `payload` | jsonb | NOT NULL; the parsed result (below) |
| `fetched_at` | timestamptz | NOT NULL |
| `expires_at` | timestamptz | NOT NULL, `CHECK (expires_at > fetched_at)` |

- PK `source_lookup_cache_pkey` (`source`, `kind`, `lookup_key`); a refresh is an upsert.
- Index `source_lookup_cache_expires_at_idx` on `expires_at`, for deleting expired rows when a
  row is written.
- Payload for `author_search`: a list of author candidates. For `author_works`: the author
  candidate, `total` (Open Library's `numFound`) and the de-duplicated works, each with id,
  alias ids, title, first published year, author names in order, and ISBN-13s for matching.
  A row with less than 1 hour left is refreshed when the list is shown (research R8).

## Domain objects (not stored)

Frozen dataclasses in `src/book_tracker/domain/imports.py`:

| Object | Fields | Notes |
|---|---|---|
| `AuthorCandidate` | `source_id`, `name`, `birth_date`, `death_date`, `top_work`, `work_count` | Dates are Open Library's free text, shown as given |
| `WorkCandidate` | `source_id`, `alias_ids` (other merged work ids), `title`, `first_publish_year`, `author_names` (ordered, no repeats), `isbn13s` (set), `edition_count` | Title and names NFKC-normalized and cut to 300/200 characters (FR-022); `isbn13s` used only for matching (FR-011) |
| `WorkList` | `author`, `works`, `total`, `truncated` | `truncated` when `total` > 2,000 (FR-020) |
| `WorkState` | `NEW`, `IN_CATALOG`, `ON_MY_LIST` | Computed per member at display time (FR-005) |
| `ImportedBook` | `book_id`, `title`, `entry_id`, `new_to_catalog` | One added book |
| `SkippedBook` | `book_id`, `title`, `reason` (`on_list` or `duplicate`) | One skipped work (FR-012, FR-021) |
| `ImportResult` | `added` (list of `ImportedBook`), `skipped` (list of `SkippedBook`) | The summary (FR-012) |

Value rules in `domain/matching.py`: `normalize_title`, `normalize_person_name`,
`isbn10_to_13` (returns `None` for an invalid check digit), and `merge_duplicate_works`
(research R6).

## Writes on confirm

| Step | Table | Rule |
|---|---|---|
| Author | `author` (existing) | Reuse by case-insensitive name; create otherwise with `created_by` = importer (AC-05, AC-06) |
| Book | `book` (existing) | Only when not already in the catalog (FR-005); `title` only: no series, number or ISBN (FR-010, FR-011); `created_by` = importer |
| Book authors | `book_author` (existing) | Open Library order, positions 1..n |
| Source link | `book_source_ref` (new) | One row per newly created book; a unique violation means "another member just imported it" → reuse that book (AC-16) |
| List entry | `reading_entry` (existing, personal) | Through `ReadingEntryRepository(db, session_user)`; chosen status; skipped if already on the list (AC-17, FR-013) |

All steps for one confirm run in one transaction that first takes the advisory lock
`pg_advisory_xact_lock(hashtext('book_tracker.import'))`, so confirms run one at a time
(research R7). Book inserts and each reading-entry insert have their own savepoint. Id and
ISBN lookups pass one array parameter (`= ANY(:ids)`). A confirm holds at most 500 works
(FR-014).

## Ownership and access summary

| Data | Placement | Read | Write |
|---|---|---|---|
| `book_source_ref` | Catalog | All members (book page) | Importing member, on confirm |
| `source_lookup_cache` | Cache, no user ids | Import services only | Import services only |
| `reading_entry` rows from an import | Personal | Owner only | Owner only; owner from session |

- No catalog data is copied into `reading_entry` (Principle II).
- `ReadingEntryRepository.book_ids_on_list(book_ids)` returns the subset of the given books on
  the bound user's list. Like every method on that repository, it never accepts a user id.

## Migration `0002_author_import`

- **Upgrade**: create `book_source_ref` and `source_lookup_cache` with the constraints and
  indexes above.
- **Downgrade**: drop `source_lookup_cache`, then `book_source_ref`. Imported books stay in the
  catalog as ordinary books; only their source links are lost. Because it drops a table that
  holds data, a downgrade in production MUST be preceded by a backup: run
  `books-backup.sh` (deploy/pi/README.md section 10) and confirm it succeeded (Principle VI).
- Tested in CI with upgrade → downgrade → upgrade, as for 0001.
