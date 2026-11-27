# Data Model: Personal Rating (spec 020)

## reading_entry (personal) – changed

| Column | Type | Rules |
|---|---|---|
| rating | smallint | nullable; CHECK `reading_entry_rating_check`: `rating BETWEEN 1 AND 5` |

- NULL means "no rating". Every existing row starts NULL (AC-13).
- Owned like the rest of the entry: read and written only through the session user's
  `ReadingEntryRepository` (Principle I).
- A status change never changes it (AC-05).

## Migration `0008_personal_rating`

- **Upgrade**: add the column and the CHECK.
- **Downgrade**: drop the CHECK and the column. Ratings are lost; the backup taken before
  every deploy keeps them (spec Clarifications).

## Domain and schemas

- `domain.ReadingEntry.rating: int | None`.
- `ReadingEntryCreate.rating`, `ReadingEntryUpdate.rating`: `int | None`, 1–5.
- `ReadingEntry` (response) `.rating: int | None`.
