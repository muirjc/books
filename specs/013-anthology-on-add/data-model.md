# Data Model: Anthology Stories on Add a Book (spec 013)

**No schema changes and no migration.** Stories are stored exactly as in spec 009:
- `story`, unique on `(series_id, series_number)`;
- `story_author`;
- `book_story`.

## Form-only values (never stored)

### StoryRow (`web/forms.py`)

| Field | Type | Notes |
|---|---|---|
| index | int | 0-based position after renumbering |
| title | str | normalized; required when the row has text |
| number | Decimal \| None | 0–999.99, required when the row has text |
| series_name / series_id | str / UUID \| None | blank name = the book's series |
| author_name / author_id | str / UUID \| None | blank name = all the book's authors |
| story_id | UUID \| None | a chosen existing story (AC-13); other fields read-only |
| confirmed_* / use_* | str / UUID \| None | spec 005 answers for this row's names |

`is_blank`: every text field is empty and there is no `story_id`. Blank rows are ignored on
save (AC-07).

### AddBookForm additions

- `anthology: bool`: the checkbox.
- `stories: list[StoryRow]`: at least one row while the box is shown; at most 50.

## Service values (`services/catalog.py`)

### BookStory

Either:
- **New**: `title`, `series_number`, `author_ids: list[UUID] | None`, `series_id: UUID | None`
  (None means the book's), or
- **Existing**: `story_id`.

### StoryNumberTaken (`services/errors.py`)

A `ConflictError` with `code = "story_number_taken"`, `existing_id` = story id, plus
`index` (which item) and `story` (for the AC-13 row message).

## Rules (all from spec 009, enforced as today)

| Rule | Where |
|---|---|
| Story has title, ≥1 author, series, number 0–999.99 | form/schema validation; NOT NULL columns |
| One story per (series, number) | `story_series_number_uq` (DB) + pre-check + `StoryNumberTaken` |
| Story is in ≥1 book | created and linked in one savepoint (`add_new_story`) |
| No two items in one save share (series, number) | form parser / `ReadingEntryCreate` validator |
| Book + entry + stories saved together | one request transaction; rollback on any refusal |
