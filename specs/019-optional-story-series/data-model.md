# Data Model: Stories Without a Series (spec 019)

## Story (catalog) – changed

| Field | Before | After |
|---|---|---|
| `series_id` | required | optional |
| `series_number` | required, 0–999.99 | optional, 0–999.99 when given |

Rules:
- **Both or neither**: a series and a number together, or neither
  (`story_series_both_or_neither`).
- **One story per series and number**, for stories with a series (unchanged unique index;
  stories without a series never clash).
- A story without a series is identified only by its id. Two may share a title.

## Book story (catalog) – changed

| Field | Before | After |
|---|---|---|
| `position` | — | integer, required: the order the story was added to this book |

- New links take the next value of `book_story_position_seq` (research R2). Positions are
  only compared within a book, so a book's values may have gaps (say 4, 17, 230).
- Existing links are numbered per book by series name, then number (today's order).

## Derived

- **A book's story order**: stories with a series by series name, then number; then
  stories without a series by position.

## Migration `0007_optional_story_series`

- **Up**: drop NOT NULL on the two story columns; add the CHECK; add `book_story.position`,
  fill it, then make it NOT NULL.
- **Down**: refused while any story has no series; otherwise the reverse.
