# Research: Series Viewer (spec 006)

## R1. Reading the page

- **Decision**: `series_view(db, user_id, series_id)` makes three reads:
  - `catalog_service.get_series` (Not Found as today);
  - `catalog_service.series_books` (every catalog book in the series, by number then title,
    from books-cay);
  - `ReadingEntryRepository(db, user_id).list_series(series_id)` (the viewer's own entries,
    owner-filtered).

  It returns `(series, SeriesView)`, where `SeriesView` holds the rows and the finished
  count.
- **Rationale**: both list queries already exist and are indexed (`book_series_id_idx`, and
  the user index on reading entries). No new query touches other members' entries
  (Principle I).
- **Alternative**: one outer join from book to the viewer's entry. Rejected: it would need
  a new persistence query in a coverage-critical module, for no gain at family scale.

## R2. Rows and gaps

- **Decision**: a pure `series_rows(books, entries) -> SeriesView` in `services/readings.py`:
  - **Book rows:** a `SeriesRow(kind="book", book, entry | None)` for each book, in the
    catalog order. The entry is matched by `book.id`.
  - **Gaps:** let `top = floor(max number)`. Every whole n in 1..top that no book has
    exactly is missing. Consecutive missing numbers form runs. A run of 1 to 3 numbers
    gives one `SeriesRow(kind="gap", first=n, last=n)` per number; a longer run gives one
    row `first..last`.
  - **Placement:** a gap row is inserted before the first book whose number is greater than
    the gap's `last`, so #6 comes before #6.5. Unnumbered books stay last.
  - **Finished count:** entries with status Finished whose book is in the list. The total
    is the number of book rows.
- **Rationale**: pure and easy to unit-test exhaustively (AC-14 to AC-16). The rule "more
  than three collapses" comes from the spec's assumptions.

## R3. Starting Add a book from a series row

- **Decision**: `GET /books/add` gains optional parameters, each parsed strictly; any bad
  value is ignored.
  - **`book=<uuid>`:** the catalog book is loaded with `catalog_service.get_book`; if it's
    not found, the plain form. `book_start_form(book)` fills:
    - `book_id`, title, `author_name_i`/`author_id_i`, `series_name`/`series_id` and
      `series_number` from the book;
    - status `want_to_read`.

    With `book_id` set, `POST /books/add` already adds that catalog book and ignores the
    typed fields (today's "picked from suggestions" path), so no new book can be created
    (AC-07).
  - **`series=<uuid>&number=<n>`:** the series is loaded with `get_series`; if it's not
    found, the plain form. `number` is validated with the existing series-number rule; if
    it's invalid, it's left blank. `series_start_form(series, number)` fills
    `series_name`/`series_id`, `series_number` and status `want_to_read`.
  - **`from_series=<uuid>`:** kept only if the series exists, and rendered as a hidden
    field. It can combine with either start.
  - **`after` (spec 004):** takes precedence when present.
- **Rationale**: reuses Add a book entirely (checks, conflicts, spec 005 prompts, spec 004
  buttons), so FR-008 holds by construction.
- **Default status Want to read:** from the spec's assumptions. The member can change it.

## R4. Returning to the series page

- **Decision**:
  - **Parsing:** `parse_add_book` reads `from_series` as a UUID (`AddBookForm.from_series`).
  - **Keeping it:** `add_book.html` renders it as a hidden field next to `then`, so it
    survives the 422 and 409 pages and the conflict buttons in the same form. The
    ISBN-conflict mini form ("Add “…” to my list instead") also carries it, as it carries
    `then`.
  - **Redirect:** on success with `then=list` and `from_series` set, `add_book` checks the
    series still exists (`get_series`). If it does, it answers
    `303 /series/<from_series>?added=<entry_id>`; if not, `/?msg=added`. `then=another`
    keeps spec 004's redirect (AC-11).
  - **Confirmation:** `GET /series/{id}?added=<entry_id>` loads the entry with the
    owner-filtered `service.get_entry`. If it is the member's own, the page shows "Added
    “Title” to your list." in a status region; another member's id, or a malformed one,
    shows nothing.
- **Rationale**: the redirect path is built from a parsed UUID, so there's no open
  redirect (FR-007). `?added=` follows the spec 004 `?after=` pattern, and a reload
  doesn't re-add.

## R5. Markup and layout

- **Decision**:
  - **List:** an `<ol class="series-rows" role="list">`, one `<li>` per row.
  - **Order within a row:** number badge, then title (a link to my entry when the book is
    on my list, plain text otherwise), then authors, then a status in text. The action link
    ("Add to my list" or "Add #n") comes last.
  - **Gap rows:** "#7 · Not in the family catalog yet" or "#8–#499 · …", with the link
    "Add #7".
  - **Progress:** a `<p>` above the list: "You've finished N of M books in this series."
  - **Empty series:** "The family catalog has no books in this series yet." and a link
    "Add a book to this series" (`?series=<id>&from_series=<id>`).
  - **CSS:** rows wrap; on a phone the action goes onto its own line. Links get
    `min-height: 44px`.
- **Rationale**: the reading order matches AC-18; status is text, not colour.
- **Accessible names:** each Add link names its book, as "Add “Summer Knight” to my list",
  with the visible text "Add to my list" and the title in a visually-hidden span. Gap
  links are "Add #7". This gives unique link names (WCAG 2.4.4).

## R6. Testing approach

- **Unit** (`series_rows`):
  - ordering, matching entries to books, and the finished count;
  - gaps: none, singles, a run of three versus four, fractional numbers, a large top,
    unnumbered books, and numbers starting above 1.
- **Integration** (no browser):
  - every row state and the progress line;
  - privacy: Ben's entries are invisible to Alice and don't change her counts;
  - 404s, and the empty series;
  - both start forms, with bad parameters ignored;
  - the return redirect through 422, 409 and spec 005 prompts;
  - `then=another`, "already on my list", and a cross-user `?added=`.
- **Browser** (`a11y`): widths, 44 px targets, axe, the reading order of a row, and the
  whole flow with JavaScript off.
- **Perf**: a 100-book series in the 5,000-book dataset, p95 under 1 s.
