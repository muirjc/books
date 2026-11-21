# Research: Upcoming Books (spec 007)

All decisions below; no open questions remain.

## R1 – Where the release date lives

- **Decision:** a nullable `book.release_date DATE` column on the catalog book, with a
  partial index `book_release_date_idx ON book (release_date) WHERE release_date IS NOT
  NULL`.
- **Rationale:** a release date is a fact about the book, the same for every member
  (Principle II). The partial index serves the "after today" and "last 30 days" range
  queries and stays tiny, because few books have a date.
- **Alternatives:** a per-entry date was rejected, because it would copy catalog data into
  personal records. A separate "announcement" table was rejected as needless.

## R2 – Pre-ordered

- **Decision:** `reading_entry.pre_ordered BOOLEAN NOT NULL DEFAULT false`.
- **Rationale:** it is personal (Principle I/II), and one flag is the minimum (Principle
  IX). It is kept after the release, and only its display is limited (spec AC-08).

## R3 – "Today"

- **Decision:** use the existing `today(request)` (the app clock, in the server's time
  zone), which is already used for the finished-date check. Services take `today: date` as
  an argument, so tests pin it. `render()` adds `today` to every template context.
- **Domain helpers** (`domain/values.py`):
  - `NOW_OUT_DAYS = 30`;
  - `is_upcoming(release_date, today)` is `release_date > today`;
  - `is_now_out(release_date, today)` is `today - 29 days <= release_date <= today`.
  The release day is day 1 and day 30 is the last day.

## R4 – The Upcoming only filter on My books

- **Decision:** a checkbox `upcoming=1` in the filter form. The repository's `list()`
  gains `upcoming_after: date | None`. When it is set, the query adds
  `release_date > :today` and orders by `release_date ASC, lower(title), id`, ignoring
  `sort` (spec assumption). The checkbox's hint says "Soonest first".
- `kept` includes `upcoming`, so pagination, HTMX updates and filtered/Clear behave like the
  other filters. Unknown values (anything other than `1`) mean off.

## R5 – The Upcoming page

- **Decision:** `GET /upcoming`, linked in the main navigation after Add a book. The
  service `upcoming_view(db, user_id, today)` returns:
  - `mine`: `ReadingEntryRepository(db, user_id).list_upcoming(today)`. It is
    owner-filtered, soonest first, with ties by title.
  - `others`: `catalog.upcoming_books(db, today)` (catalog books with
    `release_date > today`, soonest first), minus the ids from the owner-filtered
    `book_ids_on_list`.
- **Privacy:** the page never queries other members' entries, so "Also coming" can't
  reveal anything about them (FR-007).
- **Add to my list** links to `/books/add?book=<id>` (spec 006). No return parameter is
  added (spec assumption).
- **Alternatives:** a single SQL anti-join on `reading_entry` was rejected. It would
  bypass the owner-bound repository, and family-scale lists are small.

## R6 – The Now out notice

- **Decision:** `ReadingEntryRepository.list_now_out(today)` returns my entries with
  status `want_to_read` and `release_date BETWEEN today - 29 AND today`, ordered by
  `release_date DESC, lower(title)`. `my_list` renders it only on the full page, above the
  filters, in a `role="status"` notice, and never in the HTMX list partial. Filtering
  therefore doesn't repeat or remove it.
- **Rationale:** it is computed per view and nothing is stored (FR-006).

## R7 – Form fields

- **Release date:** an `<input type="date" name="release_date">` in
  `partials/book_fields.html`, after ISBN, labelled "Release date (optional)" with the hint
  "If the book isn't out yet, the date it's due." It is parsed with a
  `TypeAdapter(ReleaseDateIn)` (`date | None`, years 1000–9999). The error is "Enter a date
  like 2027-03-01". It is used by Add a book, Edit book (`/catalog/books/{id}/edit`) and
  the entry page's book section (`save_book_details`, `_unchanged`).
- **Pre-ordered:** in `partials/entry_fields.html`, a hidden `pre_ordered=""` is followed by
  a checkbox `pre_ordered=yes` labelled "Pre-ordered". Starlette's `FormData.get` returns
  the last value, so a ticked box wins and an unticked one leaves `""`. A form without
  the field (the JSON-less callers) changes nothing.
  - `parse_entry_update` adds `pre_ordered` when it is present.
  - `parse_add_book` reads it into `AddBookForm.pre_ordered`.
- **Carry-over (spec 004):** "Add and add another" clears both fields. They are specific
  to the book, like title and ISBN.

## R8 – JSON API (additive)

- `Book` response: `release_date: date | null`.
- `BookCreate` / `new_book`: optional `release_date`.
- `BookUpdate`: optional, nullable `release_date`.
- `ReadingEntry` response: `pre_ordered: bool`.
- `ReadingEntryCreate`: `pre_ordered: bool = false`.
- `ReadingEntryUpdate`: optional `pre_ordered` (not nullable).
- `GET /api/v1/me/readings`: query `upcoming: bool = false`. When it is true, the
  response is filtered and sorted as in R4.
- The spec 001 `openapi.yaml` and `openapi.generated.json` are updated. oasdiff sees only
  additions; adding a response property and an optional request field are non-breaking.

## R9 – Labels in the UI

- **A macro `release_label(book, entry=None)`** in `macros.html`, using the global `today`:
  - "Coming 3 Mar 2027" in a `span.coming` while the date is upcoming;
  - "· Pre-ordered" when `entry.pre_ordered` and the book is upcoming or now out.
- **Where it is used:**
  - My books rows: a new `.book-release` cell in the existing grid;
  - series page rows: inside `.series-status`;
  - the entry page heading area;
  - the chosen-book display on Add a book;
  - the Upcoming page.
- **The entry page** also shows "Released <date>" for a past date (FR-002).
