# Research: Personal Rating (spec 020)

## R1 – Storage

- **Decision**: migration `0008_personal_rating` adds `reading_entry.rating smallint NULL`
  with CHECK `reading_entry_rating_check` (`rating BETWEEN 1 AND 5`). Existing rows get
  NULL. The downgrade drops the column (spec Clarifications: undo removes ratings; the
  pre-deploy backup keeps them).
- **Rationale**: the product spec's data model already names this column. A CHECK keeps a
  bad value out whatever the entry point (Principle VI).
- **No index**: My books always filters by `user_id` first (existing index), so sorting or
  filtering by rating works on one member's rows, at most about 5,000. The perf test
  (AC-15) confirms this. An index on `(user_id, rating)` can be added later if it doesn't.
- **Alternatives**: a separate `rating` table (rejected: one value per entry, no history);
  a downgrade refused while ratings exist (rejected in Clarifications).

## R2 – Sort

- **Decision**: new sort keys `-rating` ("Highest rated") and `rating` ("Lowest rated") in
  `persistence/readings.py` `SORTS` and `_order`. `_order` already puts NULLs last in both
  directions and breaks ties by title, then id, which is exactly AC-08.
- The web `SORT_OPTIONS` and the API's `Sort` literal gain the two keys.

## R3 – Filter

- **Decision**: the repository's `list()` gains `min_rating: int | None` (rating ≥ n) and
  `rated: bool | None` (True: has a rating; False: has none).
- **Web**: one select `rating` on My books with values `""` (Any rating), `5`, `4`, `3`,
  `2` ("5", "4 and up", "3 and up", "2 and up"), `rated` and `unrated`. The route maps a
  number to `min_rating` and the words to `rated`; any other value is ignored, like an
  unknown status today. It's kept in `filters`, so the address, paging and Clear (spec 018)
  carry it.
- **API**: `GET /me/readings` gains `min_rating` (integer 1–5) and `rated` (boolean), both
  optional. Both together are allowed (`rated=false` with `min_rating` matches nothing).
- **Alternatives**: one `rating` string parameter in the API too (rejected: two typed
  parameters validate themselves and read clearly in OpenAPI).

## R4 – Forms

- **Decision**: `partials/entry_fields.html` (used by the entry page and Add a book) gains
  a `Rating (optional)` select: "No rating" (`""`) and 1–5 with the AC-01 words. A select
  is a native, keyboard- and screen-reader-friendly control that needs no JavaScript, and
  its 44 px height matches the Status select.
- `parse_entry_update`: `rating` in the form → `data["rating"] = value or None`.
  `parse_add_book`: the same into the create payload. A value outside `""`/1–5 gives the
  field message "Choose a rating from 1 to 5, or No rating" (AC-04).
- The entry route's `ENTRY_FIELDS` gains `rating`; unchanged values are dropped as today.

## R5 – Schemas and service

- `ReadingEntryCreate.rating: int | None = Field(None, ge=1, le=5)`.
- `ReadingEntryUpdate.rating`: same type; changed only when given, so a field left out
  keeps the rating and null clears it (AC-11). The API and web routes already pass only the
  fields set (`model_fields_set`); `update_entry` adds `rating` to the set of fields it
  copies (`finished_on`, `notes`, `pre_ordered`).
- `ReadingEntry` (output) gains `rating: int | None`.
- `domain.ReadingEntry` gains `rating`; `to_reading_entry` maps it.
- A status change doesn't touch the rating (AC-05): `apply_status_change` only changes
  `times_read` and dates.

## R6 – Display

- A macro `rating_text(entry)` in `macros.html` gives "Rated N out of 5", or nothing.
- Used in `partials/reading_list.html` (a `book-rating` line on My books rows) and the book
  page's `row-status` line (" · Rated 4 out of 5"). The entry page needs no extra line: its
  Rating field shows the saved rating (AC-01, AC-07).
  Text only, no star glyphs (AC-06).

## R7 – Privacy

- The rating lives only on `reading_entry`, which every read already filters by the session
  user in `persistence/readings.py` (coverage-critical). Catalog schemas (`Book`, series
  and author views) never include it.
- Cross-user tests: Ben's rated entry is 404 for Alice by page and API; the book page,
  series page, author page, catalog, Upcoming and the API catalog endpoints, viewed by
  Alice, never contain Ben's rating (AC-12).

## R8 – Unchanged paths

- Import (spec 002) and the quick-add rows (spec 015) create entries through the same
  service with no rating, so they get NULL.
