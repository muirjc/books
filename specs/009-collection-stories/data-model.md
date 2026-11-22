# Data Model: Stories in Collections

Migration `0004_collection_stories` adds three catalog tables. Nothing existing changes.

## story

| Column | Type | Rules |
|---|---|---|
| id | uuid PK | |
| title | varchar(300) NOT NULL | normalised like book titles |
| series_id | uuid NOT NULL | FK series.id ON DELETE RESTRICT (`story_series_id_fkey`) |
| series_number | numeric(5,2) NOT NULL | CHECK 0 ≤ n ≤ 999.99 (`story_series_number_range`) |
| created_by, updated_by | uuid NOT NULL | FK app_user.id RESTRICT |
| created_at, updated_at | timestamptz NOT NULL | default now() |

Index: `story_series_number_uq` UNIQUE (series_id, series_number). It serves both
uniqueness (FR-003) and the series page (by series, ordered by number).

## story_author

| Column | Type | Rules |
|---|---|---|
| story_id | uuid | PK part; FK story.id ON DELETE CASCADE |
| author_id | uuid | PK part; FK author.id ON DELETE RESTRICT (`story_author_author_id_fkey`) |
| position | smallint NOT NULL | CHECK ≥ 1; UNIQUE (story_id, position) |

Index: `story_author_author_id_idx` (author_id), for spec 008's "has works" check.

## book_story

| Column | Type | Rules |
|---|---|---|
| book_id | uuid | PK part; FK book.id ON DELETE CASCADE |
| story_id | uuid | PK part; FK story.id ON DELETE CASCADE (`book_story_story_id_fkey`) |

Index: `book_story_story_id_idx` (story_id).

## Rules not expressible as constraints

- **A story is in at least one book:** see research R2 (conditional delete in the remove
  path).

## Domain

- `BookRef(id, title)`
- `Story(id, title, authors: tuple[BookAuthor], series: SeriesRef, series_number: Decimal,
  books: tuple[BookRef], created_by, created_at, updated_by, updated_at)`, with books by
  title.
- `SeriesRow` gains:
  - `story: Story | None`;
  - `story_entries: tuple[ReadingEntry, ...]`, the viewer's entries for the containing
    books;
  - `story_status`;
  - `contains: tuple[Decimal, ...]` on book rows (AC-14).
- `SeriesView` gains `stories_finished` and `stories_total`.

## Downgrade

`downgrade()` drops the three tables, which loses story data. In production, take and check
a backup with books-backup.sh first, as for 0003.
