# Data Model: Upcoming Books (spec 007)

## Schema changes (migration `0003_upcoming_books`)

| Table | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| `book` (catalog) | `release_date` | `DATE` | yes | – | expected or actual release date |
| `reading_entry` (personal) | `pre_ordered` | `BOOLEAN` | no | `false` | the owner's own flag |

- **Index:** `book_release_date_idx ON book (release_date) WHERE release_date IS NOT NULL`.
- **Upgrade:** adds the two columns and the index. Existing rows get `NULL` / `false`.
- **Downgrade:** drops the index and both columns. This is destructive, so the deploy's
  existing backup step runs first (plan, Migrations).

## Domain

- `Book.release_date: date | None`
- `ReadingEntry.pre_ordered: bool`
- `domain/values.py`:
  - `NOW_OUT_DAYS = 30`;
  - `is_upcoming(d, today)`: `d is not None and d > today`;
  - `is_now_out(d, today)`: `d is not None and today - 29 days <= d <= today`.

## Service views (not stored)

- **`UpcomingView`:**
  - `mine: tuple[ReadingEntry, ...]`: my entries whose book is upcoming, soonest first;
  - `others: tuple[Book, ...]`: upcoming catalog books not on my list, soonest first.
- **`now_out(db, user_id, today) -> tuple[ReadingEntry, ...]`:** my Want to read entries
  released in the last 30 days, most recent first.

## Forms

- `AddBookForm.release_date: date | None` (raw `release_date`).
- `AddBookForm.pre_ordered: bool` (raw `pre_ordered`, `"yes"` when ticked).
- **`parse_entry_update`:** `pre_ordered` is added when the field is in the form.
- **`book_form(book)`, `book_start_form(book)`:** include `release_date`.
- **`carry_over_form`:** clears it (R7).
